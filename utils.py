################################################################################################# 
## Project name : Agentic AI POC                                                                #
## Business owner , Team : Data and AIA                                                         #
## Notebook Author , Team: POC Team                                                             #
## Date: 29th Oct 2025                                                                          #
## Purpose of Notebook: This file contains the function that will edit the runbook in AA.       #
#################################################################################################

import config
from azure.identity import DefaultAzureCredential, AzureCliCredential
from azure.mgmt.automation import AutomationClient
from datetime import datetime
import os

def create_new_runbook(runbook_name, system_name):
    cred = DefaultAzureCredential()
    client = AutomationClient(cred, config.SUBSCRIPTION_ID)
    time_stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    os.makedirs("generated_runbooks", exist_ok=True)

    new_runbook_name = f"{runbook_name}_{system_name}_{time_stamp}"
    file_name = f"{new_runbook_name}.ps1"
    file_path = os.path.join("generated_runbooks", file_name)

    print(f"Retrieving script from existing runbook: {runbook_name}")
    try:
        content_response = client.runbook_draft.get_content(
            resource_group_name=config.RESOURCE_GROUP,
            automation_account_name=config.AUTOMATION_ACCOUNT,
            runbook_name=runbook_name
        )
        source_script = (
            content_response.decode("utf-8")
            if hasattr(content_response, "decode")
            else str(content_response)
        )
        print(f"Successfully retrieved script from runbook: {runbook_name}")
    except Exception as e:
        print(f"Could not fetch source runbook content: {e}")
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
            content=source_script
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
