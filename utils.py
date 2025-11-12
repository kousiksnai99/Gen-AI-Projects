#################################################################################################
## Project Name: Agentic AI POC                                                                ##
## Business Owner / Team: Data and AIA                                                         ##
## Author / Team: POC Team                                                                     ##
## Date: 29th Oct 2025                                                                         ##
## Purpose: Utility functions for Azure Automation runbook handling.                           ##
## Dependencies: config.py, azure.identity, azure.mgmt.automation                              ##
#################################################################################################

###############  IMPORT PACKAGES  ###############
import config
from azure.identity import DefaultAzureCredential
from azure.mgmt.automation import AutomationClient
from datetime import datetime
import os
import requests
import logging

###############  LOGGING CONFIGURATION  ###############
logging.basicConfig(
    filename="agent_api.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

###############  FUNCTION DEFINITIONS  ###############
def get_source_content(runbook_name):
    """
    Fetch runbook content from Azure REST API.
    Works for both Draft and Published versions.
    """
    try:
        credential = DefaultAzureCredential()
        token = credential.get_token("https://management.azure.com/.default").token
        url = (
            f"https://management.azure.com/subscriptions/{config.SUBSCRIPTION_ID}"
            f"/resourceGroups/{config.RESOURCE_GROUP}"
            f"/providers/Microsoft.Automation/automationAccounts/{config.AUTOMATION_ACCOUNT}"
            f"/runbooks/{runbook_name}/content?api-version=2024-10-23"
        )
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/octet-stream"}
        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            logging.info(f"Successfully fetched content for {runbook_name}")
            return response.content.decode("utf-8", errors="ignore")
        else:
            logging.warning(f"Failed to fetch content: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        logging.error(f"Error fetching runbook content: {e}")
        return None


def create_new_runbook(runbook_name, system_name):
    """
    Creates a new runbook by copying content from an existing one.
    """
    try:
        cred = DefaultAzureCredential()
        client = AutomationClient(cred, config.SUBSCRIPTION_ID)
        time_stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        os.makedirs("generated_runbooks", exist_ok=True)

        new_runbook_name = f"{runbook_name}_{system_name}_{time_stamp}"
        file_name = f"{new_runbook_name}.ps1"
        file_path = os.path.join("generated_runbooks", file_name)

        logging.info(f"Retrieving script from existing runbook: {runbook_name}")

        source_script = None
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
            logging.info(f"Successfully retrieved draft content from runbook: {runbook_name}")
        except Exception as e:
            logging.warning(f"No draft version found: {e}")

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
                logging.info(f"Successfully retrieved published content from runbook: {runbook_name}")
            except Exception as e:
                logging.warning(f"Could not fetch published content: {e}. Trying REST fallback.")
                source_script = get_source_content(runbook_name)

        if not source_script:
            source_script = (
                f"# Auto-generated Runbook\n# Name: {file_name}\n# System: {system_name}\n"
                f"# Created: {time_stamp}\n\nWrite-Output 'Running {file_name}'\n"
            )

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(source_script)
        logging.info(f"Runbook file created locally: {file_path}")

        try:
            client.runbook.create_or_update(
                resource_group_name=config.RESOURCE_GROUP,
                automation_account_name=config.AUTOMATION_ACCOUNT,
                runbook_name=new_runbook_name,
                parameters={
                    "location": config.LOCATION,
                    "name": new_runbook_name,
                    "properties": {"runbookType": "PowerShell", "logProgress": True, "logVerbose": False},
                },
            )
            logging.info(f"Runbook created in Azure Automation: {new_runbook_name}")
        except Exception as e:
            logging.error(f"Error creating runbook: {e}")
            return

        try:
            poller = client.runbook_draft.begin_replace_content(
                resource_group_name=config.RESOURCE_GROUP,
                automation_account_name=config.AUTOMATION_ACCOUNT,
                runbook_name=new_runbook_name,
                runbook_content=source_script,
            )
            poller.result()
            logging.info(f"Content uploaded successfully to Azure Automation: {new_runbook_name}")
        except Exception as e:
            logging.error(f"Error uploading runbook content: {e}")

    except Exception as e:
        logging.error(f"Unexpected error in create_new_runbook: {e}")
