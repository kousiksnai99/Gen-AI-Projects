#################################################################################################
## File: main.py                                                                     #
## Purpose: Expose the diagnostic_agent functionality via FastAPI REST API                     #
#################################################################################################

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from diagnostic_agent import process_issue
from troubleshooting_agent import process_issue as process_troubleshoot_issue
from utils import create_new_runbook
import uvicorn


app = FastAPI(title="Diagnostic Agent API")

class IssueRequest(BaseModel):
    issue: str
    execute: bool = False
    target_machine: str = "demo_system"

@app.post("/diagnostic/chat")
def chat_with_agent(req: IssueRequest):
    """
    Takes an issue string and returns runbook name.
    Optionally executes the runbook if execute=True.
    """
    try:
        runbook_name = process_issue(req.issue)
        if not runbook_name:
            raise HTTPException(status_code=404, detail="No runbook name found from agent response.")

        if req.execute:
            create_new_runbook(runbook_name, req.target_machine)
            return {"runbook_name": runbook_name, "message": f"Runbook '{runbook_name}' executed on {req.target_machine}"}

        return {"runbook_name": runbook_name, "message": "Runbook ready but not executed."}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/troubleshoot/chat")
def chat_with_troubleshoot_agent(req: IssueRequest):
    """
    Takes an issue string and sends it to the troubleshooting agent.
    Optionally executes the runbook if execute=True.
    """
    try:
        runbook_name = process_troubleshoot_issue(req.issue)
        if not runbook_name:
            raise HTTPException(status_code=404, detail="No runbook name found from troubleshooting agent response.")

        if req.execute:
            create_new_runbook(runbook_name, req.target_machine)
            return {"runbook_name": runbook_name, "message": f"Runbook '{runbook_name}' executed on {req.target_machine}"}

        return {"runbook_name": runbook_name, "message": "Runbook ready but not executed."}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
def health_check():
    return {"status": "ok", "message": "Diagnostic Agent API is running"}

# Run locally with:  uvicorn main:app --reload
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
