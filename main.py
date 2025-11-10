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

app = FastAPI(title="Diagnostic + Troubleshooting Agent API")

class IssueRequest(BaseModel):
    issue: str
    execute: bool = False
    target_machine: str = "demo_system"

#########################################
# Diagnostic Agent Endpoint (UNCHANGED)
#########################################
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

#############################################
#  Troubleshooting Agent Endpoint (UPDATED)
#############################################
@app.post("/troubleshooting/chat")
def chat_with_troubleshooting_agent(req: IssueRequest):
    try:
        clean_name, full_text = troubleshooting_process_issue(req.issue)

        if not clean_name:
            raise HTTPException(status_code=404, detail="No runbook name found from troubleshooting agent.")

        if req.execute:
            create_new_runbook(clean_name, req.target_machine)
            return {
                "runbook_name": clean_name,
                "message": full_text + f"\n\n Runbook executed on {req.target_machine}"
            }

        return {
            "runbook_name": clean_name,
            "message": full_text  
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
def health_check():
    return {"status": "ok", "message": "API is running"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
