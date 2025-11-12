#################################################################################################
## Project Name: Agentic AI POC                                                                ##
## Business Owner / Team: Data and AIA                                                         ##
## Author / Team: POC Team                                                                     ##
## Date: 29th Oct 2025                                                                         ##
## Purpose: Troubleshooting Agent to identify and confirm automated runbook actions.           ##
## Dependencies: config.py                                                                     ##
#################################################################################################

###############  IMPORT PACKAGES  ###############
from azure.ai.projects import AIProjectClient
from azure.identity import AzureCliCredential
from azure.ai.agents.models import ListSortOrder
import config
import logging

###############  LOGGING CONFIGURATION  ###############
logging.basicConfig(
    filename="agent_api.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

###############  INITIALIZE AGENT  ###############
project = AIProjectClient(
    credential=AzureCliCredential(),
    endpoint=config.MODEL_ENDPOINT
)
agent = project.agents.get_agent(config.TROUBLESHOOTING_AGENT_ID)


###############  HELPER FUNCTIONS  ###############
def extract_runbook_name(full_text):
    """Extract only the runbook name from the beginning of the agent response."""
    if not full_text:
        return None
    first_line = full_text.split("\n")[0]
    clean = first_line.split("–")[0].split("-")[0].strip()
    return clean


###############  CORE FUNCTION  ###############
def process_issue(issue):
    """Process a troubleshooting issue and return a runbook suggestion."""
    try:
        thread = project.agents.threads.create()
        project.agents.messages.create(thread_id=thread.id, role="user", content=issue)

        run = project.agents.runs.create_and_process(thread_id=thread.id, agent_id=agent.id)
        if run.status == "failed":
            logging.error(f"Troubleshooting run failed: {run.last_error}")
            return None, None

        messages = project.agents.messages.list(thread_id=thread.id, order=ListSortOrder.ASCENDING)
        full_text = None
        for message in messages:
            if message.text_messages:
                full_text = message.text_messages[-1].text.value

        if not full_text:
            logging.warning("No troubleshooting text received.")
            return None, None

        clean_name = extract_runbook_name(full_text)
        logging.info(f"Troubleshooting agent suggested runbook: {clean_name}")
        return clean_name, full_text

    except Exception as e:
        logging.error(f"Error in troubleshooting process: {e}")
        return None, None
