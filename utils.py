################################################################################################# 
## Project name : Agentic AI POC                                                                #
## Business owner , Team : Data and AIA                                                         #
## Notebook Author , Team: POC Team                                                             #
## Date: 29th Oct 2025                                                                          #
## Purpose of Notebook: This file contains the function that will edit the runbook in AA.       #
#################################################################################################

import config
from azure.identity import DefaultAzureCredential
from azure.mgmt.automation import AutomationClient
from datetime import datetime
import os
import requests

def get_source_content(runbook_name):
    """
    Fetch runbook content directly from Azure REST API.
    Works for both Draft and Published versions.
    """
    credential = DefaultAzureCredential()
    token = credential.get_token("https://management.azure.com/.default").token

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

    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        runbook_content = response.content.decode("utf-8", errors="ignore")
        print(f"Successfully fetched content for {runbook_name}")
        return runbook_content
    else:
        print(f"Failed to fetch content for {runbook_name}: {response.status_code} - {response.text}")
        return None


def create_new_runbook(runbook_name, system_name):
    """
    Creates a new runbook by copying content from an existing one.
    """
    cred = DefaultAzureCredential()
    client = AutomationClient(cred, config.SUBSCRIPTION_ID)
    time_stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    os.makedirs("generated_runbooks", exist_ok=True)

    new_runbook_name = f"{runbook_name}_{system_name}_{time_stamp}"
    file_name = f"{new_runbook_name}.ps1"
    file_path = os.path.join("generated_runbooks", file_name)

    print(f"Retrieving script from existing runbook: {runbook_name}")
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
        print(f"Successfully retrieved draft content from runbook: {runbook_name}")
    except Exception as e:
        print(f"No draft version found or error reading draft: {e}")

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
            print(f"Successfully retrieved published content from runbook: {runbook_name}")
        except Exception as e:
            print(f"Could not fetch published runbook content: {e}")
            print("Trying to fetch using REST API fallback method.")
            source_script = get_source_content(runbook_name)

    if not source_script:
        source_script = (
            f"# Auto-generated Runbook\n# Name: {file_name}\n# System: {system_name}\n"
            f"# Created: {time_stamp}\n\nWrite-Output 'Running {file_name}'\n"
        )

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(source_script)
    print(f"Runbook file created locally: {file_path}")

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
        print(f"Runbook created in Azure Automation: {runbook.name}")
    except Exception as e:
        print(f"Error creating runbook in Azure Automation: {e}")
        return

    try:
        poller = client.runbook_draft.begin_replace_content(
            resource_group_name=config.RESOURCE_GROUP,
            automation_account_name=config.AUTOMATION_ACCOUNT,
            runbook_name=new_runbook_name,
            runbook_content=source_script
        )
        poller.result()
        print(f"Runbook content uploaded successfully for: {file_name}")
    except Exception as e:
        print(f"Error replacing runbook content: {e}")

    try:
        client.runbook.begin_publish(
            resource_group_name=config.RESOURCE_GROUP,
            automation_account_name=config.AUTOMATION_ACCOUNT,
            runbook_name=new_runbook_name
        ).result()
        print(f"Runbook published successfully: {file_name}")
    except Exception as e:
        print(f"Error publishing runbook: {e}")
