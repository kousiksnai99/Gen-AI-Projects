#################################################################################################
## File: troubleshooting_agent.py
## Purpose: Agent that identifies the correct troubleshooting runbook for issues.
#################################################################################################

from azure.ai.projects import AIProjectClient
from azure.identity import AzureCliCredential
from azure.ai.agents.models import ListSortOrder
import config
from utils import sanitize_runbook_name

project = AIProjectClient(
    credential=AzureCliCredential(),
    endpoint=config.MODEL_ENDPOINT
)

agent = project.agents.get_agent(config.TROUBLESHOOTING_AGENT_ID)

def process_issue_troubleshoot(issue):
    # Create a new conversation thread
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

    messages = project.agents.messages.list(thread_id=thread.id, order=ListSortOrder.ASCENDING)

    runbook_name = None
    for message in messages:
        if message.text_messages:
            raw_name = message.text_messages[-1].text.value
            runbook_name = sanitize_runbook_name(raw_name)

    return runbook_name
