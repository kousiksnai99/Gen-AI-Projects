#################################################################################################
## Project name : Agentic AI POC                                                                #
## Purpose: Troubleshooting Agent                                                               #
#################################################################################################

from azure.ai.projects import AIProjectClient
from azure.identity import AzureCliCredential
from azure.ai.agents.models import ListSortOrder
import config
import re

# Initialize AI Project
project = AIProjectClient(
    credential=AzureCliCredential(),
    endpoint=config.MODEL_ENDPOINT
)

# Load Troubleshooting Agent
agent = project.agents.get_agent(config.TROUBLESHOOTING_AGENT_ID)


def extract_runbook_name(full_text):
    if not full_text:
        return None
    
    first_line = full_text.split("\n")[0]
    first_line = first_line.strip()

    # Remove description after hyphen/dash
    first_line = re.split(r"[–-]", first_line)[0].strip()

    # Replace spaces with underscores
    name = first_line.replace(" ", "_")

    # Remove special chars except _
    name = re.sub(r"[^A-Za-z0-9_]", "", name)

    # Ensure Troubleshoot_ prefix is there
    if not name.lower().startswith("troubleshoot"):
        name = "Troubleshoot_" + name

    return name



def process_issue(issue):
    # Create cloud thread
    thread = project.agents.threads.create()
    project.agents.messages.create(
        thread_id=thread.id,
        role="user",
        content=issue
    )

    # Process the response
    run = project.agents.runs.create_and_process(
        thread_id=thread.id,
        agent_id=agent.id
    )

    if run.status == "failed":
        print(f"Run failed: {run.last_error}")
        return None, None

    # Get messages
    messages = project.agents.messages.list(thread_id=thread.id, order=ListSortOrder.ASCENDING)

    full_text = None
    for message in messages:
        if message.text_messages:
            full_text = message.text_messages[-1].text.value

    if not full_text:
        return None, None

    clean_name = extract_runbook_name(full_text)

    return clean_name, full_text   

{
    "detail": "[Errno 22] Invalid argument: 'generated_runbooks\\\\Troubleshoot_KB0010265 — This is a \"Cannot Open Microsoft Outlook\" issue. I’m now performing the following steps:_demo_syetem_20251110_085241.ps1'"
}
