#################################################################################################
## Project name : Agentic AI POC                                                                #
## Business owner, Team : Data and AIA                                                          #
## Notebook Author, Team: POC Team                                                              #
## Date: 2025-10-29                                                                              #
## Purpose of Notebook: This module calls the configured Diagnostic Agent from Azure AI Projects.#
## Connections:                                                                                  #
##   - Uses config.py for configuration values (MODEL_ENDPOINT, DIAGNOSTIC_AGENT_ID, etc.)      #
##   - Uses utils.create_new_runbook when called from main to execute runbooks                   #
## Notes: Keep credential usage unchanged (DefaultAzureCredential / AzureCliCredential).         #
#################################################################################################

from __future__ import annotations

###############  IMPORT PACKAGES  ###############
import typing
from typing import Optional

from logger_config import get_logger

# Azure SDK imports (kept as in original code)
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential, AzureCliCredential
from azure.ai.agents.models import ListSortOrder
from azure.mgmt.automation import AutomationClient

import config
##################################################

logger = get_logger(__name__)

# ###############  INITIALIZE AZURE CLIENTS  ###############
# Use credentials as before. We keep behavior identical but centralize initialization.
_CREDENTIAL = DefaultAzureCredential()
try:
    _AUTOMATION_CLIENT = AutomationClient(_CREDENTIAL, config.SUBSCRIPTION_ID)
except Exception:
    _AUTOMATION_CLIENT = None  # keep backward-compatible behavior if automation client isn't used here

_project_client = AIProjectClient(credential=AzureCliCredential(), endpoint=config.MODEL_ENDPOINT)
_agent = _project_client.agents.get_agent(config.DIAGNOSTIC_AGENT_ID)
# ##########################################################

def process_issue(issue: str) -> Optional[str]:
    """
    Send the provided issue text to the Diagnostic Agent and return the runbook name.

    :param issue: free-text issue description
    :return: runbook name string or None if not found / on failure
    """
    if not issue:
        logger.warning("process_issue called with empty issue text.")
        return None

    try:
        # Create a new thread and post the user message
        thread = _project_client.agents.threads.create()
        _project_client.agents.messages.create(thread_id=thread.id, role="user", content=issue)

        # Trigger processing of the thread
        run = _project_client.agents.runs.create_and_process(thread_id=thread.id, agent_id=_agent.id)

        # Handle run status
        if run.status == "failed":
            logger.error("Diagnostic agent run failed: %s", getattr(run, "last_error", "<no error info>"))
            return None

        # Retrieve messages and extract the runbook name (last text message content)
        messages = _project_client.agents.messages.list(thread_id=thread.id, order=ListSortOrder.ASCENDING)
        runbook_name = None
        for message in messages:
            if message.text_messages:
                runbook_name = message.text_messages[-1].text.value

        if runbook_name:
            logger.info("Diagnostic agent returned runbook name: %s", runbook_name)
            return runbook_name
        else:
            logger.warning("Diagnostic agent returned no runbook_name for issue: %s", issue)
            return None

    except Exception as exc:
        logger.exception("Exception while processing diagnostic issue: %s", exc)
        return None
