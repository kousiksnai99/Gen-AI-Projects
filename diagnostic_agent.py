#################################################################################################
## Project Name   : Agentic AI POC
## Diagnostic Agent (instrumented with Time_Logger)
#################################################################################################

# ###############  IMPORT PACKAGES  ###############
import logging
from datetime import datetime
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential, AzureCliCredential
from azure.ai.agents.models import ListSortOrder
from azure.mgmt.automation import AutomationClient

import config
from utils import create_new_runbook  # create_new_runbook now accepts time_logger optional


# ###############  CONFIGURATION CONSTANTS  ###############
SUBSCRIPTION_ID = config.SUBSCRIPTION_ID
RESOURCE_GROUP = config.RESOURCE_GROUP
AUTOMATION_ACCOUNT = config.AUTOMATION_ACCOUNT
LOCATION = config.LOCATION

# ###############  LOGGING CONFIGURATION  ###############
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
)
logger = logging.getLogger("diagnostic_agent")


# ###############  AZURE CLIENT INIT (lazy inside function where we timestamp creds)  ###############
def _now_isoutc() -> str:
    return datetime.utcnow().isoformat(timespec="microseconds") + "Z"


def process_issue(issue: str) -> tuple[str | None, dict]:
    """
    Sends an issue to the Azure Diagnostic AI Agent and returns:
      - runbook_name (or None)
      - time_logger dict containing timing checkpoints for the agent portion

    Note: This function preserves existing behavior and adds timing instrumentation.
    """
    time_logger: dict = {}

    try:
        time_logger["Foundry_Start"] = _now_isoutc()

        # Authenticate (DefaultAzureCredential + CLI for AIProjectClient) — mark credential window
        time_logger["Cred_Start"] = _now_isoutc()
        default_credential = DefaultAzureCredential()
        ai_project_client = AIProjectClient(
            credential=AzureCliCredential(),
            endpoint=config.MODEL_ENDPOINT
        )
        diagnostic_agent = ai_project_client.agents.get_agent(config.DIAGNOSTIC_AGENT_ID)
        time_logger["Cred_End"] = _now_isoutc()

        # Create new thread
        time_logger["Foundry_Thread_Create_Start"] = _now_isoutc()
        thread = ai_project_client.agents.threads.create()
        time_logger["Foundry_Thread_Create_End"] = _now_isoutc()

        # Post message
        time_logger["Foundry_Message_Post_Start"] = _now_isoutc()
        ai_project_client.agents.messages.create(
            thread_id=thread.id,
            role="user",
            content=issue
        )
        time_logger["Foundry_Message_Post_End"] = _now_isoutc()

        # Execute agent run
        time_logger["Foundry_Run_Start"] = _now_isoutc()
        run = ai_project_client.agents.runs.create_and_process(
            thread_id=thread.id,
            agent_id=diagnostic_agent.id
        )
        time_logger["Foundry_Run_End"] = _now_isoutc()

        if run.status == "failed":
            logger.error("Diagnostic AI agent run failed: %s", run.last_error)
            time_logger["Foundry_End"] = _now_isoutc()
            return None, time_logger

        # Retrieve messages
        time_logger["Foundry_Retrieve_Start"] = _now_isoutc()
        messages = ai_project_client.agents.messages.list(
            thread_id=thread.id,
            order=ListSortOrder.ASCENDING
        )
        time_logger["Foundry_Retrieve_End"] = _now_isoutc()

        # Extract runbook name
        time_logger["Runbook_Resolution_Start"] = _now_isoutc()
        runbook_name: str | None = None
        for message in messages:
            if message.text_messages:
                runbook_name = message.text_messages[-1].text.value
        time_logger["Runbook_Resolution_End"] = _now_isoutc()

        time_logger["Foundry_End"] = _now_isoutc()

        logger.info("Diagnostic agent returned runbook: %s", runbook_name)
        return runbook_name, time_logger

    except Exception as exc:
        time_logger["Foundry_End"] = _now_isoutc()
        logger.exception("Exception occurred while processing diagnostic issue: %s", exc)
        return None, time_logger
