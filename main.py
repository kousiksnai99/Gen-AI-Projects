#################################################################################################
## File: main.py
## Purpose: Expose the diagnostic_agent and troubleshooting_agent functionality via FastAPI REST API
#################################################################################################

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from diagnostic_agent import process_issue
from troubleshooting_agent import process_issue_troubleshoot
from utils import create_new_runbook
import uvicorn

app = FastAPI(title="Diagnostic & Troubleshooting Agent API")

class IssueRequest(BaseModel):
    issue: str
    execute: bool = False
    target_machine: str = "demo_system"

@app.post("/diagnostic/chat")
def chat_with_agent(req: IssueRequest):
    """
    Diagnostic Agent → Returns runbook name, optionally executes.
    """
    try:
        runbook_name = process_issue(req.issue)
        if not runbook_name:
            raise HTTPException(status_code=404, detail="No runbook name found from diagnostic agent response.")

        if req.execute:
            create_new_runbook(runbook_name, req.target_machine)
            return {"runbook_name": runbook_name,
                    "message": f"Runbook '{runbook_name}' executed on {req.target_machine}"}

        return {"runbook_name": runbook_name, "message": "Runbook ready but not executed."}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/troubleshooting/chat")
def chat_with_troubleshooting_agent(req: IssueRequest):
    """
    Troubleshooting Agent → Same flow as diagnostic agent but with different agent model.
    """
    try:
        runbook_name = process_issue_troubleshoot(req.issue)
        if not runbook_name:
            raise HTTPException(status_code=404, detail="No valid runbook name returned from troubleshooting agent.")

        if req.execute:
            create_new_runbook(runbook_name, req.target_machine)
            return {"runbook_name": runbook_name,
                    "message": f"Runbook '{runbook_name}' executed on {req.target_machine}"}

        return {"runbook_name": runbook_name, "message": "Runbook ready but not executed."}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
def health_check():
    return {"status": "ok", "message": "Agent API is running"}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
