################################################################################################# 
## Project name : Agentic AI POC                                                                #
## Business owner , Team : Data and AIA                                                         #
## Notebook Author , Team: POC Team                                                             #
## Date: 29th Oct 2025                                                                          #
## Puprose of Notebook: This is the agent that takes summary as input and run on user machine.  #
#################################################################################################

# # Load all the libraries
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential, AzureCliCredential
from azure.ai.agents.models import ListSortOrder
from azure.mgmt.automation import AutomationClient
import config
from utilsy import create_new_runbook 
#import tools
subscription_id= config.SUBSCRIPTION_ID
resource_group= config.RESOURCE_GROUP
automation_account= config.AUTOMATION_ACCOUNT
LOCATION= config.LOCATION 
scripttext="test"
runbook_type="PowerShell"

cred=DefaultAzureCredential()
client=AutomationClient(cred, subscription_id)
 
project = AIProjectClient(
    credential=AzureCliCredential(),
    endpoint=config.MODEL_ENDPOINT)
# agent = project.agents.get_agent(config.DIAGNOSTIC_AGENT_ID)
test_input='n'

if test_input=='y':
    pass
else:
    agent = project.agents.get_agent(config.DIAGNOSTIC_AGENT_ID)

def process_issue(issue):
    # Create a new thread
    thread = project.agents.threads.create()
    project.agents.messages.create(
        thread_id=thread.id,
        role="user",
        content=issue
    )
    # Run the agent to process the thread
    run = project.agents.runs.create_and_process(
        thread_id=thread.id,
        agent_id=agent.id
    )
    # Handle run status
    if run.status == "failed":
        print(f"Run failed: {run.last_error}")
        return None

    # Retrieve messages and extract the runbook name
    messages = project.agents.messages.list(thread_id=thread.id, order=ListSortOrder.ASCENDING)
    runbook_name = None
    for message in messages:
        if message.text_messages:
            runbook_name = message.text_messages[-1].text.value

    if runbook_name:
        # execute_runbook(runbook_name)
        return runbook_name
    else:
        print("No runbook name found.")
        return None


# ========================= FASTAPI INTEGRATION START =========================
from fastapi import FastAPI, Request
from pydantic import BaseModel
import uvicorn

app = FastAPI(title="Agentic AI Diagnostic API")

class IssueRequest(BaseModel):
    issue: str
    execute: bool = False

@app.post("/chat")
def chat_with_agent(request: IssueRequest):
    issue_text = request.issue.strip()
    response = process_issue(issue_text)

    if response is None:
        return {"status": "failed", "message": "No runbook name found or agent failed."}

    if request.execute:
        create_new_runbook(response, 'api_system')
        return {
            "status": "success",
            "runbook_name": response,
            "action": "Executed runbook via API"
        }

    return {
        "status": "success",
        "runbook_name": response,
        "action": "Runbook identified but not executed"
    }
# ========================= FASTAPI INTEGRATION END =========================


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--api":
        # Run as FastAPI server
        uvicorn.run("diagnostic_agent:app", host="0.0.0.0", port=8000, reload=True)
    else:
        # Original CLI logic
        print("Chat with your agent.")
        issue = input("Your issue : ").strip()
        response = process_issue(issue)
        if test_input=='y':
            tools.execute_runbook(response)
        else:
            print("We are going to do testing in your system.")
            print("Please close all the confidential documents and type y")
            print(f"We will be executing {response} ")
            run_script=input ("y/n:    ")
            if run_script=='y':
                create_new_runbook(response, 'demo_system')
            else:
                print("Sorry I am exiting without Running the script")





Traceback (most recent call last):
  File "F:\Kousik\helpdesk_assistant\diagnostic_agent.py", line 73, in <module>
    from fastapi import FastAPI, Request
ModuleNotFoundError: No module named 'fastapi'

