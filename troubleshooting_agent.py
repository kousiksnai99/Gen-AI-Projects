#################################################################################################
## Project Name   : Agentic AI POC
## Purpose        : Troubleshooting Agent
## Author/Team    : POC Team
## Date           : 29th Oct 2025
##
## Description:
##   This script defines the Troubleshooting Agent, which interacts with an Azure AI Agent
##   to analyze user-provided issue descriptions and suggest the appropriate runbook for
##   automated issue resolution.
##
##   Key Responsibilities:
##     - Send troubleshooting issues to the Azure AI agent.
##     - Retrieve AI-generated responses and extract the runbook name.
##     - Return both the cleaned runbook name and full AI message for downstream execution.
#################################################################################################

# -----------------------------------------------------------------------------------------------
# Library Imports
# -----------------------------------------------------------------------------------------------
from azure.ai.projects import AIProjectClient
from azure.identity import AzureCliCredential
from azure.ai.agents.models import ListSortOrder
import config

# -----------------------------------------------------------------------------------------------
# Azure AI Project Initialization
# -----------------------------------------------------------------------------------------------
# Create an AI project client using Azure CLI credentials
ai_project_client = AIProjectClient(
    credential=AzureCliCredential(),
    endpoint=config.MODEL_ENDPOINT
)

# Load the configured Troubleshooting Agent
troubleshooting_agent = ai_project_client.agents.get_agent(config.TROUBLESHOOTING_AGENT_ID)

# -----------------------------------------------------------------------------------------------
# Function: extract_runbook_name
# -----------------------------------------------------------------------------------------------
def extract_runbook_name(full_text: str) -> str | None:
    """
    Extract the runbook name from the beginning of the AI agent response.

    Example:
        Input  -> "Troubleshoot_KB0010265 – Cannot Open Outlook..."
        Output -> "Troubleshoot_KB0010265"

    Args:
        full_text (str): Full response text returned by the troubleshooting agent.

    Returns:
        str | None: Extracted runbook name if found, otherwise None.
    """
    if not full_text:
        return None

    # Consider only the first line of the AI response
    first_line = full_text.split("\n")[0]

    # Split before dash or en dash to isolate the runbook name
    clean_name = first_line.split("–")[0].split("-")[0].strip()

    return clean_name

# -----------------------------------------------------------------------------------------------
# Function: process_issue
# -----------------------------------------------------------------------------------------------
def process_issue(issue: str) -> tuple[str | None, str | None]:
    """
    Send a troubleshooting issue to the Azure AI Troubleshooting Agent and
    retrieve the suggested runbook name along with the full explanation.

    Args:
        issue (str): The issue description provided by the user.

    Returns:
        tuple[str | None, str | None]:
            clean_runbook_name: The extracted runbook name (if available).
            full_response_text: The full AI-generated troubleshooting message.
    """
    try:
        # ---------------------------------------------------------------------------------------
        # Step 1: Create a new thread for this troubleshooting session
        # ---------------------------------------------------------------------------------------
        thread = ai_project_client.agents.threads.create()

        # ---------------------------------------------------------------------------------------
        # Step 2: Add the user's issue as a message in the thread
        # ---------------------------------------------------------------------------------------
        ai_project_client.agents.messages.create(
            thread_id=thread.id,
            role="user",
            content=issue
        )

        # ---------------------------------------------------------------------------------------
        # Step 3: Trigger the agent to process the issue
        # ---------------------------------------------------------------------------------------
        run = ai_project_client.agents.runs.create_and_process(
            thread_id=thread.id,
            agent_id=troubleshooting_agent.id
        )

        # Handle failure scenarios
        if run.status == "failed":
            print(f"[ERROR] Troubleshooting run failed: {run.last_error}")
            return None, None

        # ---------------------------------------------------------------------------------------
        # Step 4: Retrieve messages from the thread in chronological order
        # ---------------------------------------------------------------------------------------
        messages = ai_project_client.agents.messages.list(
            thread_id=thread.id,
            order=ListSortOrder.ASCENDING
        )

        full_response_text = None
        for message in messages:
            if message.text_messages:
                # Capture the last AI response text
                full_response_text = message.text_messages[-1].text.value

        if not full_response_text:
            print("[INFO] No text response received from troubleshooting agent.")
            return None, None

        # ---------------------------------------------------------------------------------------
        # Step 5: Extract the runbook name from the AI response
        # ---------------------------------------------------------------------------------------
        clean_runbook_name = extract_runbook_name(full_response_text)

        return clean_runbook_name, full_response_text

    except Exception as e:
        print(f"[EXCEPTION] Failed to process troubleshooting issue: {e}")
        return None, None
