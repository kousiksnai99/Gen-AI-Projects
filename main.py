#################################################################################################
## File: main.py
## Purpose: Expose REST APIs for Diagnostic and Troubleshooting Agents
## Author: <Your Name>
## Description:
##   This FastAPI service provides two main endpoints:
##     - /diagnostic/chat : Handles diagnostic issue analysis and optional runbook execution.
##     - /troubleshooting/chat : Handles troubleshooting issue resolution with a confirmation flow.
##   It also maintains a short-lived in-memory store for pending user confirmations.
#################################################################################################

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from diagnostic_agent import process_issue as diagnostic_process_issue
from troubleshooting_agent import process_issue as troubleshooting_process_issue
from utils import create_new_runbook
import uvicorn
from datetime import datetime, timedelta
import threading

# -----------------------------------------------------------------------------------------------
# FastAPI App Initialization
# -----------------------------------------------------------------------------------------------
app = FastAPI(title="Diagnostic & Troubleshooting Agent API")

# -----------------------------------------------------------------------------------------------
# Request Model Definition
# -----------------------------------------------------------------------------------------------
class IssueRequest(BaseModel):
    """
    Request model for diagnostic/troubleshooting chat endpoints.
    """
    issue: str                               # User-described issue or response (e.g., "Disk error", "yes")
    execute: bool = False                    # Whether to execute the generated runbook automatically
    target_machine: str = "demo_system"      # Target system or machine name


# -----------------------------------------------------------------------------------------------
# Global State: Pending Confirmations (In-memory store)
# Structure:
#   {
#       "machine_name": {
#           "runbook_name": str,
#           "full_text": str,
#           "expires_at": datetime
#       }
#   }
# -----------------------------------------------------------------------------------------------
PENDING_CONFIRMATIONS = {}
PENDING_LOCK = threading.Lock()
PENDING_TTL_SECONDS = 300  # Time-to-live for pending confirmations (in seconds)


# -----------------------------------------------------------------------------------------------
# Utility Function: Cleanup Expired Confirmations
# -----------------------------------------------------------------------------------------------
def cleanup_expired_pending():
    """
    Remove expired pending confirmations from the in-memory store.
    This function is called periodically before processing new troubleshooting requests.
    """
    with PENDING_LOCK:
        now = datetime.utcnow()
        expired_keys = [
            key for key, data in PENDING_CONFIRMATIONS.items()
            if data["expires_at"] <= now
        ]
        for key in expired_keys:
            del PENDING_CONFIRMATIONS[key]


# -----------------------------------------------------------------------------------------------
# Endpoint: Diagnostic Agent Chat
# -----------------------------------------------------------------------------------------------
@app.post("/diagnostic/chat")
def chat_with_diagnostic_agent(req: IssueRequest):
    """
    Endpoint for interacting with the Diagnostic Agent.

    Flow:
      1. Calls diagnostic agent to analyze the issue and get a runbook name.
      2. If 'execute=True', executes the runbook immediately on the target machine.
      3. Returns the runbook name and status message.
    """
    try:
        # Process the issue using the diagnostic agent
        runbook_name = diagnostic_process_issue(req.issue)

        if not runbook_name:
            raise HTTPException(
                status_code=404,
                detail="No runbook name found from diagnostic agent."
            )

        # Execute runbook immediately if requested
        if req.execute:
            create_new_runbook(runbook_name, req.target_machine)
            return {
                "runbook_name": runbook_name,
                "message": f"Runbook '{runbook_name}' executed on {req.target_machine}"
            }

        # Otherwise, return runbook information only
        return {
            "runbook_name": runbook_name,
            "message": "Runbook ready but not executed."
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# -----------------------------------------------------------------------------------------------
# Endpoint: Troubleshooting Agent Chat (Two-step confirmation flow)
# -----------------------------------------------------------------------------------------------
@app.post("/troubleshooting/chat")
def chat_with_troubleshooting_agent(req: IssueRequest):
    """
    Endpoint for interacting with the Troubleshooting Agent.

    Flow:
      - Step 1: User describes an issue → agent suggests a runbook and asks for confirmation.
      - Step 2: User replies with 'yes'/'y' → stored runbook gets executed on the target machine.

    If execute=True during Step 1, the pending runbook suggestion is stored
    for confirmation for up to PENDING_TTL_SECONDS (default: 5 minutes).
    """
    try:
        # Clean up any expired pending confirmations before processing
        cleanup_expired_pending()

        user_input = (req.issue or "").strip().lower()

        # ---------------------------------------------------------------------------------------
        # Step 2: User confirms ("yes"/"y") → execute pending runbook
        # ---------------------------------------------------------------------------------------
        if user_input in ("yes", "y"):
            with PENDING_LOCK:
                pending = PENDING_CONFIRMATIONS.get(req.target_machine)

                if not pending:
                    raise HTTPException(
                        status_code=404,
                        detail="No pending runbook confirmation found for this target machine."
                    )

                runbook_name = pending["runbook_name"]
                # Remove pending to prevent duplicate execution
                del PENDING_CONFIRMATIONS[req.target_machine]

            # Execute the confirmed runbook
            create_new_runbook(runbook_name, req.target_machine)
            return {"message": f"Runbook '{runbook_name}' executed on {req.target_machine}"}

        # ---------------------------------------------------------------------------------------
        # Step 1: Initial issue description → agent suggests runbook
        # ---------------------------------------------------------------------------------------
        runbook_name, full_description = troubleshooting_process_issue(req.issue)

        if not runbook_name:
            raise HTTPException(
                status_code=404,
                detail="No runbook name found from troubleshooting agent."
            )

        # Store pending confirmation if execution is expected later
        if req.execute:
            with PENDING_LOCK:
                PENDING_CONFIRMATIONS[req.target_machine] = {
                    "runbook_name": runbook_name,
                    "full_text": full_description,
                    "expires_at": datetime.utcnow() + timedelta(seconds=PENDING_TTL_SECONDS)
                }

        # Prepare next-step confirmation prompt
        next_step_prompt = (
            f"Do you want me to fix this issue automatically by running runbook '{runbook_name}' (yes/no)?"
        )

        return {
            "message": full_description,
            "next_step": next_step_prompt
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# -----------------------------------------------------------------------------------------------
# Endpoint: Health Check
# -----------------------------------------------------------------------------------------------
@app.get("/health")
def health_check():
    """
    Simple API health check endpoint.
    """
    return {"status": "ok", "message": "API is running"}


# -----------------------------------------------------------------------------------------------
# Application Entry Point
# -----------------------------------------------------------------------------------------------
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
