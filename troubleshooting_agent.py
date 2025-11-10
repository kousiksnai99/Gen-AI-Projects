#################################################################################################
## Project name : Agentic AI POC                                                                #
## Business owner , Team : Data and AIA                                                         #
## Notebook Author , Team: POC Team                                                             #
## Date: 29th Oct 2025                                                                          #
## Purpose: Troubleshooting Agent - Same behavior style as Diagnostic agent                     #
## Returns: (clean_runbook_name, original_explanation_text)                                     #
#################################################################################################

from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential, AzureCliCredential
from azure.ai.agents.models import ListSortOrder
import config
import re

# Load Azure Config
subscription_id = config.SUBSCRIPTION_ID
resource_group = config.RESOURCE_GROUP
automation_account = config.AUTOMATION_ACCOUNT
LOCATION = config.LOCATION

# Create agent client (Same as Diagnostic)
project = AIProjectClient(
    credential=AzureCliCredential(),
    endpoint=config.MODEL_ENDPOINT
)

# Load Troubleshooting Agent ID
agent = project.agents.get_agent(config.TROUBLESHOOTING_AGENT_ID)

def extract_runbook_name(full_text):
    """
    Extract runbook name similar to diagnostic agent:
    - Take first line only
    - Remove emojis, quotes, extra punctuation
    - Convert spaces → underscores
    - Remove non-alphanumeric except underscores
    """
    if not full_text:
        return None
    
    first_line = full_text.split("\n")[0].strip()
    first_line = re.split(r"[–-]", first_line)[0].strip()
    name = first_line.replace(" ", "_")
    name = re.sub(r"[^A-Za-z0-9_]", "", name)

    if not name.lower().startswith("troubleshoot"):
        name = "Troubleshoot_" + name

    return name


def process_issue(issue):
    """
    Returns tuple: (runbook_name_for_automation, explanation_message_for_postman)
    """
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

    final_message = None
    for message in messages:
        if message.text_messages:
            final_message = message.text_messages[-1].text.value

    if not final_message:
        return None, None

    # Clean runbook name for Automation Account creation
    clean_name = extract_runbook_name(final_message)

    return clean_name, final_message
