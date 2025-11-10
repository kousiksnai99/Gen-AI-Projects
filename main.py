#################################################################################################
## File: main.py                                                                     #
## Purpose: Expose Diagnostic & Troubleshooting Agent APIs                            #
#################################################################################################

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from diagnostic_agent import process_issue as diagnostic_process_issue
from troubleshooting_agent import process_issue as troubleshooting_process_issue
from utils import create_new_runbook
import uvicorn
from datetime import datetime, timedelta
import threading

app = FastAPI(title="Diagnostic + Troubleshooting Agent API")

class IssueRequest(BaseModel):
    issue: str
    execute: bool = False
    target_machine: str = "demo_system"

# In-memory pending confirmation store
# Structure: { target_machine: {"runbook_name": str, "full_text": str, "expires_at": datetime} }
PENDING_CONFIRMATIONS = {}
PENDING_LOCK = threading.Lock()
PENDING_TTL_SECONDS = 300  # pending confirmation valid for 5 minutes

def cleanup_expired_pending():
    """Remove expired pending confirmations (run in background occasionally)."""
    with PENDING_LOCK:
        now = datetime.utcnow()
        expired_keys = [k for k, v in PENDING_CONFIRMATIONS.items() if v["expires_at"] <= now]
        for k in expired_keys:
            del PENDING_CONFIRMATIONS[k]

@app.post("/diagnostic/chat")
def chat_with_diagnostic_agent(req: IssueRequest):
    try:
        runbook_name = diagnostic_process_issue(req.issue)

        if not runbook_name:
            raise HTTPException(status_code=404, detail="No runbook name found from diagnostic agent.")

        if req.execute:
            create_new_runbook(runbook_name, req.target_machine)
            return {"runbook_name": runbook_name,
                    "message": f"Runbook '{runbook_name}' executed on {req.target_machine}"}

        return {"runbook_name": runbook_name, "message": "Runbook ready but not executed."}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/troubleshooting/chat")
def chat_with_troubleshooting_agent(req: IssueRequest):
    try:
        cleanup_expired_pending()

        user_input = (req.issue or "").strip().lower()

        # STEP 2 CONFIRMATION
        if user_input in ("yes", "y"):
            with PENDING_LOCK:
                pending = PENDING_CONFIRMATIONS.get(req.target_machine)
                if not pending:
                    raise HTTPException(status_code=404, detail="No pending runbook confirmation found.")
                runbook_name = pending["runbook_name"]
                del PENDING_CONFIRMATIONS[req.target_machine]

            create_new_runbook(runbook_name, req.target_machine)
            return {"message": f"Runbook executed on {req.target_machine}"}

        # STEP 1 - CALL AGENT
        runbook_name, step_message = troubleshooting_process_issue(req.issue)

        if not runbook_name:
            raise HTTPException(status_code=404, detail="No runbook identified.")

        if req.execute:
            with PENDING_LOCK:
                PENDING_CONFIRMATIONS[req.target_machine] = {
                    "runbook_name": runbook_name,
                    "expires_at": datetime.utcnow() + timedelta(seconds=PENDING_TTL_SECONDS)
                }

        return {
            "message": step_message,
            "next_step": "Do you want me to fix this issue automatically? (yes/no)"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
def health_check():
    return {"status": "ok", "message": "API is running"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
