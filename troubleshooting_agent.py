#################################################################################################
## Project name : Agentic AI POC - Troubleshooting Agent                                       #
## Business owner, Team : Data and AIA                                                         #
## Notebook Author , Team: POC Team                                                            #
## Date: 2025-11-12                                                                           #
## Purpose of File: Interact with Azure AI Projects to obtain a runbook name and full text.    #
## Connections: used by main.py (chat_with_troubleshooting_agent).                              #
#################################################################################################

###############  IMPORT PACKAGES  ###############
import logging
from azure.ai.projects import AIProjectClient
from azure.identity import AzureCliCredential, DefaultAzureCredential
from azure.ai.agents.models import ListSortOrder
import config

###############  LOGGER  ###############
logger = logging.getLogger("troubleshooting_agent")

###############  CLIENT FACTORY  ###############
def _get_project_client():
    """
    Create an AIProjectClient. We prefer AzureCliCredential for tool-compatible development,
    but DefaultAzureCredential (Managed Identity) is acceptable as well for production.
    """
    try:
        cred = AzureCliCredential()
        client = AIProjectClient(credential=cred, endpoint=config.MODEL_ENDPOINT)
        logger.info("Using AzureCliCredential for AIProjectClient.")
        return client
    except Exception:
        cred = DefaultAzureCredential()
        logger.info("Using DefaultAzureCredential for AIProjectClient.")
        return AIProjectClient(credential=cred, endpoint=config.MODEL_ENDPOINT)

###############  HELPER: extract_runbook_name  ###############
def extract_runbook_name(full_text: str):
    """
    Extract only the runbook name from the beginning of the response.
    Example incoming:
        "Troubleshoot_KB0010265 – Cannot Open Outlook..."
    Output:
        "Troubleshoot_KB0010265"

    This function provides limited, deterministic parsing and should be extended
    for language or formatting variations.
    """
    if not full_text:
        return None

    # First line only
    first_line = full_text.split("\n")[0]

    # Split before dash or long text (handles both en-dash and hyphen)
    clean = first_line.split("–")[0].split("-")[0].strip()

    return clean

###############  PUBLIC FUNCTION: process_issue  ###############
def process_issue(issue: str):
    """
    Create a thread with the troubleshooting agent and return a (clean_name, full_text) tuple.

    Returns:
        (clean_name: str, full_text: str) or (None, None) on failure.
    """
    if not issue:
        logger.warning("Empty issue passed to troubleshooting.process_issue")
        return None, None

    project = _get_project_client()
    agent = project.agents.get_agent(config.TROUBLESHOOTING_AGENT_ID)

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
        logger.error("Troubleshooting agent run failed: %s", getattr(run, "last_error", "<no error>"))
        return None, None

    # Get messages and pick the last text message as the full_text
    messages = project.agents.messages.list(thread_id=thread.id, order=ListSortOrder.ASCENDING)

    full_text = None
    for message in messages:
        if getattr(message, "text_messages", None):
            full_text = message.text_messages[-1].text.value

    if not full_text:
        logger.warning("No full_text returned by troubleshooting agent.")
        return None, None

    clean_name = extract_runbook_name(full_text)
    logger.info("Troubleshooting agent returned runbook name: %s", clean_name)
    return clean_name, full_text
