#################################################################################################
## Project Name   : Diagnostic & Troubleshooting Agent API
## Business Owner : <Fill In>
## Author/Team    : <Your Name> / <Team Name>
## Date           : 18-Nov-2025
##
## Purpose:
##   FastAPI service exposing REST APIs for Diagnostic and Troubleshooting Agents.
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

# Local modules
from diagnostic_agent import process_issue as diagnostic_process_issue
from troubleshooting_agent import process_issue as troubleshooting_process_issue
from utils import create_new_runbook

import uvicorn

# -----------------------------------------------------------------------------------------------
# CONSTANTS
# -----------------------------------------------------------------------------------------------
APP_TITLE = "Diagnostic & Troubleshooting Agent API"
PENDING_TTL_SECONDS: int = 300

# -----------------------------------------------------------------------------------------------
# LOGGING
# -----------------------------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
)
logger = logging.getLogger("diagnostic_troubleshooting_api")

# -----------------------------------------------------------------------------------------------
# FASTAPI APP
# -----------------------------------------------------------------------------------------------
app = FastAPI(title=APP_TITLE)


# -----------------------------------------------------------------------------------------------
# MODELS
# -----------------------------------------------------------------------------------------------
class IssueRequest(BaseModel):
    issue: str
    execute: bool = False
    target_machine: str = "demo_system"


class ConfirmRequest(BaseModel):
    confirm: bool
    target_machine: str


# -----------------------------------------------------------------------------------------------
# GLOBAL MEMORY STORE
# -----------------------------------------------------------------------------------------------
PENDING_CONFIRMATIONS: Dict[str, Dict[str, Any]] = {}
PENDING_LOCK = threading.Lock()


# -----------------------------------------------------------------------------------------------
# CLEANUP EXPIRED
# -----------------------------------------------------------------------------------------------
def cleanup_expired_pending() -> None:
    with PENDING_LOCK:
        now = datetime.utcnow()
        expired = [
            machine for machine, data in PENDING_CONFIRMATIONS.items()
            if data.get("expires_at") and data["expires_at"] <= now
        ]
        for machine in expired:
            logger.info("Removing expired pending confirmation for machine=%s", machine)
            del PENDING_CONFIRMATIONS[machine]


# -----------------------------------------------------------------------------------------------
# DIAGNOSTIC ENDPOINT
# -----------------------------------------------------------------------------------------------
@app.post("/diagnostic/chat")
def chat_with_diagnostic_agent(req: IssueRequest):
    """
    Diagnostic Agent API + TIME LOGGER
    """
    try:
        logger.info("Diagnostic request received | machine=%s execute=%s",
                    req.target_machine, req.execute)

        runbook_name, diag_time_logger = diagnostic_process_issue(req.issue)

        if not runbook_name:
            raise HTTPException(status_code=404, detail="Diagnostic agent returned no runbook.")

        if req.execute:
            create_new_runbook(runbook_name, req.target_machine)
            return {
                "runbook_name": runbook_name,
                "message": f"Runbook '{runbook_name}' executed on {req.target_machine}",
                "Diagnostic_Time_Logger": diag_time_logger
            }

        return {
            "runbook_name": runbook_name,
            "message": "Runbook ready but not executed.",
            "Diagnostic_Time_Logger": diag_time_logger
        }

    except Exception as exc:
        logger.exception("Error: %s", exc)
        raise HTTPException(status_code=500, detail="Internal server error")


# -----------------------------------------------------------------------------------------------
# TROUBLESHOOTING STEP 1
# -----------------------------------------------------------------------------------------------
@app.post("/troubleshooting/analyze")
def troubleshooting_analyze(req: IssueRequest):
    try:
        cleanup_expired_pending()
        runbook_name, full_description = troubleshooting_process_issue(req.issue)

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

    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error")


# -----------------------------------------------------------------------------------------------
# TROUBLESHOOTING STEP 2
# -----------------------------------------------------------------------------------------------
@app.post("/troubleshooting/confirm")
def troubleshooting_confirm(req: ConfirmRequest):
    try:
        cleanup_expired_pending()

        with PENDING_LOCK:
            pending = PENDING_CONFIRMATIONS.get(req.target_machine)
            if not pending:
                raise HTTPException(status_code=404, detail="No pending runbook found.")

            if not req.confirm:
                del PENDING_CONFIRMATIONS[req.target_machine]
                return {"message": "Runbook execution cancelled."}

            runbook_name = pending["runbook_name"]
            del PENDING_CONFIRMATIONS[req.target_machine]

        create_new_runbook(runbook_name, req.target_machine)
        return {"message": f"Runbook '{runbook_name}' executed on {req.target_machine}"}

    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error")


# -----------------------------------------------------------------------------------------------
# HEALTH CHECK
# -----------------------------------------------------------------------------------------------
@app.get("/health")
def health_check():
    return {"status": "ok"}


# -----------------------------------------------------------------------------------------------
# ENTRY POINT
# -----------------------------------------------------------------------------------------------
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
