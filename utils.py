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
import os
import tempfile   

def create_new_runbook(runbook_name, system_name):
    cred=DefaultAzureCredential()
    client=AutomationClient(cred, config.SUBSCRIPTION_ID)
    time_stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # NEW FUNCTIONALITY STARTS HERE
    # Always create a brand-new PowerShell file safely, without touching pre-approved ones
    new_runbook_name = f"{runbook_name}_{system_name}_{time_stamp}"
    temp_dir = tempfile.gettempdir()
    ps_script_path = os.path.join(temp_dir, f"{new_runbook_name}.ps1")

    ps_script_content = f"""
# ===============================================
# Auto-generated Runbook
# Name: {new_runbook_name}
# Created On: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
# ===============================================

Write-Output "Executing runbook: {new_runbook_name}"
"""
    with open(ps_script_path, "w", encoding="utf-8") as ps_file:
        ps_file.write(ps_script_content.strip())

    print(f"[INFO] Created new local runbook file: {ps_script_path}")
    # NEW FUNCTIONALITY ENDS HERE

    runbook=client.runbook.create_or_update(
        resource_group_name=config.RESOURCE_GROUP,
        automation_account_name= config.AUTOMATION_ACCOUNT,
        runbook_name=f"{runbook_name}_{system_name}_{time_stamp}",
        parameters={
            "location":config.LOCATION,
            "name": f"{runbook_name}_{system_name}_{time_stamp}",
            "properties":{
                "runbookType":"PowerShell",
                "logProgress": True,
                "logVerbose": False,
                },
                },
                )
    
    # Upload PowerShell script content to the new runbook
    with open(ps_script_path, "r", encoding="utf-8") as content_file:
        content = content_file.read()

    client.runbook_draft.replace_content(
        resource_group_name=config.RESOURCE_GROUP,
        automation_account_name=config.AUTOMATION_ACCOUNT,
        runbook_name=new_runbook_name,
        content=content,
    )

    # Publish the runbook
    client.runbook_draft.publish(
        resource_group_name=config.RESOURCE_GROUP,
        automation_account_name=config.AUTOMATION_ACCOUNT,
        runbook_name=new_runbook_name,
    )

    print(f"[SUCCESS] Runbook '{new_runbook_name}' created and published successfully.")