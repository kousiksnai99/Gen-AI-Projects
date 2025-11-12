#################################################################################################
## Project Name: Agentic AI POC                                                                ##
## Business Owner / Team: Data and AIA                                                         ##
## Author / Team: POC Team                                                                     ##
## Date: 29th Oct 2025                                                                         ##
## Purpose: Expose Diagnostic & Troubleshooting Agent APIs using FastAPI.                      ##
## Dependencies: diagnostic_agent.py, troubleshooting_agent.py, utils.py                       ##
#################################################################################################

###############  IMPORT PACKAGES  ###############
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from diagnostic_agent import process_issue as diagnostic_process_issue
from troubleshooting_agent import process_issue as troubleshooting_process_issue
from utils import create_new_runbook
from datetime import datetime, timedelta
import threading
import logging
import uvicorn

###############  LOGGING CONFIGURATION  ###############
logging.basicConfig(
    filename="agent_api.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

###############  APP INITIALIZATION  ###############
app = FastAPI(title="Diagnostic + Troubleshooting Agent API")

###############  DATA MODELS  ###############
class IssueRequest(BaseModel):
    issue: str
    execute: bool = False
    target_machine: str = "demo_system"

###############  GLOBAL VARIABLES  ###############
PENDING_CONFIRMATIONS = {}
PENDING_LOCK = threading.Lock()
PENDING_TTL_SECONDS = 300  # pending confirmation valid for 5 minutes


###############  UTILITY FUNCTIONS  ###############
def cleanup_expired_pending():
    """Remove expired pending confirmations from memory."""
    with PENDING_LOCK:
        now = datetime.utcnow()
        expired_keys = [k for k, v in PENDING_CONFIRMATIONS.items() if v["expires_at"] <= now]
        for k in expired_keys:
            del PENDING_CONFIRMATIONS[k]
            logging.info(f"Expired pending confirmation removed for {k}")


###############  API ROUTES  ###############
@app.post("/diagnostic/chat")
def chat_with_diagnostic_agent(req: IssueRequest):
    """
    Endpoint to communicate with Diagnostic Agent.
    It can either suggest or execute a diagnostic runbook.
    """
    try:
        runbook_name = diagnostic_process_issue(req.issue)
        if not runbook_name:
            raise HTTPException(status_code=404, detail="No runbook name found from diagnostic agent.")

        if req.execute:
            create_new_runbook(runbook_name, req.target_machine)
            logging.info(f"Runbook '{runbook_name}' executed on {req.target_machine}")
            return {"runbook_name": runbook_name,
                    "message": f"Runbook '{runbook_name}' executed on {req.target_machine}"}

        logging.info(f"Runbook '{runbook_name}' prepared but not executed.")
        return {"runbook_name": runbook_name, "message": "Runbook ready but not executed."}

    except Exception as e:
        logging.error(f"Diagnostic agent error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/troubleshooting/chat")
def chat_with_troubleshooting_agent(req: IssueRequest):
    """
    Two-step troubleshooting flow:
    Step 1: Request troubleshooting suggestion.
    Step 2: Confirm execution with "yes" or "y".
    """
    try:
        cleanup_expired_pending()
        user_issue_normalized = (req.issue or "").strip().lower()

        # Step 2: Execute confirmation
        if user_issue_normalized in ("yes", "y"):
            with PENDING_LOCK:
                pending = PENDING_CONFIRMATIONS.get(req.target_machine)
                if not pending:
                    raise HTTPException(status_code=404, detail="No pending runbook confirmation found.")
                runbook_name = pending["runbook_name"]
                del PENDING_CONFIRMATIONS[req.target_machine]

            create_new_runbook(runbook_name, req.target_machine)
            logging.info(f"Runbook executed on {req.target_machine}")
            return {"message": f"Runbook executed on {req.target_machine}"}

        # Step 1: Request troubleshooting suggestion
        clean_name, full_text = troubleshooting_process_issue(req.issue)
        if not clean_name:
            raise HTTPException(status_code=404, detail="No runbook name found from troubleshooting agent.")

        if req.execute:
            with PENDING_LOCK:
                PENDING_CONFIRMATIONS[req.target_machine] = {
                    "runbook_name": clean_name,
                    "full_text": full_text,
                    "expires_at": datetime.utcnow() + timedelta(seconds=PENDING_TTL_SECONDS)
                }

        next_step_text = f"Do you want me to fix this issue automatically by running runbook '{clean_name}' (yes/no)?"
        logging.info(f"Troubleshooting agent suggested runbook: {clean_name}")
        return {"message": full_text, "next_step": next_step_text}

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Troubleshooting agent error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "ok", "message": "API is running"}


###############  MAIN EXECUTION  ###############
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
