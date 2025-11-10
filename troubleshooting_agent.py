#################################################################################################
## Troubleshooting Agent - Similar to Diagnostic Agent but preserves explanation text          ##
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
    """
    Extract runbook name similar to diagnostic agent:
    - Take first line only
    - Remove emojis, quotes, extra punctuation
    - Convert spaces → underscores
    - Remove non-alphanumeric except underscores
    """

    first_line = full_text.split("\n")[0].strip()
    first_line = re.split(r"[–-]", first_line)[0].strip()
    name = first_line.replace(" ", "_")
    name = re.sub(r"[^A-Za-z0-9_]", "", name)

    if not name.lower().startswith("troubleshoot"):
        name = "Troubleshoot_" + name

    return name


def process_issue(issue):
    thread = project.agents.threads.create()
    project.agents.messages.create(thread_id=thread.id, role="user", content=issue)
    run = project.agents.runs.create_and_process(thread_id=thread.id, agent_id=agent.id)

    messages = project.agents.messages.list(thread_id=thread.id, order=ListSortOrder.ASCENDING)

    msg = None
    for message in messages:
        if message.text_messages:
            msg = message.text_messages[-1].text.value

    if not msg:
        return None, None

    clean_runbook_name = extract_runbook_name(msg)

    return clean_runbook_name, msg
