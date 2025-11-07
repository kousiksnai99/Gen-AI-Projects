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
from utils import create_new_runbook 

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
        return runbook_name
    else:
        print("No runbook name found.")
        return None





Retrieving script from existing runbook: This is an issue preventing Microsoft Outlook from opening. I’m now performing the following steps:
1. Checking for corrupted OST files and rebuilding them if needed
2. Resetting Outlook startup configuration
3. Repairing the Outlook profile and launch settings
No draft version found or error reading draft: Operation returned an invalid status 'Bad Request'
Content: <!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01//EN""http://www.w3.org/TR/html4/strict.dtd">
<HTML><HEAD><TITLE>Bad Request</TITLE>
<META HTTP-EQUIV="Content-Type" Content="text/html; charset=us-ascii"></HEAD>
<BODY><h2>Bad Request - Invalid URL</h2>
<hr><p>HTTP Error 400. The request URL is invalid.</p>
</BODY></HTML>

Could not fetch published runbook content: Operation returned an invalid status 'Bad Request'
Content: <!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01//EN""http://www.w3.org/TR/html4/strict.dtd">
<HTML><HEAD><TITLE>Bad Request</TITLE>
<META HTTP-EQUIV="Content-Type" Content="text/html; charset=us-ascii"></HEAD>
<BODY><h2>Bad Request - Invalid URL</h2>
<hr><p>HTTP Error 400. The request URL is invalid.</p>
</BODY></HTML>

Trying to fetch using REST API fallback method.
Failed to fetch content for This is an issue preventing Microsoft Outlook from opening. I’m now performing the following steps:
1. Checking for corrupted OST files and rebuilding them if needed
2. Resetting Outlook startup configuration
3. Repairing the Outlook profile and launch settings: 400 - <!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01//EN""http://www.w3.org/TR/html4/strict.dtd">
<HTML><HEAD><TITLE>Bad Request</TITLE>
<META HTTP-EQUIV="Content-Type" Content="text/html; charset=us-ascii"></HEAD>
<BODY><h2>Bad Request - Invalid URL</h2>
<hr><p>HTTP Error 400. The request URL is invalid.</p>
</BODY></HTML>

Runbook file created locally: generated_runbooks\This is an issue preventing Microsoft Outlook from opening. I’m now performing the following steps:
1. Checking for corrupted OST files and rebuilding them if needed
2. Resetting Outlook startup configuration
3. Repairing the Outlook profile and launch settings_demo_syetem_20251107_135932.ps1
Error creating runbook in Azure Automation: Cannot deserialize content-type: text/html
