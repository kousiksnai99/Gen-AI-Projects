#################################################################################################
## Project name : Agentic AI POC                                                                #
## Purpose: Troubleshooting Agent                                                               #
#################################################################################################

from azure.ai.projects import AIProjectClient
from azure.identity import AzureCliCredential
from azure.ai.agents.models import ListSortOrder
import config

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
    clean = first_line.split("–")[0].split("-")[0].strip()
    return clean


def extract_steps_only(full_text):
    """
    Removes the first line (runbook name + title) and returns only steps.
    """
    if not full_text:
        return None

    lines = full_text.split("\n")
    if len(lines) <= 1:
        return full_text  # Nothing to remove

    # Return everything AFTER first line
    return "\n".join(lines[1:]).strip()


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
        return None, None

    messages = project.agents.messages.list(thread_id=thread.id, order=ListSortOrder.ASCENDING)

    full_text = None
    for message in messages:
        if message.text_messages:
            full_text = message.text_messages[-1].text.value

    if not full_text:
        return None, None

    clean_name = extract_runbook_name(full_text)
    steps_only = extract_steps_only(full_text)

    return clean_name, steps_only
