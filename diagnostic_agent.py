################################################################################################# 
## Project name : Agentic AI POC                                                                #
## Business owner , Team : Data and AIA                                                         #
## Notebook Author , Team: POC Team                                                             #
## Date: 29th Oct 2025                                                                          #
## Purpose of Notebook: This is the agent that takes summary as input and runs on user machine. #
#################################################################################################

from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential, AzureCliCredential
from azure.ai.agents.models import ListSortOrder
from azure.mgmt.automation import AutomationClient
import config
from utils import create_new_runbook
import os
import sys

subscription_id = config.SUBSCRIPTION_ID
resource_group = config.RESOURCE_GROUP
automation_account = config.AUTOMATION_ACCOUNT
LOCATION = config.LOCATION
scripttext = "test"
runbook_type = "PowerShell"

cred = DefaultAzureCredential()
client = AutomationClient(cred, subscription_id)

project = AIProjectClient(
    credential=AzureCliCredential(),
    endpoint=config.MODEL_ENDPOINT
)
agent = project.agents.get_agent(config.DIAGNOSTIC_AGENT_ID)


def process_issue(issue):
    thread = project.agents.threads.create()
    project.agents.messages.create(
        thread_id=thread.id,
        role="user",
        content=issue
    )

    run = project.agents.runs.create_and_process(
        thread_id=thread.id,
        agent_id=agent.id
    )

    if run.status == "failed":
        print(f"Run failed: {run.last_error}")
        return None

    messages = project.agents.messages.list(
        thread_id=thread.id,
        order=ListSortOrder.ASCENDING
    )

    runbook_name = None
    for message in messages:
        if message.text_messages:
            runbook_name = message.text_messages[-1].text.value

    if runbook_name:
        create_new_runbook(runbook_name, 'system_name')
        return runbook_name
    else:
        print("No runbook name found.")
        return None


print("Chat with your agent.")
issue = input("Your issue : ").strip()
response = process_issue(issue)
create_new_runbook(response, 'demo_system')
