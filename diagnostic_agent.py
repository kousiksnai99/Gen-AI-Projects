#################################################################################################
## Project Name   : Agentic AI POC
## Business Owner : Data and AIA
## Author/Team    : POC Team
## Date           : 29th Oct 2025
## Purpose        : 
##   This script defines the Diagnostic Agent that takes a user-provided issue summary as input,
##   processes it through Azure AI Agent APIs, and returns the name of the runbook that can be 
##   executed on the user’s machine.
##
##   Key Functionalities:
##     - Connects to Azure Automation and AI Agent services.
##     - Sends issue text to a diagnostic AI agent.
##     - Retrieves and returns the corresponding runbook name.
#################################################################################################

# -----------------------------------------------------------------------------------------------
# Library Imports
# -----------------------------------------------------------------------------------------------
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential, AzureCliCredential
from azure.ai.agents.models import ListSortOrder
from azure.mgmt.automation import AutomationClient
import config
from utils import create_new_runbook

# -----------------------------------------------------------------------------------------------
# Configuration Constants
# -----------------------------------------------------------------------------------------------
SUBSCRIPTION_ID = config.SUBSCRIPTION_ID
RESOURCE_GROUP = config.RESOURCE_GROUP
AUTOMATION_ACCOUNT = config.AUTOMATION_ACCOUNT
LOCATION = config.LOCATION

# Default values for runbook
SCRIPT_TEXT = "test"
RUNBOOK_TYPE = "PowerShell"

# -----------------------------------------------------------------------------------------------
# Azure Authentication and Client Initialization
# -----------------------------------------------------------------------------------------------
# Default credential chain (Managed Identity, CLI, Environment, etc.)
default_credential = DefaultAzureCredential()

# Automation client for managing Azure Automation Runbooks
automation_client = AutomationClient(default_credential, SUBSCRIPTION_ID)

# AI Project client (uses Azure CLI authentication)
ai_project_client = AIProjectClient(
    credential=AzureCliCredential(),
    endpoint=config.MODEL_ENDPOINT
)

# Retrieve the configured diagnostic agent
diagnostic_agent = ai_project_client.agents.get_agent(config.DIAGNOSTIC_AGENT_ID)

# -----------------------------------------------------------------------------------------------
# Function: process_issue
# -----------------------------------------------------------------------------------------------
def process_issue(issue: str) -> str | None:
    """
    Process a user-reported issue using the Azure AI Diagnostic Agent.

    Args:
        issue (str): Description or summary of the issue provided by the user.

    Returns:
        str | None: The name of the runbook identified by the diagnostic agent,
                    or None if no runbook name was found.

    Flow:
        1. Create a new thread in the AI agent.
        2. Send the issue text as a user message.
        3. Run the agent to process the thread.
        4. Retrieve and parse messages to extract the runbook name.
    """
    try:
        # ---------------------------------------------------------------------------------------
        # Step 1: Create a new thread for this issue
        # ---------------------------------------------------------------------------------------
        thread = ai_project_client.agents.threads.create()

        # ---------------------------------------------------------------------------------------
        # Step 2: Post the issue message to the thread
        # ---------------------------------------------------------------------------------------
        ai_project_client.agents.messages.create(
            thread_id=thread.id,
            role="user",
            content=issue
        )

        # ---------------------------------------------------------------------------------------
        # Step 3: Execute the diagnostic agent to process the thread
        # ---------------------------------------------------------------------------------------
        run = ai_project_client.agents.runs.create_and_process(
            thread_id=thread.id,
            agent_id=diagnostic_agent.id
        )

        # ---------------------------------------------------------------------------------------
        # Step 4: Handle failure cases
        # ---------------------------------------------------------------------------------------
        if run.status == "failed":
            print(f"[ERROR] Diagnostic run failed: {run.last_error}")
            return None

        # ---------------------------------------------------------------------------------------
        # Step 5: Retrieve messages and extract the runbook name
        # ---------------------------------------------------------------------------------------
        messages = ai_project_client.agents.messages.list(
            thread_id=thread.id,
            order=ListSortOrder.ASCENDING
        )

        runbook_name = None
        for message in messages:
            if message.text_messages:
                # Assuming the last text message contains the runbook name
                runbook_name = message.text_messages[-1].text.value

        # ---------------------------------------------------------------------------------------
        # Step 6: Return runbook name (if found)
        # ---------------------------------------------------------------------------------------
        if runbook_name:
            return runbook_name
        else:
            print("[INFO] No runbook name found from diagnostic agent.")
            return None

    except Exception as e:
        print(f"[EXCEPTION] Failed to process issue: {e}")
        return None
