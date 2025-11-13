#################################################################################################
## Project Name   : Agentic AI POC
## Business Owner : Data and AIA
## Author/Team    : POC Team
## Date           : 29th Oct 2025
##
## Purpose:
##   This script contains helper functions that interact with Azure Automation (AA)
##   to fetch, duplicate, and publish runbooks programmatically.
##
##   Key Functionalities:
##     - Retrieve existing runbook content (draft, published, or via REST fallback).
##     - Create new runbooks by copying existing ones with timestamped names.
##     - Upload and publish new runbooks in Azure Automation.
#################################################################################################

# -----------------------------------------------------------------------------------------------
# Library Imports
# -----------------------------------------------------------------------------------------------
import os
import requests
from datetime import datetime
from azure.identity import DefaultAzureCredential
from azure.mgmt.automation import AutomationClient
import config

# -----------------------------------------------------------------------------------------------
# Function: get_source_content
# -----------------------------------------------------------------------------------------------
def get_source_content(runbook_name: str) -> str | None:
    """
    Fetch the content of an existing runbook from Azure Automation using the REST API.

    This function supports both Draft and Published runbook versions.

    Args:
        runbook_name (str): Name of the existing runbook in Azure Automation.

    Returns:
        str | None: The decoded runbook script content if fetched successfully,
                    otherwise None.
    """
    credential = DefaultAzureCredential()
    token = credential.get_token("https://management.azure.com/.default").token

    # Construct the Azure REST API endpoint URL
    url = (
        f"https://management.azure.com/subscriptions/{config.SUBSCRIPTION_ID}"
        f"/resourceGroups/{config.RESOURCE_GROUP}"
        f"/providers/Microsoft.Automation/automationAccounts/{config.AUTOMATION_ACCOUNT}"
        f"/runbooks/{runbook_name}/content?api-version=2024-10-23"
    )

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/octet-stream"
    }

    # Call the Azure REST API
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        runbook_content = response.content.decode("utf-8", errors="ignore")
        print(f"[INFO] Successfully fetched content for '{runbook_name}'.")
        return runbook_content
    else:
        print(f"[ERROR] Failed to fetch content for '{runbook_name}': "
              f"{response.status_code} - {response.text}")
        return None


# -----------------------------------------------------------------------------------------------
# Function: create_new_runbook
# -----------------------------------------------------------------------------------------------
def create_new_runbook(runbook_name: str, system_name: str) -> None:
    """
    Create a new Azure Automation runbook by duplicating the content of an existing one.

    If the existing runbook content is unavailable (neither draft nor published),
    a placeholder script is generated.

    Args:
        runbook_name (str): Name of the source runbook.
        system_name (str): Target system identifier to include in the new runbook name.

    Returns:
        None
    """
    credential = DefaultAzureCredential()
    client = AutomationClient(credential, config.SUBSCRIPTION_ID)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Local folder to store generated runbook scripts
    os.makedirs("generated_runbooks", exist_ok=True)

    # Build unique name for the new runbook
    new_runbook_name = f"{runbook_name}_{system_name}_{timestamp}"
    file_name = f"{new_runbook_name}.ps1"
    file_path = os.path.join("generated_runbooks", file_name)

    print(f"[INFO] Retrieving script content from existing runbook: '{runbook_name}'")

    source_script = None

    # -------------------------------------------------------------------------------------------
    # Attempt 1: Retrieve draft version
    # -------------------------------------------------------------------------------------------
    try:
        content_stream = client.runbook_draft.get_content(
            resource_group_name=config.RESOURCE_GROUP,
            automation_account_name=config.AUTOMATION_ACCOUNT,
            runbook_name=runbook_name
        )
        if hasattr(content_stream, "read"):
            source_script = content_stream.read().decode("utf-8")
        else:
            source_script = str(content_stream)
        print(f"[INFO] Successfully retrieved draft content from '{runbook_name}'.")
    except Exception as e:
        print(f"[WARN] No draft version found or failed to read draft: {e}")

    # -------------------------------------------------------------------------------------------
    # Attempt 2: Retrieve published version
    # -------------------------------------------------------------------------------------------
    if not source_script:
        try:
            content_stream = client.runbook.get_content(
                resource_group_name=config.RESOURCE_GROUP,
                automation_account_name=config.AUTOMATION_ACCOUNT,
                runbook_name=runbook_name
            )
            if hasattr(content_stream, "read"):
                source_script = content_stream.read().decode("utf-8")
            else:
                source_script = str(content_stream)
            print(f"[INFO] Successfully retrieved published content from '{runbook_name}'.")
        except Exception as e:
            print(f"[WARN] Could not fetch published content: {e}")
            print("[INFO] Attempting REST API fallback method.")
            source_script = get_source_content(runbook_name)

    # -------------------------------------------------------------------------------------------
    # Fallback: Generate default script if no content was retrieved
    # -------------------------------------------------------------------------------------------
    if not source_script:
        source_script = (
            f"# Auto-generated Runbook\n"
            f"# Name: {file_name}\n"
            f"# System: {system_name}\n"
            f"# Created: {timestamp}\n\n"
            f"Write-Output 'Running {file_name}'\n"
        )
        print("[INFO] Using auto-generated placeholder runbook content.")

    # -------------------------------------------------------------------------------------------
    # Write the runbook content to a local file
    # -------------------------------------------------------------------------------------------
    with open(file_path, "w", encoding="utf-8") as file:
        file.write(source_script)
    print(f"[INFO] Runbook file created locally: {file_path}")

    # -------------------------------------------------------------------------------------------
    # Step 1: Create a new runbook in Azure Automation
    # -------------------------------------------------------------------------------------------
    try:
        runbook = client.runbook.create_or_update(
            resource_group_name=config.RESOURCE_GROUP,
            automation_account_name=config.AUTOMATION_ACCOUNT,
            runbook_name=new_runbook_name,
            parameters={
                "location": config.LOCATION,
                "name": new_runbook_name,
                "properties": {
                    "runbookType": "PowerShell",
                    "logProgress": True,
                    "logVerbose": False,
                },
            },
        )
        print(f"[INFO] Runbook created in Azure Automation: '{runbook.name}'")
    except Exception as e:
        print(f"[ERROR] Failed to create runbook in Azure Automation: {e}")
        return

    # -------------------------------------------------------------------------------------------
    # Step 2: Upload content to the newly created runbook
    # -------------------------------------------------------------------------------------------
    try:
        poller = client.runbook_draft.begin_replace_content(
            resource_group_name=config.RESOURCE_GROUP,
            automation_account_name=config.AUTOMATION_ACCOUNT,
            runbook_name=new_runbook_name,
            runbook_content=source_script
        )
        poller.result()
        print(f"[INFO] Runbook content uploaded successfully: '{file_name}'")
    except Exception as e:
        print(f"[ERROR] Failed to upload runbook content: {e}")

    # -------------------------------------------------------------------------------------------
    # Step 3: Publish the runbook
    # -------------------------------------------------------------------------------------------
    try:
        client.runbook.begin_publish(
            resource_group_name=config.RESOURCE_GROUP,
            automation_account_name=config.AUTOMATION_ACCOUNT,
            runbook_name=new_runbook_name
        ).result()
        print(f"[INFO] Runbook published successfully: '{file_name}'")
    except Exception as e:
        print(f"[ERROR] Failed to publish runbook: {e}")
