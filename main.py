# FULL INTEGRATED main.py
# (Your provided file with JobIdRequest added and fetch-output endpoint working)

#################################################################################################
## Project Name   : Agentic AI POC
## Business Owner : Data and AIA
## Author/Team    : POC Team
## Date           : 29th Oct 2025
##
## Purpose:
##   FastAPI service exposing REST APIs for Diagnostic and Troubleshooting Agents.
##
##   Endpoints:
##     1. /diagnostic/chat
##          - Sends issue to Diagnostic Agent
##          - Optionally executes runbook immediately
##
##     2. /troubleshooting/analyze
##          - Sends issue to Troubleshooting Agent
##          - Returns full AI message + runbook name
##          - If execute=True → stored for confirmation
##
##     3. /troubleshooting/confirm
##          - Confirms runbook execution (yes/no equivalent)
##          - Executes stored runbook if confirmed
##
## Notes:
##   - Follow project coding patterns: strong sectioning, docstrings, logging, no prints.
##   - No external integrations (KeyVault, DevOps etc.) beyond existing imports.
#################################################################################################

# -----------------------------------------------------------------------------------------------
# IMPORTS
# -----------------------------------------------------------------------------------------------
from datetime import datetime, timedelta
import threading
import logging
from typing import Optional, Dict, Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

# Local modules (assumed present)
from diagnostic_agent import process_issue as diagnostic_process_issue
from troubleshooting_agent import process_issue as troubleshooting_process_issue
from utils import create_new_runbook

import uvicorn

# Disable Azure SDK verbose logging
logging.getLogger("azure").setLevel(logging.WARNING)
logging.getLogger("azure.core.pipeline.policies.http_logging_policy").setLevel(logging.WARNING)

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
    issue: str = Field(..., description="User issue description or input text")
    execute: bool = Field(False, description="Store runbook for execution if True")
    target_machine: str = Field("demo_system", description="Target system or machine name")


class ConfirmRequest(BaseModel):
    confirm: bool = Field(..., description="True = execute, False = cancel")
    target_machine: str = Field(..., description="Machine for which pending task exists")


class JobIdRequest(BaseModel):
    """
    Request model for fetching Azure Automation runbook output by job ID.
    """
    job_id: str = Field(..., description="Azure Automation Job ID")


# -----------------------------------------------------------------------------------------------
# GLOBAL IN-MEMORY STORE
# -----------------------------------------------------------------------------------------------
PENDING_CONFIRMATIONS: Dict[str, Dict[str, Any]] = {}
PENDING_LOCK = threading.Lock()


# -----------------------------------------------------------------------------------------------
# UTILITY FUNCTIONS
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
    try:
        logger.info(
            "Diagnostic request received | machine=%s execute=%s",
            req.target_machine, req.execute
        )

        runbook_name: Optional[str] = diagnostic_process_issue(req.issue)

        if not runbook_name:
            raise HTTPException(status_code=404, detail="Diagnostic agent returned no runbook.")

        if req.execute:
            create_new_runbook(runbook_name, req.target_machine)
            return {
                "runbook_name": runbook_name,
                "message": f"Runbook '{runbook_name}' executed on {req.target_machine}"
            }

        return {
            "runbook_name": runbook_name,
            "message": "Runbook ready but not executed."
        }

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Unhandled exception in /diagnostic/chat: %s", exc)
        raise HTTPException(status_code=500, detail="Internal server error")


# -----------------------------------------------------------------------------------------------
# TROUBLESHOOTING STEP-1
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


# -----------------------------------------------------------------------------------------------
# TROUBLESHOOTING STEP-2
# -----------------------------------------------------------------------------------------------
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

        return {
            "message": f"Runbook '{runbook_name}' executed on {req.target_machine}"
        }

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Unhandled exception in /troubleshooting/confirm: %s", exc)
        raise HTTPException(status_code=500, detail="Internal server error")


# -----------------------------------------------------------------------------------------------
# FETCH RUNBOOK OUTPUT BY JOB ID
# -----------------------------------------------------------------------------------------------
@app.post("/runbook/fetch-output")
async def fetch_output_by_job_id(request: JobIdRequest):
    try:
        from utils import get_runbook_output_by_job_id
        output = get_runbook_output_by_job_id(request.job_id)

        return {
            "job_id": request.job_id,
            "output": output
        }

    except Exception as exc:
        logger.error(f"Failed to fetch output: {exc}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch output: {exc}")


# -----------------------------------------------------------------------------------------------
# HEALTH CHECK
# -----------------------------------------------------------------------------------------------
@app.get("/health")
def health_check():
    return {"status": "ok", "message": "API is running"}


# -----------------------------------------------------------------------------------------------
# ENTRY POINT
# -----------------------------------------------------------------------------------------------
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
