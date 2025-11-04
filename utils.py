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

def create_new_runbook(runbook_name, system_name):
    cred = DefaultAzureCredential()
    client = AutomationClient(cred, config.SUBSCRIPTION_ID)
    time_stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    os.makedirs("generated_runbooks", exist_ok=True)

    new_runbook_name = f"{runbook_name}_{system_name}_{time_stamp}"
    file_name = f"{new_runbook_name}.ps1"
    file_path = os.path.join("generated_runbooks", file_name)

    print(f"Retrieving script from existing runbook: {runbook_name}")
    source_script = get_source_content(runbook_name)

    # Fallback if no content retrieved
    if not source_script:
        source_script = (
            f"# Auto-generated Runbook\n# Name: {file_name}\n# System: {system_name}\n"
            f"# Created: {time_stamp}\n\nWrite-Output 'Running {file_name}'\n"
        )

    with open(file_path, "w") as f:
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


def get_source_content(runbook_name):
    credential = DefaultAzureCredential()
    token = credential.get_token("https://management.azure.com/.default").token
    url = (
        f"https://management.azure.com/subscriptions/{config.SUBSCRIPTION_ID}"
        f"/resourceGroups/{config.RESOURCE_GROUP}/providers/Microsoft.Automation/"
        f"automationAccounts/{config.AUTOMATION_ACCOUNT}/runbooks/{runbook_name}/content"
        f"?api-version=2024-10-23"
    )
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/octet-stream"
    }

    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.content.decode("utf-8", errors="ignore")
    else:
        print(f"Failed to fetch content: {response.status_code} {response.text}")
        return None
