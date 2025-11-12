#################################################################################################
## Project name : Agentic AI POC                                                                #
## Business owner, Team : Data and AIA                                                          #
## Notebook Author, Team: POC Team                                                              #
## Date: 2025-11-12                                                                             #
## Purpose of Notebook: Expose Diagnostic & Troubleshooting Agent HTTP APIs (FastAPI app).     #
## Connections:                                                                                        #
##   - imports diagnostic_agent.process_issue                                                    #
##   - imports troubleshooting_agent.process_issue                                              #
##   - imports utils.create_new_runbook                                                           #
## Notes: This file contains the HTTP surface used by callers and orchestrates the two-step     #
## troubleshooting confirmation flow. Do not hardcode environment-specific values here.        #
#################################################################################################

from __future__ import annotations

###############  IMPORT PACKAGES  ###############
import threading
from datetime import datetime, timedelta
from typing import Dict, Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn

# Local modules
from logger_config import get_logger
from diagnostic_agent import process_issue as diagnostic_process_issue
from troubleshooting_agent import process_issue as troubleshooting_process_issue
from utils import create_new_runbook, validate_runbook_name
##################################################

logger = get_logger(__name__)

# ###############  APP / MODELS / CONSTANTS ###############
app = FastAPI(title="Diagnostic + Troubleshooting Agent API")

class IssueRequest(BaseModel):
    """
    Request body for both diagnostic and troubleshooting endpoints.

    Fields:
      - issue: textual description or 'yes'/'y' confirmation for runbook execution.
      - execute: boolean flag indicating that user expects a runbook to be stored as pending for confirmation.
      - target_machine: name of the target machine (used when executing runbooks).
    """
    issue: str
    execute: bool = False
    target_machine: str = "demo_system"

# In-memory pending confirmation store
# Structure: { target_machine: {"runbook_name": str, "full_text": str, "expires_at": datetime} }
PENDING_CONFIRMATIONS: Dict[str, Dict[str, Any]] = {}
PENDING_LOCK = threading.Lock()
PENDING_TTL_SECONDS = int(__import__("os").getenv("PENDING_TTL_SECONDS", 300))  # 5 minutes default
##########################################################

# ###############  HELPERS ###############
def cleanup_expired_pending() -> None:
    """
    Remove expired pending confirmations from the in-memory store.
    Intended to be called at start of troubleshooting request handling.
    """
    with PENDING_LOCK:
        now = datetime.utcnow()
        expired_keys = [key for key, value in PENDING_CONFIRMATIONS.items() if value["expires_at"] <= now]
        for key in expired_keys:
            logger.info("Cleaning up expired pending confirmation for target: %s", key)
            del PENDING_CONFIRMATIONS[key]
# #########################################


@app.post("/diagnostic/chat")
def chat_with_diagnostic_agent(req: IssueRequest):
    """
    Diagnostic endpoint:
      - Calls the diagnostic agent to obtain a runbook name (string).
      - If req.execute is True -> create and execute a new runbook copy on target machine.
      - Returns JSON containing runbook_name and a user-friendly message.

    Preserves previous behavior and signatures while adding logging and validation.
    """
    try:
        logger.info("Received diagnostic request for target '%s' (execute=%s)", req.target_machine, req.execute)
        runbook_name = diagnostic_process_issue(req.issue)

        if not runbook_name:
            logger.warning("Diagnostic agent returned no runbook name for issue: %s", req.issue)
            raise HTTPException(status_code=404, detail="No runbook name found from diagnostic agent.")

        # Validate runbook name format (best-effort)
        if not validate_runbook_name(runbook_name):
            logger.warning("Returned runbook name '%s' failed validation; continuing but logging.", runbook_name)

        if req.execute:
            create_new_runbook(runbook_name, req.target_machine)
            message = f"Runbook '{runbook_name}' executed on {req.target_machine}"
            logger.info(message)
            return {"runbook_name": runbook_name, "message": message}

        return {"runbook_name": runbook_name, "message": "Runbook ready but not executed."}

    except HTTPException:
        raise
    except Exception as exc:  # keep same behavior but logged
        logger.exception("Unhandled error in /diagnostic/chat: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/troubleshooting/chat")
def chat_with_troubleshooting_agent(req: IssueRequest):
    """
    Two-step troubleshooting flow:
      - If request.issue is an affirmative ("yes"/"y") (case-insensitive), we look up the pending confirmation
        for req.target_machine and, if found, execute the runbook and return execution message.
      - Otherwise: call the troubleshooting agent to get the runbook name and full_text, store a pending
        confirmation (only if req.execute True) and return the full_text + a next_step prompt.
    """
    try:
        logger.info("Received troubleshooting request for target '%s' (execute=%s)", req.target_machine, req.execute)

        # Clean expired pendings first
        cleanup_expired_pending()

        user_issue_normalized = (req.issue or "").strip().lower()

        # If user replied "yes" (confirmation) -> execute the pending runbook for this target_machine
        if user_issue_normalized in ("yes", "y"):
            with PENDING_LOCK:
                pending = PENDING_CONFIRMATIONS.get(req.target_machine)
                if not pending:
                    logger.warning("Confirmation requested but no pending runbook for target %s", req.target_machine)
                    raise HTTPException(status_code=404, detail="No pending runbook confirmation found for this target machine. Please request troubleshooting first.")
                runbook_name = pending["runbook_name"]

                # Remove pending immediately to avoid double execution
                del PENDING_CONFIRMATIONS[req.target_machine]

            # Execute runbook now
            create_new_runbook(runbook_name, req.target_machine)
            logger.info("Executed confirmed runbook '%s' for target '%s'", runbook_name, req.target_machine)
            return {"message": f"Runbook executed on {req.target_machine}"}

        # Otherwise: treat this as initial troubleshooting request
        clean_name, full_text = troubleshooting_process_issue(req.issue)

        if not clean_name:
            logger.warning("Troubleshooting agent returned no runbook name for issue: %s", req.issue)
            raise HTTPException(status_code=404, detail="No runbook name found from troubleshooting agent.")

        # Store pending confirmation (only if execute flag is True the user expects to run it later)
        if req.execute:
            with PENDING_LOCK:
                PENDING_CONFIRMATIONS[req.target_machine] = {
                    "runbook_name": clean_name,
                    "full_text": full_text,
                    "expires_at": datetime.utcnow() + timedelta(seconds=PENDING_TTL_SECONDS)
                }
            logger.info("Stored pending runbook '%s' for target '%s' (expires in %s seconds)", clean_name, req.target_machine, PENDING_TTL_SECONDS)

        # Respond with message and next_step prompt as requested
        next_step_text = (
            f"Do you want me to fix this issue automatically by running runbook '{clean_name}' (yes/no)?"
        )

        logger.debug("Returning troubleshooting response (runbook=%s)", clean_name)
        return {
            "message": full_text,
            "next_step": next_step_text
        }

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Unhandled error in /troubleshooting/chat: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/health")
def health_check():
    """Simple health check endpoint used by monitoring."""
    logger.debug("Health check called.")
    return {"status": "ok", "message": "API is running"}


if __name__ == "__main__":
    # Run uvicorn for local development. In production, deploy via ASGI server as appropriate.
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
