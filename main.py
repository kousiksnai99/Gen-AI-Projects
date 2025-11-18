#################################################################################################
## Project name : Diagnostic & Troubleshooting Agent API
## Business owner / Team : <Fill in>
## Author / Team : <Your Name> / <Team Name>
## Date : 2025-11-18
## Purpose :
##   FastAPI service exposing REST APIs for Diagnostic and Troubleshooting Agents.
##   - /diagnostic/chat     : Diagnostic agent analysis and optional runbook execution.
##   - /troubleshooting/chat : Troubleshooting agent suggestion + confirmation flow.
##
## Notes:
##   - This file follows the project's coding standards: clear sectioning, single import block,
##     documented functions, logging (no print), meaningful variable names, and in-file README.
##   - Do NOT integrate external resources here (Azure DevOps, KeyVault, CI/CD) — per request.
#################################################################################################

# ###############  IMPORT PACKAGES  ###############
from datetime import datetime, timedelta
import threading
import logging
from typing import Dict, Any, Optional, Tuple

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

# local module imports (assumed present and unchanged)
from diagnostic_agent import process_issue as diagnostic_process_issue
from troubleshooting_agent import process_issue as troubleshooting_process_issue
from utils import create_new_runbook

import uvicorn

# ###############  CONFIGURATION / CONSTANTS  ###############
APP_TITLE = "Diagnostic & Troubleshooting Agent API"
PENDING_TTL_SECONDS: int = 300  # TTL for pending confirmations (seconds)

# ###############  LOGGING SETUP  ###############
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
)
logger = logging.getLogger("diagnostic_troubleshooting_api")

# ###############  FASTAPI APP INITIALIZATION  ###############
app = FastAPI(title=APP_TITLE)


# ###############  REQUEST / RESPONSE MODELS  ###############
class IssueRequest(BaseModel):
    """
    Request model for diagnostic and troubleshooting endpoints.
    Fields:
      - issue: user-described issue or response (e.g. "Disk error", "yes")
      - execute: whether to execute the suggested runbook automatically or store for confirmation
      - target_machine: machine/system name the runbook will be executed against
    """
    issue: str = Field(..., description="User-described issue or reply (e.g., 'Disk error' or 'yes')")
    execute: bool = Field(False, description="Execute runbook immediately (or store for confirm when True)")
    target_machine: str = Field("demo_system", description="Target system or machine name")


# ###############  GLOBAL STATE: PENDING CONFIRMATIONS (IN-MEMORY)  ###############
# Structure:
#   {
#       "machine_name": {
#           "runbook_name": str,
#           "full_text": str,
#           "expires_at": datetime
#       }
#   }
PENDING_CONFIRMATIONS: Dict[str, Dict[str, Any]] = {}
PENDING_LOCK = threading.Lock()


# ###############  UTILITY FUNCTIONS  ###############
def cleanup_expired_pending() -> None:
    """
    Remove expired pending confirmations from the in-memory store.
    Called before processing troubleshooting requests to ensure stale entries are removed.
    """
    with PENDING_LOCK:
        now = datetime.utcnow()
        expired_keys = [
            machine for machine, data in PENDING_CONFIRMATIONS.items()
            if data.get("expires_at") and data["expires_at"] <= now
        ]
        for machine in expired_keys:
            logger.info("Cleaning up expired pending confirmation for machine: %s", machine)
            del PENDING_CONFIRMATIONS[machine]


# ###############  ENDPOINTS  ###############
@app.post("/diagnostic/chat")
def chat_with_diagnostic_agent(req: IssueRequest):
    """
    Endpoint to interact with Diagnostic Agent.

    Flow:
      1. Call diagnostic agent to analyze the issue and return a runbook name.
      2. If req.execute is True -> call create_new_runbook(...) to execute immediately.
      3. Return runbook name and a status message.
    """
    try:
        logger.info("Received diagnostic request for machine=%s execute=%s", req.target_machine, req.execute)

        runbook_name: Optional[str] = diagnostic_process_issue(req.issue)

        if not runbook_name:
            logger.warning("Diagnostic agent returned no runbook for issue: %s", req.issue)
            raise HTTPException(status_code=404, detail="No runbook name found from diagnostic agent.")

        if req.execute:
            # Execute runbook immediately
            logger.info("Executing runbook '%s' on machine '%s'", runbook_name, req.target_machine)
            create_new_runbook(runbook_name, req.target_machine)
            return {
                "runbook_name": runbook_name,
                "message": f"Runbook '{runbook_name}' executed on {req.target_machine}"
            }

        logger.info("Runbook '%s' ready (not executed) for machine '%s'", runbook_name, req.target_machine)
        return {
            "runbook_name": runbook_name,
            "message": "Runbook ready but not executed."
        }

    except HTTPException:
        # Re-raise HTTPExceptions to let FastAPI return them as-is
        raise
    except Exception as exc:  # broad exception only to convert to HTTP 500 with logging
        logger.exception("Unhandled exception in /diagnostic/chat: %s", exc)
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/troubleshooting/chat")
def chat_with_troubleshooting_agent(req: IssueRequest):
    """
    Endpoint to interact with Troubleshooting Agent - two-step confirmation flow.

    Flow:
      Step 1: User describes issue -> agent suggests runbook and (if execute=True) store pending confirmation.
      Step 2: User replies 'yes'/'y' -> execute pending runbook for the given target_machine.

    Note:
      - Pending confirmations are kept in-memory for a limited TTL (PENDING_TTL_SECONDS).
      - This function runs a cleanup for expired pendings at the start of each call.
    """
    try:
        logger.info("Received troubleshooting request for machine=%s execute=%s issue=%s",
                    req.target_machine, req.execute, req.issue)

        # Clean up expired pending confirmations first
        cleanup_expired_pending()

        user_input = (req.issue or "").strip().lower()

        # ---------------------------------------------
        # Step 2: Confirmation ("yes" or "y") -> execute stored runbook
        # ---------------------------------------------
        if user_input in ("yes", "y"):
            logger.info("User confirmed execution on machine '%s'", req.target_machine)
            with PENDING_LOCK:
                pending = PENDING_CONFIRMATIONS.get(req.target_machine)

                if not pending:
                    logger.warning("No pending runbook found for machine '%s' on confirmation", req.target_machine)
                    raise HTTPException(
                        status_code=404,
                        detail="No pending runbook confirmation found for this target machine."
                    )

                runbook_name = pending.get("runbook_name")
                # Remove pending to prevent duplicate execution
                del PENDING_CONFIRMATIONS[req.target_machine]

            # Execute the confirmed runbook
            logger.info("Executing confirmed runbook '%s' on machine '%s'", runbook_name, req.target_machine)
            create_new_runbook(runbook_name, req.target_machine)
            return {"message": f"Runbook '{runbook_name}' executed on {req.target_machine}"}

        # ---------------------------------------------
        # Step 1: Initial issue description -> agent suggests runbook
        # ---------------------------------------------
        runbook_result: Tuple[Optional[str], Optional[str]] = troubleshooting_process_issue(req.issue)
        # Expect troubleshooting_process_issue to return (runbook_name, full_description)
        runbook_name, full_description = runbook_result if isinstance(runbook_result, tuple) else (None, None)

        if not runbook_name:
            logger.warning("Troubleshooting agent returned no runbook for issue: %s", req.issue)
            raise HTTPException(status_code=404, detail="No runbook name found from troubleshooting agent.")

        # Store pending confirmation if user requested execution later (req.execute True)
        if req.execute:
            with PENDING_LOCK:
                PENDING_CONFIRMATIONS[req.target_machine] = {
                    "runbook_name": runbook_name,
                    "full_text": full_description,
                    "expires_at": datetime.utcnow() + timedelta(seconds=PENDING_TTL_SECONDS)
                }
                logger.info("Stored pending runbook '%s' for machine '%s' (ttl=%s seconds)",
                            runbook_name, req.target_machine, PENDING_TTL_SECONDS)

        next_step_prompt = (
            f"Do you want me to fix this issue automatically by running runbook '{runbook_name}' (yes/no)?"
        )

        return {
            "message": full_description,
            "next_step": next_step_prompt
        }

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Unhandled exception in /troubleshooting/chat: %s", exc)
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/health")
def health_check():
    """
    Simple health check endpoint.
    """
    return {"status": "ok", "message": "API is running"}


# ###############  APPLICATION ENTRY POINT  ###############
if __name__ == "__main__":
    # Running with reload=True is convenient for development only.
    # In production run via an ASGI server/process manager (gunicorn, uvicorn workers, etc.)
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
