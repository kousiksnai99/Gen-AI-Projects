#################################################################################################
## Project Name   : Agentic AI POC
## Business Owner : Data and AIA
## Author/Team    : POC Team
## Date           : 29th Oct 2025
## Purpose        :
##   Diagnostic Agent module for processing user-provided issue summaries through Azure AI Agent
##   services and extracting the name of the relevant automation runbook.
##
##   Key Functionalities:
##     - Connects to Azure Automation & Azure AI Agent services.
##     - Sends issue text to a Diagnostic AI Agent.
##     - Retrieves and returns the corresponding runbook name.
##
## Notes:
##   - This file follows DSET-standardized structure, comments, naming, and logging.
##   - No additional integrations added as per request.
#################################################################################################


# ###############  IMPORT PACKAGES  ###############
import logging
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential, AzureCliCredential
from azure.ai.agents.models import ListSortOrder
from azure.mgmt.automation import AutomationClient

import config
from utils import create_new_runbook


# ###############  CONFIGURATION CONSTANTS  ###############
SUBSCRIPTION_ID = config.SUBSCRIPTION_ID
RESOURCE_GROUP = config.RESOURCE_GROUP
AUTOMATION_ACCOUNT = config.AUTOMATION_ACCOUNT
LOCATION = config.LOCATION

# Default values for runbook creation
SCRIPT_TEXT = "test"
RUNBOOK_TYPE = "PowerShell"


# ###############  LOGGING CONFIGURATION  ###############
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
)
logger = logging.getLogger("diagnostic_agent")


# ###############  AZURE CLIENT INITIALIZATION  ###############
# Authenticate using DefaultAzureCredential (Supports MI, CLI, Env)
default_credential = DefaultAzureCredential()

# Azure Automation client
automation_client = AutomationClient(default_credential, SUBSCRIPTION_ID)

# Azure AI Project client (CLI credential)
ai_project_client = AIProjectClient(
    credential=AzureCliCredential(),
    endpoint=config.MODEL_ENDPOINT
)

# Fetch Diagnostic AI Agent instance
diagnostic_agent = ai_project_client.agents.get_agent(config.DIAGNOSTIC_AGENT_ID)


# ###############  FUNCTION: process_issue  ###############
def process_issue(issue: str) -> str | None:
    """
    Sends an issue description to the Azure Diagnostic AI Agent and extracts the
    recommended runbook name from the response messages.

    Args:
        issue (str):
            The text describing the user's problem or issue.

    Returns:
        str | None:
            The name of the runbook returned by the Diagnostic AI Agent,
            or None if no runbook was found or processing failed.

    Flow:
        1. Create a new AI agent thread.
        2. Add the issue text as a message.
        3. Run the agent on the thread.
        4. Retrieve and parse the resulting messages.
    """
    try:
        logger.info("Processing diagnostic issue: %s", issue)

        # Step 1: Create a new thread
        thread = ai_project_client.agents.threads.create()
        logger.debug("Created new diagnostic thread: %s", thread.id)

        # Step 2: Send user message to the thread
        ai_project_client.agents.messages.create(
            thread_id=thread.id,
            role="user",
            content=issue
        )
        logger.debug("Posted issue message to diagnostic thread")

        # Step 3: Run the diagnostic agent
        run = ai_project_client.agents.runs.create_and_process(
            thread_id=thread.id,
            agent_id=diagnostic_agent.id
        )

        # Step 4: Handle run failure
        if run.status == "failed":
            logger.error("Diagnostic AI agent run failed: %s", run.last_error)
            return None

        # Step 5: Retrieve messages to extract runbook name
        messages = ai_project_client.agents.messages.list(
            thread_id=thread.id,
            order=ListSortOrder.ASCENDING
        )

        runbook_name: str | None = None

        for message in messages:
            if message.text_messages:
                # Assume the final text message contains the runbook name
                runbook_name = message.text_messages[-1].text.value

        # Step 6: Return runbook name if found
        if runbook_name:
            logger.info("Diagnostic agent returned runbook: %s", runbook_name)
            return runbook_name

        logger.info("No runbook name found in diagnostic agent response.")
        return None

    except Exception as exc:
        logger.exception("Exception occurred while processing diagnostic issue: %s", exc)
        return None
