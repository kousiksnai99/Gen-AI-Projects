#################################################################################################
## Project name : Agentic AI POC - Diagnostic Agent                                            #
## Business owner, Team : Data and AIA                                                         #
## Notebook Author , Team: POC Team                                                            #
## Date: 2025-11-12                                                                           #
## Purpose of File: Interact with Azure AI Projects to obtain a runbook name for an issue.     #
## Connections: used by main.py (chat_with_diagnostic_agent).                                   #
## Notes: Uses DefaultAzureCredential (Managed Identity preferred) or AzureCliCredential as fallback.
#################################################################################################

###############  IMPORT PACKAGES  ###############
from datetime import datetime
import logging
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential, AzureCliCredential
from azure.ai.agents.models import ListSortOrder
from azure.mgmt.automation import AutomationClient
import config
from utils import create_new_runbook  # kept for backward compatibility, not invoked here
# NOTE: This module preserves original function name process_issue which main.py imports.

###############  LOGGER  ###############
logger = logging.getLogger("diagnostic_agent")

###############  CREDENTIALS / CLIENTS  ###############
# Use managed identity by default via DefaultAzureCredential. If environment forces CLI credential,
# AzureCliCredential may be used (helpful for local development).
try:
    _credential = DefaultAzureCredential()
    logger.info("Using DefaultAzureCredential for Azure SDKs (Managed Identity if available).")
except Exception:
    _credential = AzureCliCredential()
    logger.warning("DefaultAzureCredential failed; falling back to AzureCliCredential for local development.")

# Initialize automation and AI project clients (deferred in functions if needed)
def _get_automation_client():
    """Return an AutomationClient instance with configured subscription id."""
    return AutomationClient(_credential, config.SUBSCRIPTION_ID)

def _get_ai_project_client():
    """Return an AIProjectClient instance. Uses AzureCliCredential for project APIs if specified in config."""
    try:
        cli_cred = AzureCliCredential()
        return AIProjectClient(credential=cli_cred, endpoint=config.MODEL_ENDPOINT)
    except Exception:
        # fallback to DefaultAzureCredential
        return AIProjectClient(credential=_credential, endpoint=config.MODEL_ENDPOINT)

###############  PUBLIC FUNCTION: process_issue  ###############
def process_issue(issue: str):
    """
    Given a textual issue, ask the diagnostic AI agent to produce a runbook name.
    Returns:
        runbook_name (str) or None if not found.

    Note: This preserves your original behaviour and return contract.
    """
    if not issue:
        logger.warning("Empty issue passed to diagnostic.process_issue")
        return None

    project = _get_ai_project_client()
    agent = project.agents.get_agent(config.DIAGNOSTIC_AGENT_ID)

    # Create a thread and post the user message (same flow as original)
    thread = project.agents.threads.create()
    project.agents.messages.create(
        thread_id=thread.id,
        role="user",
        content=issue
    )

    # Process the agent run synchronously as before
    run = project.agents.runs.create_and_process(
        thread_id=thread.id,
        agent_id=agent.id
    )

    if run.status == "failed":
        logger.error("Agent run failed: %s", getattr(run, "last_error", "<no error>"))
        return None

    # Retrieve messages and extract the last text message value as runbook name
    messages = project.agents.messages.list(thread_id=thread.id, order=ListSortOrder.ASCENDING)
    runbook_name = None
    for message in messages:
        if getattr(message, "text_messages", None):
            runbook_name = message.text_messages[-1].text.value

    if runbook_name:
        logger.info("Diagnostic agent returned runbook name: %s", runbook_name)
        return runbook_name
    else:
        logger.warning("No runbook name found from diagnostic agent messages.")
        return None
