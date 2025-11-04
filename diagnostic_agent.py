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





#################################################################################################
## File: diagnostic_api.py                                                                     #
## Purpose: Expose the diagnostic_agent functionality via FastAPI REST API                     #
#################################################################################################

#################################################################################################
## Project name : Agentic AI POC                                                                #
## Business owner , Team : Data and AIA                                                         #
## Notebook Author , Team: POC Team                                                             #
## Date: 29th Oct 2025                                                                          #
## Purpose: FastAPI wrapper to trigger diagnostic agent workflow                                #
#################################################################################################

from fastapi import FastAPI, Request
import uvicorn
from diagnostic_agent import process_issue
from utilsy import create_new_runbook

app = FastAPI(title="Agentic AI Diagnostic API")

@app.post("/diagnostic/chat")
async def diagnostic_chat(request: Request):
    body = await request.json()
    issue = body.get("issue")

    if not issue:
        return {"error": "Missing 'issue' in request body."}

    response = process_issue(issue)
    if not response:
        return {"message": "No runbook found for the given issue."}

    print("We are going to do testing in your system.")
    print("Please close all confidential documents before proceeding.")
    print(f"We will be executing: {response}")

    runbook_created = create_new_runbook(response, 'demo_system')
    if runbook_created:
        return {"message": f"Runbook '{response}' executed successfully."}
    else:
        return {"error": "Failed to create or execute runbook."}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
