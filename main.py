#################################################################################################
## File: main.py
## Purpose: Expose Diagnostic & Troubleshooting Agent APIs
#################################################################################################

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from diagnostic_agent import process_issue as diagnostic_process_issue
from troubleshooting_agent import process_issue as troubleshooting_process_issue
from utils import create_new_runbook
import uvicorn

app = FastAPI(title="Diagnostic + Troubleshooting Agent API")

class IssueRequest(BaseModel):
    issue: str
    target_machine: str = "demo_system"
    confirm: str | None = None
    execute: bool = False


#########################################
# Diagnostic Agent Endpoint (RESTORED)
#########################################
@app.post("/diagnostic/chat")
def chat_with_diagnostic_agent(req: IssueRequest):
    try:
        runbook_name = diagnostic_process_issue(req.issue)

        if not runbook_name:
            raise HTTPException(status_code=404, detail="No runbook name found from diagnostic agent.")

        # If user asked to execute
        if req.execute:
            create_new_runbook(runbook_name, req.target_machine)
            return {
                "runbook_name": runbook_name,
                "message": f"Runbook '{runbook_name}' executed on {req.target_machine}"
            }

        # Return only runbook reference
        return {
            "runbook_name": runbook_name,
            "message": "Runbook ready but not executed."
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


#############################################
# Troubleshooting Agent Endpoint (Two-Step)
#############################################
@app.post("/troubleshooting/chat")
def chat_with_troubleshooting_agent(req: IssueRequest):
    try:
        clean_runbook_name, full_text = troubleshooting_process_issue(req.issue)

        if not clean_runbook_name:
            raise HTTPException(status_code=404, detail="No runbook name found")

        # Step 1: No confirmation yet → Only show summary
        if req.confirm is None:
            return {
                "summary": full_text,
                "target_machine": req.target_machine,
                "question": "Do you want to proceed with applying this fix on the machine?",
                "response_options": ["yes", "no"]
            }

        # Step 2: User confirmed yes → Execute
        if req.confirm.lower() == "yes":
            create_new_runbook(clean_runbook_name, req.target_machine)
            return {
                "message": f"Solution has been executed on {req.target_machine}."
            }

        # Step 2: User declined
        if req.confirm.lower() == "no":
            return {
                "message": "Execution cancelled."
            }

        return {"message": "Invalid confirm input. Use yes or no."}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
def health_check():
    return {"status": "ok", "message": "API is running"}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
