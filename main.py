#################################################################################################
## Project Name   : Diagnostic & Troubleshooting Agent API
## Business Owner : <Fill In>
## Author/Team    : <Your Name> / <Team Name>
## Date           : 18-Nov-2025
##
## Purpose:
##   FastAPI service exposing REST APIs for Diagnostic and Troubleshooting Agents.
##
## Notes:
##   - This file includes Time_Logger instrumentation for /diagnostic/chat.
#################################################################################################

# -----------------------------------------------------------------------------------------------
# IMPORTS
# -----------------------------------------------------------------------------------------------
from datetime import datetime, timedelta
import threading
import logging
from typing import Optional, Dict, Any, Tuple

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

# Local modules (assumed present)
# NOTE: diagnostic_process_issue now returns tuple (runbook_name, time_logger)
from diagnostic_agent import process_issue as diagnostic_process_issue
from troubleshooting_agent import process_issue as troubleshooting_process_issue
from utils import create_new_runbook

import uvicorn


# -----------------------------------------------------------------------------------------------
# APPLICATION CONSTANTS
# -----------------------------------------------------------------------------------------------
APP_TITLE = "Diagnostic & Troubleshooting Agent API"
PENDING_TTL_SECONDS: int = 300   # TTL for pending confirmations (seconds)


# -----------------------------------------------------------------------------------------------
# LOGGING SETUP
# -----------------------------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
)
logger = logging.getLogger("diagnostic_troubleshooting_api")


# -----------------------------------------------------------------------------------------------
# FASTAPI INITIALIZATION
# -----------------------------------------------------------------------------------------------
app = FastAPI(title=APP_TITLE)


# -----------------------------------------------------------------------------------------------
# REQUEST / RESPONSE MODELS
# -----------------------------------------------------------------------------------------------
class IssueRequest(BaseModel):
    """
    Request model for API interactions with Diagnostic and Troubleshooting Agents.
    """
    issue: str = Field(..., description="User issue description or input text")
    execute: bool = Field(False, description="Store/execute runbook if True")
    target_machine: str = Field("demo_system", description="Target system or machine name")


class ConfirmRequest(BaseModel):
    confirm: bool = Field(..., description="True = execute, False = cancel")
    target_machine: str = Field(..., description="Machine for which pending task exists")


# -----------------------------------------------------------------------------------------------
# GLOBAL IN-MEMORY STORE FOR PENDING RUNBOOK CONFIRMATIONS
# -----------------------------------------------------------------------------------------------
PENDING_CONFIRMATIONS: Dict[str, Dict[str, Any]] = {}
PENDING_LOCK = threading.Lock()


# -----------------------------------------------------------------------------------------------
# UTILITY FUNCTIONS
# -----------------------------------------------------------------------------------------------
def cleanup_expired_pending() -> None:
    """
    Removes expired pending confirmations from the in-memory store.
    """
    with PENDING_LOCK:
        now = datetime.utcnow()
        expired = [
            machine for machine, data in PENDING_CONFIRMATIONS.items()
            if data.get("expires_at") and data["expires_at"] <= now
        ]
        for machine in expired:
            logger.info("Removing expired pending confirmation for machine=%s", machine)
            del PENDING_CONFIRMATIONS[machine]


def _now_isoutc() -> str:
    """Helper — current UTC ISO timestamp with Z suffix."""
    return datetime.utcnow().isoformat(timespec="microseconds") + "Z"


# -----------------------------------------------------------------------------------------------
# DIAGNOSTIC AGENT ENDPOINT (with Time_Logger)
# -----------------------------------------------------------------------------------------------
@app.post("/diagnostic/chat")
def chat_with_diagnostic_agent(req: IssueRequest):
    """
    Diagnostic Agent API

    Enhanced with Time_Logger to measure timings across the diagnostic flow.
    Returns runbook_name, message, and Time_Logger dict in the response.
    """
    # Initialize local time logger
    time_logger: Dict[str, str] = {}

    try:
        # JSON parse start (request entry)
        time_logger["JSON_Parser_Start"] = _now_isoutc()

        # (Pydantic has already parsed `req` before reaching function)
        # JSON parse end
        time_logger["JSON_Parser_End"] = _now_isoutc()

        # Schema validation (we do a light manual check to mark times)
        time_logger["Schema_Validation_Start"] = _now_isoutc()
        # Minimal schema validation: ensure issue is non-empty string
        if not isinstance(req.issue, str) or not req.issue.strip():
            time_logger["Schema_Validation_End"] = _now_isoutc()
            raise HTTPException(status_code=422, detail="Invalid 'issue' field.")
        time_logger["Schema_Validation_End"] = _now_isoutc()

        # Config access (marking when config usage would happen)
        time_logger["Config_Start"] = _now_isoutc()
        # No heavy config ops here; this marks the interval for config reads.
        time_logger["Config_End"] = _now_isoutc()

        # Credentials / client init (if any) - we mark the window before calling diagnostic agent
        time_logger["Cred_Start"] = _now_isoutc()

        # Call into diagnostic agent — note: diagnostic_process_issue now returns (runbook_name, agent_time_logger)
        agent_result = diagnostic_process_issue(req.issue)

        # diagnostic_process_issue should return tuple (runbook_name, agent_time_logger)
        if isinstance(agent_result, tuple):
            runbook_name, agent_time = agent_result
            # Merge agent_time into our time_logger
            if isinstance(agent_time, dict):
                # only add keys that do not clobber existing keys
                for k, v in agent_time.items():
                    if k not in time_logger:
                        time_logger[k] = v
        else:
            # Backwards compatibility if agent returns only runbook name
            runbook_name = agent_result

        time_logger["Cred_End"] = _now_isoutc()

        if not runbook_name:
            time_logger["Runbook_Resolution_Start"] = time_logger.get("Runbook_Resolution_Start", _now_isoutc())
            time_logger["Runbook_Resolution_End"] = _now_isoutc()
            logger.warning("No runbook returned from diagnostic agent for issue: %s", req.issue)
            raise HTTPException(status_code=404, detail="Diagnostic agent returned no runbook.")

        # Runbook resolution timestamps (if agent didn't set them)
        time_logger.setdefault("Runbook_Resolution_Start", _now_isoutc())
        time_logger.setdefault("Runbook_Resolution_End", _now_isoutc())

        # If execute requested, call create_new_runbook and capture automation/cloning times
        if req.execute:
            time_logger["Automation_Start"] = _now_isoutc()
            # create_new_runbook now accepts optional time_logger to fill automation/cloning times
            try:
                create_new_runbook(runbook_name, req.target_machine, time_logger=time_logger)
            finally:
                time_logger["Automation_End"] = time_logger.get("Automation_End", _now_isoutc())
                time_logger.setdefault("Cloning_Start", time_logger.get("Cloning_Start", _now_isoutc()))
                time_logger.setdefault("Cloning_End", time_logger.get("Cloning_End", _now_isoutc()))

            return {
                "runbook_name": runbook_name,
                "message": f"Runbook '{runbook_name}' executed on {req.target_machine}",
                "Time_Logger": time_logger
            }

        # Non-execute path — return runbook and the collected time logger
        time_logger.setdefault("Event_Logger_Start", _now_isoutc())
        time_logger.setdefault("Event_Logger_End", _now_isoutc())

        return {
            "runbook_name": runbook_name,
            "message": "Runbook ready but not executed.",
            "Time_Logger": time_logger
        }

    except HTTPException:
        # Ensure we still return time logger for diagnostics when possible
        if "Time_Logger" in locals():
            # raise with HTTPException (FastAPI will return the status); include logger in logs only
            raise
        else:
            raise
    except Exception as exc:
        logger.exception("Unhandled exception in /diagnostic/chat: %s", exc)
        # Try to include partial time_logger
        response_payload = {"message": "Internal server error"}
        if time_logger:
            response_payload["Time_Logger"] = time_logger
        raise HTTPException(status_code=500, detail=response_payload)


# -----------------------------------------------------------------------------------------------
# TROUBLESHOOTING ENDPOINTS (unchanged)
# -----------------------------------------------------------------------------------------------
@app.post("/troubleshooting/analyze")
def troubleshooting_analyze(req: IssueRequest):
    try:
        logger.info(
            "Troubleshooting Step-1 | machine=%s execute=%s issue=%s",
            req.target_machine, req.execute, req.issue
        )

        cleanup_expired_pending()

        runbook_name, full_description = troubleshooting_process_issue(req.issue)

        if not runbook_name:
            raise HTTPException(status_code=404, detail="Troubleshooting agent returned no runbook.")

        if req.execute:
            with PENDING_LOCK:
                PENDING_CONFIRMATIONS[req.target_machine] = {
                    "runbook_name": runbook_name,
                    "full_text": full_description,
                    "expires_at": datetime.utcnow() + timedelta(seconds=PENDING_TTL_SECONDS)
                }

        return {
            "runbook_name": runbook_name,
            "full_description": full_description,
            "execute_pending": req.execute
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Unhandled exception in /troubleshooting/analyze: %s", exc)
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/troubleshooting/confirm")
def troubleshooting_confirm(req: ConfirmRequest):
    try:
        logger.info(
            "Troubleshooting Step-2 | machine=%s confirm=%s",
            req.target_machine, req.confirm
        )

        cleanup_expired_pending()

        with PENDING_LOCK:
            pending = PENDING_CONFIRMATIONS.get(req.target_machine)

            if not pending:
                raise HTTPException(status_code=404, detail="No pending runbook for this target machine.")

            if not req.confirm:
                del PENDING_CONFIRMATIONS[req.target_machine]
                return {"message": "Runbook execution cancelled."}

            runbook_name = pending["runbook_name"]
            del PENDING_CONFIRMATIONS[req.target_machine]

        create_new_runbook(runbook_name, req.target_machine)
        return {"message": f"Runbook '{runbook_name}' executed on {req.target_machine}"}
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Unhandled exception in /troubleshooting/confirm: %s", exc)
        raise HTTPException(status_code=500, detail="Internal server error")


# -----------------------------------------------------------------------------------------------
# HEALTH CHECK
# -----------------------------------------------------------------------------------------------
@app.get("/health")
def health_check():
    return {"status": "ok", "message": "API is running"}


# -----------------------------------------------------------------------------------------------
# APPLICATION ENTRY POINT
# -----------------------------------------------------------------------------------------------
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
