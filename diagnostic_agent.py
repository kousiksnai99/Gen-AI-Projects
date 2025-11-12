#################################################################################################
## Project Name: Agentic AI POC                                                                ##
## Business Owner / Team: Data and AIA                                                         ##
## Author / Team: POC Team                                                                     ##
## Date: 29th Oct 2025                                                                         ##
## Purpose: Diagnostic agent that processes user issue summary and identifies runbook.         ##
## Dependencies: config.py, utils.py                                                           ##
#################################################################################################

###############  IMPORT PACKAGES  ###############
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential, AzureCliCredential
from azure.ai.agents.models import ListSortOrder
from azure.mgmt.automation import AutomationClient
import config
from utils import create_new_runbook
import logging

###############  LOGGING CONFIGURATION  ###############
logging.basicConfig(
    filename="agent_api.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

###############  AZURE CONFIGURATION  ###############
subscription_id = config.SUBSCRIPTION_ID
resource_group = config.RESOURCE_GROUP
automation_account = config.AUTOMATION_ACCOUNT
LOCATION = config.LOCATION

###############  INITIALIZE AGENTS  ###############
cred = DefaultAzureCredential()
client = AutomationClient(cred, subscription_id)

project = AIProjectClient(
    credential=AzureCliCredential(),
    endpoint=config.MODEL_ENDPOINT
)
agent = project.agents.get_agent(config.DIAGNOSTIC_AGENT_ID)


###############  CORE FUNCTION  ###############
def process_issue(issue):
    """
    Process a diagnostic issue using Azure AI Agent to identify the relevant runbook.
    """
    try:
        thread = project.agents.threads.create()
        project.agents.messages.create(thread_id=thread.id, role="user", content=issue)

        run = project.agents.runs.create_and_process(thread_id=thread.id, agent_id=agent.id)
        if run.status == "failed":
            logging.error(f"Diagnostic run failed: {run.last_error}")
            return None

        messages = project.agents.messages.list(thread_id=thread.id, order=ListSortOrder.ASCENDING)
        runbook_name = None
        for message in messages:
            if message.text_messages:
                runbook_name = message.text_messages[-1].text.value

        if runbook_name:
            logging.info(f"Diagnostic agent returned runbook: {runbook_name}")
            return runbook_name
        else:
            logging.warning("Diagnostic agent returned no runbook.")
            return None
    except Exception as e:
        logging.error(f"Error in diagnostic process: {e}")
        return None
