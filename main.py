#################################################################################################
## Project name : Agentic AI POC - Diagnostic & Troubleshooting API                          #
## Business owner, Team : Data and AIA                                                        #
## Notebook Author, Team: POC Team                                                            #
## Date: 2025-11-12                                                                           #
## Purpose of File: Expose Diagnostic & Troubleshooting Agent HTTP APIs (FastAPI)             #
## Connections: imports diagnostic_agent.process_issue and troubleshooting_agent.process_issue #
## See: README / repo-level docs for architecture, CI/CD and environment promotion notes.     #
#################################################################################################

###############  IMPORT PACKAGES  ###############
from datetime import datetime, timedelta
import threading
import logging
import logging.handlers
import os

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# Local modules (kept same names and public function signatures)
from diagnostic_agent import process_issue as diagnostic_process_issue
from troubleshooting_agent import process_issue as troubleshooting_process_issue
from utils import create_new_runbook, send_telemetry_event  # send_telemetry_event optional

###############  SETTINGS / CONFIGURATION  ###############
# Environment-aware settings (do not hardcode environment-specific values)
ENVIRONMENT = os.getenv("ENVIRONMENT", "dev").lower()  # used by CI/CD pipelines to promote between envs
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))
PENDING_TTL_SECONDS = int(os.getenv("PENDING_TTL_SECONDS", "300"))  # 5 minutes default

###############  LOGGING SETUP  ###############
LOG_DIR = os.getenv("LOG_DIR", "logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, f"agent_api_{ENVIRONMENT}.log")

logger = logging.getLogger("agent_api")
logger.setLevel(logging.INFO)
handler = logging.handlers.RotatingFileHandler(LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8")
formatter = logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)

###############  APP INIT  ###############
app = FastAPI(title="Diagnostic + Troubleshooting Agent API", version="1.0.0")
logger.info(f"Starting Diagnostic + Troubleshooting Agent API (env={ENVIRONMENT})")

###############  DATA MODELS  ###############
class IssueRequest(BaseModel):
    """
    Input model for /diagnostic/chat and /troubleshooting/chat

    - issue: textual issue or a confirmation (yes/no)
    - execute: boolean, if True we store a pending confirmation or execute immediately (existing behaviour)
    - target_machine: logical target machine name (default demo_system)
    """
    issue: str
    execute: bool = False
    target_machine: str = "demo_system"

###############  IN-MEMORY PENDING CONFIRMATIONS  ###############
# Structure: { target_machine: {"runbook_name": str, "full_text": str, "expires_at": datetime} }
PENDING_CONFIRMATIONS = {}
PENDING_LOCK = threading.Lock()

def cleanup_expired_pending():
    """Remove expired pending confirmations."""
    with PENDING_LOCK:
        now = datetime.utcnow()
        expired_keys = [k for k, v in PENDING_CONFIRMATIONS.items() if v["expires_at"] <= now]
        for k in expired_keys:
            logger.info("Cleaning up expired pending confirmation for %s", k)
            del PENDING_CONFIRMATIONS[k]

###############  API ENDPOINTS  ###############
@app.post("/diagnostic/chat")
def chat_with_diagnostic_agent(req: IssueRequest):
    """
    1) Calls the diagnostic agent to get a runbook name.
    2) If req.execute is True, create and publish a new runbook for the target machine.
    Keeps JSON response compatible with previous behaviour.
    """
    try:
        logger.info("Received diagnostic request for target=%s", req.target_machine)
        runbook_name = diagnostic_process_issue(req.issue)

        if not runbook_name:
            logger.warning("Diagnostic agent did not return a runbook name for issue: %s", req.issue)
            raise HTTPException(status_code=404, detail="No runbook name found from diagnostic agent.")

        if req.execute:
            logger.info("Executing runbook '%s' on %s (requested execute=True)", runbook_name, req.target_machine)
            create_new_runbook(runbook_name, req.target_machine)
            send_telemetry_event({"event": "runbook_executed", "runbook": runbook_name, "target": req.target_machine})
            return {
                "runbook_name": runbook_name,
                "message": f"Runbook '{runbook_name}' executed on {req.target_machine}"
            }

        logger.info("Diagnostic runbook prepared (not executed) for %s: %s", req.target_machine, runbook_name)
        return {"runbook_name": runbook_name, "message": "Runbook ready but not executed."}

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error in diagnostic endpoint: %s", exc)
        send_telemetry_event({"event": "diagnostic_error", "error": str(exc)})
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/troubleshooting/chat")
def chat_with_troubleshooting_agent(req: IssueRequest):
    """
    Two-step troubleshooting flow (preserves prior behaviour):

    - If req.issue is "yes" or "y" (case-insensitive), attempt to execute a pending runbook for req.target_machine.
    - Otherwise, call the troubleshooting agent to generate runbook name + full_text, store pending confirmation (if execute True),
      and return the message and a next_step prompt asking for confirmation.

    This function adds better logging and telemetry while keeping behaviour intact.
    """
    try:
        logger.info("Received troubleshooting request for target=%s", req.target_machine)

        # Clean expired pendings first
        cleanup_expired_pending()

        user_issue_normalized = (req.issue or "").strip().lower()

        # If user replied "yes" (confirmation) -> execute the pending runbook for this target_machine
        if user_issue_normalized in ("yes", "y"):
            with PENDING_LOCK:
                pending = PENDING_CONFIRMATIONS.get(req.target_machine)
                if not pending:
                    logger.warning("No pending confirmation found for %s when user replied yes", req.target_machine)
                    raise HTTPException(status_code=404, detail="No pending runbook confirmation found for this target machine. Please request troubleshooting first.")
                runbook_name = pending["runbook_name"]
                # Remove pending immediately to avoid double execution
                del PENDING_CONFIRMATIONS[req.target_machine]

            logger.info("Executing pending runbook '%s' on %s after confirmation", runbook_name, req.target_machine)
            create_new_runbook(runbook_name, req.target_machine)
            send_telemetry_event({"event": "troubleshooting_runbook_executed", "runbook": runbook_name, "target": req.target_machine})
            return {"message": f"Runbook executed on {req.target_machine}"}

        # Otherwise: treat this as initial troubleshooting request
        clean_name, full_text = troubleshooting_process_issue(req.issue)

        if not clean_name:
            logger.warning("Troubleshooting agent did not return a runbook name for issue: %s", req.issue)
            raise HTTPException(status_code=404, detail="No runbook name found from troubleshooting agent.")

        # Store pending confirmation (only if execute flag is True the user expects to run it later)
        if req.execute:
            with PENDING_LOCK:
                PENDING_CONFIRMATIONS[req.target_machine] = {
                    "runbook_name": clean_name,
                    "full_text": full_text,
                    "expires_at": datetime.utcnow() + timedelta(seconds=PENDING_TTL_SECONDS)
                }
            logger.info("Stored pending confirmation for %s -> %s (ttl=%s)", req.target_machine, clean_name, PENDING_TTL_SECONDS)
            send_telemetry_event({"event": "troubleshooting_pending_stored", "runbook": clean_name, "target": req.target_machine})

        # Respond with message and next_step prompt as requested (same JSON fields as before)
        next_step_text = f"Do you want me to fix this issue automatically by running runbook '{clean_name}' (yes/no)?"

        return {
            "message": full_text,
            "next_step": next_step_text
        }

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error in troubleshooting endpoint: %s", exc)
        send_telemetry_event({"event": "troubleshooting_error", "error": str(exc)})
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/health")
def health_check():
    """Simple health check endpoint."""
    return {"status": "ok", "message": "API is running", "environment": ENVIRONMENT}

###############  MAIN LAUNCHER  ###############
if __name__ == "__main__":
    # For local/dev debugging only. In production, use proper uvicorn/gunicorn process manager and CI/CD.
    import uvicorn
    uvicorn.run("main:app", host=API_HOST, port=API_PORT, reload=True)
