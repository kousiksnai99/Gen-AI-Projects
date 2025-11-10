#################################################################################################
## File: main.py                                                                     #
## Purpose: Expose the diagnostic_agent & troubleshooting_agent via FastAPI REST API           #
#################################################################################################

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from diagnostic_agent import process_issue as diagnostic_process_issue
from troubleshooting_agent import process_issue as troubleshooting_process_issue
from utils import create_new_runbook
import uvicorn

app = FastAPI(title="Agentic AI Diagnostic & Troubleshooting API")

class IssueRequest(BaseModel):
    issue: str
    execute: bool = False
    target_machine: str = "demo_system"


############################################
# ✅ Diagnostic Agent Endpoint (NO CHANGE)
############################################
@app.post("/diagnostic/chat")
def chat_with_diagnostic_agent(req: IssueRequest):
    try:
        runbook_name = diagnostic_process_issue(req.issue)
        if not runbook_name:
            raise HTTPException(status_code=404, detail="No runbook name found from agent response.")

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

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


############################################
# ✅ Troubleshooting Agent Endpoint (NEW)
############################################
@app.post("/troubleshoot/chat")
def chat_with_troubleshooting_agent(req: IssueRequest):
    try:
        runbook_name, explanation = troubleshooting_process_issue(req.issue)

        if not runbook_name:
            raise HTTPException(status_code=404, detail="No valid runbook name returned by agent.")

        if req.execute:
            create_new_runbook(runbook_name, req.target_machine)
            return {
                "runbook_name": runbook_name,
                "message": explanation
            }

        return {
            "runbook_name": runbook_name,
            "message": explanation
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
def health_check():
    return {"status": "ok", "message": "API is running"}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
