#################################################################################################
## Project name : Agentic AI POC                                                                #
## Purpose: Troubleshooting Agent                                                               #
#################################################################################################

from azure.ai.projects import AIProjectClient
from azure.identity import AzureCliCredential
from azure.ai.agents.models import ListSortOrder
import config
import re

project = AIProjectClient(
    credential=AzureCliCredential(),
    endpoint=config.MODEL_ENDPOINT
)

agent = project.agents.get_agent(config.TROUBLESHOOTING_AGENT_ID)


def extract_runbook_name(full_text):
    if not full_text:
        return None
    
    first_line = full_text.split("\n")[0].strip()

    # Remove description part after dash
    first_line = re.split(r"[–-]", first_line)[0].strip()

    # Convert to safe file/runbook name
    name = re.sub(r"[^A-Za-z0-9_]", "_", first_line)

    if not name.lower().startswith("troubleshoot"):
        name = "Troubleshoot_" + name

    return name


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
        return None, None

    messages = project.agents.messages.list(thread_id=thread.id, order=ListSortOrder.ASCENDING)

    full_text = None
    for message in messages:
        if message.text_messages:
            full_text = message.text_messages[-1].text.value

    if not full_text:
        return None, None

    clean_name = extract_runbook_name(full_text)
    return clean_name, full_text
