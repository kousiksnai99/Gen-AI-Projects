#################################################################################################
## Project name : Agentic AI POC                                                                #
## Purpose: Troubleshooting Agent module                                                        #
## Connections:                                                                                  #
##   - Uses config.py for TROUBLESHOOTING_AGENT_ID and MODEL_ENDPOINT                           #
##   - Exposes process_issue(issue) which returns (clean_runbook_name, full_response_text)      #
#################################################################################################

from __future__ import annotations

###############  IMPORT PACKAGES  ###############
from typing import Optional, Tuple

from logger_config import get_logger

from azure.ai.projects import AIProjectClient
from azure.identity import AzureCliCredential
from azure.ai.agents.models import ListSortOrder

import config
##################################################

logger = get_logger(__name__)

# Initialize AI Project client (same behavior as before)
_project = AIProjectClient(credential=AzureCliCredential(), endpoint=config.MODEL_ENDPOINT)
_agent = _project.agents.get_agent(config.TROUBLESHOOTING_AGENT_ID)


def extract_runbook_name(full_text: str) -> Optional[str]:
    """
    Extract only the runbook name from the beginning of the response.
    Example incoming:
        "Troubleshoot_KB0010265 – Cannot Open Outlook..."
    Output:
        "Troubleshoot_KB0010265"

    This function performs a best-effort extraction and returns None if input is empty.
    """
    if not full_text:
        return None

    # Use only the first line for extraction
    first_line = full_text.split("\n")[0]

    # Split before typical dash characters and trim whitespace
    clean = first_line.split("–")[0].split("-")[0].strip()

    # Basic validation: must be a non-empty token
    if not clean:
        return None
    return clean


def process_issue(issue: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Send the issue text to the troubleshooting agent and return a tuple:
      (clean_runbook_name, full_text_response)

    :param issue: free-text issue description
    :return: (runbook_name, full_text) or (None, None) on failures
    """
    if not issue:
        logger.warning("process_issue called with empty issue text.")
        return None, None

    try:
        thread = _project.agents.threads.create()
        _project.agents.messages.create(thread_id=thread.id, role="user", content=issue)

        run = _project.agents.runs.create_and_process(thread_id=thread.id, agent_id=_agent.id)
        if run.status == "failed":
            logger.error("Troubleshooting agent run failed: %s", getattr(run, "last_error", "<no error info>"))
            return None, None

        messages = _project.agents.messages.list(thread_id=thread.id, order=ListSortOrder.ASCENDING)

        full_text = None
        for message in messages:
            if message.text_messages:
                full_text = message.text_messages[-1].text.value

        if not full_text:
            logger.warning("Troubleshooting agent returned empty response for issue: %s", issue)
            return None, None

        clean_name = extract_runbook_name(full_text)
        logger.info("Troubleshooting agent returned runbook '%s'", clean_name)
        return clean_name, full_text

    except Exception as exc:
        logger.exception("Exception while processing troubleshooting issue: %s", exc)
        return None, None
