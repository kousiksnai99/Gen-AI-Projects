################################################################################################# 
## Project name : Agentic AI POC                                                                #
## Business owner , Team : Data and AIA                                                         #
## Notebook Author , Team: POC Team                                                             #
## Date: 29th Oct 2025                                                                          #
## Puprose of Notebook: This file contains the function that will edit the runbook in AA.       #
#################################################################################################

# # Load all the libraries
import config
from azure.identity import DefaultAzureCredential, AzureCliCredential
from azure.mgmt.automation import AutomationClient
from datetime import datetime
import os  # ✅ Added for local file handling

def create_new_runbook(runbook_name, system_name):
    cred = DefaultAzureCredential()
    client = AutomationClient(cred, config.SUBSCRIPTION_ID)
    time_stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # ✅ Ensure a dedicated folder exists for storing new runbooks
    os.makedirs("generated_runbooks", exist_ok=True)

    # ✅ Create unique runbook file name and path
    file_name = f"{runbook_name}_{system_name}_{time_stamp}.ps1"
    file_path = os.path.join("generated_runbooks", file_name)

    # ✅ Create a PowerShell file locally — this will not touch any pre-approved runbook
    script_content = f"# Auto-generated Runbook\n# Name: {file_name}\n# System: {system_name}\n# Created: {time_stamp}\n\nWrite-Output 'Running {file_name}'\n"

    with open(file_path, "w") as f:
        f.write(script_content)

    print(f"✅ Runbook file created locally: {file_path}")

    # ✅ Create new runbook in Azure Automation with unique name
    runbook = client.runbook.create_or_update(
        resource_group_name=config.RESOURCE_GROUP,
        automation_account_name=config.AUTOMATION_ACCOUNT,
        runbook_name=f"{runbook_name}_{system_name}_{time_stamp}",
        parameters={
            "location": config.LOCATION,
            "name": f"{runbook_name}_{system_name}_{time_stamp}",
            "properties": {
                "runbookType": "PowerShell",
                "logProgress": True,
                "logVerbose": False,
            },
        },
    )

    print(f"☁️ Runbook created in Azure Automation: {runbook.name}")

    # ✅ Replace the draft content using the new async method
    try:
        poller = client.runbook_draft.begin_replace_content(
            resource_group_name=config.RESOURCE_GROUP,
            automation_account_name=config.AUTOMATION_ACCOUNT,
            runbook_name=f"{runbook_name}_{system_name}_{time_stamp}",
            content=script_content
        )
        poller.result()  # Wait for completion
        print(f"✍️ Runbook content uploaded successfully for: {file_name}")
    except Exception as e:
        print(f"⚠️ Error replacing runbook content: {e}")

    # ✅ Publish the new runbook (same as before, nothing changed)
    try:
        client.runbook.begin_publish(
            resource_group_name=config.RESOURCE_GROUP,
            automation_account_name=config.AUTOMATION_ACCOUNT,
            runbook_name=f"{runbook_name}_{system_name}_{time_stamp}"
        ).result()
        print(f"🚀 Runbook published successfully: {file_name}")
    except Exception as e:
        print(f"⚠️ Error publishing runbook: {e}")
