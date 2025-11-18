#################################################################################################
## Project Name   : Agentic AI POC
## Purpose        : Troubleshooting Agent
## Author/Team    : POC Team
## Date           : 29th Oct 2025
##
## Description:
##   This module defines the Troubleshooting Agent that interacts with an Azure AI Agent
##   to analyze issue descriptions and provide the recommended runbook for automated resolution.
##
## Key Responsibilities:
##   - Submit user troubleshooting input to the Azure AI Agent
##   - Retrieve generated AI messages
##   - Extract and return the runbook name + full AI response
##
## Notes:
##   - This file follows the DSET standardization guidelines.
##   - No new integrations or architectural changes were added per request.
#################################################################################################


# ###############  IMPORT PACKAGES  ###############
import logging
from azure.ai.projects import AIProjectClient
from azure.identity import AzureCliCredential
from azure.ai.agents.models import ListSortOrder
import config


# ###############  LOGGING CONFIGURATION ###############
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
)
logger = logging.getLogger("troubleshooting_agent")


# ###############  AZURE AI PROJECT INITIALIZATION ###############
# Azure AI Project Client using CLI Credential
ai_project_client = AIProjectClient(
    credential=AzureCliCredential(),
    endpoint=config.MODEL_ENDPOINT
)

# Load the configured Troubleshooting Agent
troubleshooting_agent = ai_project_client.agents.get_agent(config.TROUBLESHOOTING_AGENT_ID)


# ###############  FUNCTION: extract_runbook_name ###############
def extract_runbook_name(full_text: str) -> str | None:
    """
    Extracts the runbook name from the AI response text.

    Example:
        Input  -> "Troubleshoot_KB0010265 – Cannot Open Outlook..."
        Output -> "Troubleshoot_KB0010265"

    Args:
        full_text (str):
            The complete response text from the troubleshooting agent.

    Returns:
        str | None:
            The extracted runbook name, or None if extraction fails.
    """
    if not full_text:
        return None

    # Use only the first line of AI response
    first_line = full_text.split("\n")[0]

    # Split on dash or en dash to isolate runbook name
    runbook_name = first_line.split("–")[0].split("-")[0].strip()

    return runbook_name


# ###############  FUNCTION: process_issue ###############
def process_issue(issue: str) -> tuple[str | None, str | None]:
    """
    Sends a troubleshooting issue to the Azure AI Troubleshooting Agent
    and returns the suggested runbook name along with the full AI message.

    Args:
        issue (str):
            The user-provided issue description.

    Returns:
        tuple[str | None, str | None]:
            clean_runbook_name : Extracted runbook name
            full_response_text : Full AI-generated troubleshooting output
    """
    try:
        logger.info("Processing troubleshooting issue: %s", issue)

        # ---------------------------------------------
        # Step 1: Create a new thread for conversation
        # ---------------------------------------------
        thread = ai_project_client.agents.threads.create()
        logger.debug("Created troubleshooting thread: %s", thread.id)

        # ---------------------------------------------
        # Step 2: Post the user's issue to the thread
        # ---------------------------------------------
        ai_project_client.agents.messages.create(
            thread_id=thread.id,
            role="user",
            content=issue
        )

        # ---------------------------------------------
        # Step 3: Process the thread using the AI agent
        # ---------------------------------------------
        run = ai_project_client.agents.runs.create_and_process(
            thread_id=thread.id,
            agent_id=troubleshooting_agent.id
        )

        if run.status == "failed":
            logger.error("Troubleshooting agent run failed: %s", run.last_error)
            return None, None

        # ---------------------------------------------
        # Step 4: Retrieve agent messages in order
        # ---------------------------------------------
        messages = ai_project_client.agents.messages.list(
            thread_id=thread.id,
            order=ListSortOrder.ASCENDING
        )

        full_response_text = None

        for message in messages:
            if message.text_messages:
                # Capture last text message
                full_response_text = message.text_messages[-1].text.value

        if not full_response_text:
            logger.info("No response text received from troubleshooting agent.")
            return None, None

        # ---------------------------------------------
        # Step 5: Extract runbook name from response
        # ---------------------------------------------
        clean_runbook_name = extract_runbook_name(full_response_text)

        logger.info("Troubleshooting agent returned runbook: %s", clean_runbook_name)

        return clean_runbook_name, full_response_text

    except Exception as exc:
        logger.exception("Exception while processing troubleshooting issue: %s", exc)
        return None, None
