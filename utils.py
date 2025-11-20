#################################################################################################
## Project Name   : Agentic AI POC
## Business Owner : Data and AIA
## Author/Team    : POC Team
## Date           : 29th Oct 2025
##
## Purpose:
##   Helper utilities that interact with Azure Automation to:
##     - Retrieve runbook content (draft, published, or REST fallback)
##     - Duplicate existing runbooks
##     - Upload and publish new runbooks programmatically
##
## Notes:
##   - This file follows DSET standardization.
##   - No new features or workflow changes were introduced.
#################################################################################################


# ###############  IMPORTS  ###############
import os
import logging
import requests
from datetime import datetime

from azure.identity import DefaultAzureCredential
from azure.mgmt.automation import AutomationClient

import config

# Disable Azure SDK verbose logging
logging.getLogger("azure").setLevel(logging.WARNING)
logging.getLogger("azure.core.pipeline.policies.http_logging_policy").setLevel(logging.WARNING)
# ###############  LOGGING SETUP ###############
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
)
logger = logging.getLogger("automation_helpers")


# ###############  FUNCTION: get_source_content ###############
def get_source_content(runbook_name: str) -> str | None:
    """
    Fetch the content of a runbook from Azure Automation using the REST API.
    This method is used as fallback when draft/published versions cannot be retrieved.

    Args:
        runbook_name (str): Existing runbook name in Azure Automation.

    Returns:
        str | None: Script content if fetched successfully, else None.
    """
    try:
        credential = DefaultAzureCredential()
        token = credential.get_token("https://management.azure.com/.default").token

        # Construct REST API endpoint
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
            content = response.content.decode("utf-8", errors="ignore")
            logger.info("Fetched runbook content via REST API: '%s'", runbook_name)
            return content

        logger.error(
            "Failed REST content fetch for '%s': %s - %s",
            runbook_name,
            response.status_code,
            response.text
        )
        return None

    except Exception as exc:
        logger.exception("Exception while fetching runbook content via REST: %s", exc)
        return None


# ###############  FUNCTION: create_new_runbook ###############
def create_new_runbook(runbook_name: str, system_name: str) -> None:
    """
    Creates a new Azure Automation runbook by duplicating content from an existing runbook.
    If neither draft nor published content exists, an auto-generated placeholder script is used.

    Args:
        runbook_name (str): The existing runbook to copy.
        system_name (str): System identifier appended to the new runbook name.

    Returns:
        None
    """
    credential = DefaultAzureCredential()
    client = AutomationClient(credential, config.SUBSCRIPTION_ID)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    os.makedirs("generated_runbooks", exist_ok=True)

    new_runbook_name = f"{runbook_name}_{system_name}_{timestamp}"
    file_name = f"{new_runbook_name}.ps1"
    file_path = os.path.join("generated_runbooks", file_name)

    logger.info("Retrieving script content for source runbook: '%s'", runbook_name)

    source_script = None

    # --------------------------------------------------------------------------
    # Attempt 1: Retrieve draft version
    # --------------------------------------------------------------------------
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

        logger.info("Draft content retrieved successfully for '%s'", runbook_name)

    except Exception as exc:
        logger.warning("Draft version unavailable for '%s': %s", runbook_name, exc)

    # --------------------------------------------------------------------------
    # Attempt 2: Retrieve published version
    # --------------------------------------------------------------------------
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

            logger.info("Published content retrieved successfully for '%s'", runbook_name)

        except Exception as exc:
            logger.warning("Published content unavailable for '%s': %s", runbook_name, exc)
            logger.info("Attempting REST API fallback...")
            source_script = get_source_content(runbook_name)

    # --------------------------------------------------------------------------
    # Fallback: Generate empty placeholder script
    # --------------------------------------------------------------------------
    if not source_script:
        source_script = (
            f"# Auto-generated Runbook\n"
            f"# Name: {file_name}\n"
            f"# System: {system_name}\n"
            f"# Created: {timestamp}\n\n"
            f"Write-Output 'Running {file_name}'\n"
        )
        logger.info("No source content found. Using placeholder script.")

    # --------------------------------------------------------------------------
    # Write script content locally
    # --------------------------------------------------------------------------
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(source_script)

    logger.info("Runbook script saved locally at: %s", file_path)

    # --------------------------------------------------------------------------
    # Step 1: Create a new runbook in Azure Automation
    # --------------------------------------------------------------------------
    try:
        created_runbook = client.runbook.create_or_update(
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

        logger.info("Runbook created in Azure Automation: %s", created_runbook.name)

    except Exception as exc:
        logger.error("Failed to create new runbook '%s': %s", new_runbook_name, exc)
        return

    # --------------------------------------------------------------------------
    # Step 2: Upload draft content
    # --------------------------------------------------------------------------
    try:
        poller = client.runbook_draft.begin_replace_content(
            resource_group_name=config.RESOURCE_GROUP,
            automation_account_name=config.AUTOMATION_ACCOUNT,
            runbook_name=new_runbook_name,
            runbook_content=source_script
        )
        poller.result()

        logger.info("Runbook content uploaded successfully: %s", file_name)

    except Exception as exc:
        logger.error("Failed to upload content for runbook '%s': %s", new_runbook_name, exc)

    # --------------------------------------------------------------------------
    # Step 3: Publish runbook
    # --------------------------------------------------------------------------
    try:
        client.runbook.begin_publish(
            resource_group_name=config.RESOURCE_GROUP,
            automation_account_name=config.AUTOMATION_ACCOUNT,
            runbook_name=new_runbook_name
        ).result()

        logger.info("Runbook published successfully: %s", file_name)

    except Exception as exc:
        logger.error("Failed to publish runbook '%s': %s", new_runbook_name, exc)

 # --------------------------------------------------------------------------
    # Step 4: EXECUTE RUNBOOK ON AZURE (NEWLY ADDED)
    # --------------------------------------------------------------------------
    try:
        job_name = f"job_{new_runbook_name}_{timestamp}"

        logger.info("Starting runbook execution: %s", new_runbook_name)

        job = client.job.create(
            resource_group_name=config.RESOURCE_GROUP,
            automation_account_name=config.AUTOMATION_ACCOUNT,
            job_name=job_name,
            parameters={
                "properties": {
                    "runbook": {"name": new_runbook_name},
                    "parameters": {},  # no params passed
                }
            }
        )

        logger.info("Runbook execution started successfully: Job ID = %s", job.id)

    except Exception as exc:
        logger.error("Failed to execute runbook '%s': %s", new_runbook_name, exc)

# ###############  FUNCTION: get_output_by_runbook_name ###############
def get_runbook_output_by_job_id(job_id: str) -> str:
    """
    Fetch Azure Automation runbook output directly using JOB ID.
    This always returns the same output shown in the Azure portal.
    """
    try:
        credential = DefaultAzureCredential()
        token = credential.get_token("https://management.azure.com/.default").token
        
        output_url = (
            f"https://management.azure.com/subscriptions/{config.SUBSCRIPTION_ID}"
            f"/resourceGroups/{config.RESOURCE_GROUP}"
            f"/providers/Microsoft.Automation/automationAccounts/{config.AUTOMATION_ACCOUNT}"
            f"/jobs/{job_id}/output?api-version=2021-06-22"
        )

        headers = {"Authorization": f"Bearer {token}"}

        resp = requests.get(output_url, headers=headers)

        if resp.status_code != 200:
            raise Exception(f"Failed to fetch job output: {resp.text}")

        return resp.text

    except Exception as exc:
        logger.exception("Error fetching job output: %s", exc)
        raise

if __name__ == "__main__":
    job_id = input("Enter Azure Automation Job ID: ")

    try:
        out = get_runbook_output_by_job_id(job_id)
        print("\n===== OUTPUT START =====\n")
        print(out)
        print("\n===== OUTPUT END =====\n")
    except Exception as e:
        print("ERROR:", e)

python utils.py
2025-11-20 18:47:58,359 [INFO] config - Successfully authenticated with Akeyless.
2025-11-20 18:47:58,638 [INFO] config - Successfully retrieved and parsed Akeyless secrets.
Enter Azure Automation Job ID: b50fffda-711c-4678-9471-4e7e03069019
2025-11-20 18:48:09,919 [ERROR] automation_helpers - Error fetching job output: Failed to fetch job output: {"error":{"code":"NoRegisteredProviderFound","message":"No registered resource provider found for location 'swedencentral' and API version '2021-06-22' for type 'automationAccounts/jobs'. The supported api-versions are '2015-01-01-preview, 2015-10-31, 2017-05-15-preview, 2018-01-15, 2018-06-30, 2019-06-01, 2020-01-13-preview, 2022-08-08, 2023-05-15-preview, 2023-11-01, 2024-10-23'. The supported locations are 'japaneast, eastus2, westeurope, southafricanorth, ukwest, switzerlandnorth, brazilsoutheast, norwayeast, germanywestcentral, uaenorth, switzerlandwest, japanwest, uaecentral, australiacentral2, southindia, francesouth, norwaywest, westus3, koreasouth, swedencentral, southeastasia, southcentralus, northcentralus, eastasia, centralus, westus, australiacentral, australiaeast, koreacentral, eastus, westus2, brazilsouth, uksouth, westcentralus, northeurope, canadacentral, australiasoutheast, centralindia, francecentral, jioindiawest, jioindiacentral, qatarcentral, southafricawest, polandcentral, israelcentral, germanynorth, italynorth, canadaeast, spaincentral'."}}       
Traceback (most recent call last):
  File "F:\Kousik\helpdesk_assistant\utils.py", line 285, in get_runbook_output_by_job_id
    raise Exception(f"Failed to fetch job output: {resp.text}")
Exception: Failed to fetch job output: {"error":{"code":"NoRegisteredProviderFound","message":"No registered resource provider found for location 'swedencentral' and API version '2021-06-22' for type 'automationAccounts/jobs'. The supported api-versions are '2015-01-01-preview, 2015-10-31, 2017-05-15-preview, 2018-01-15, 2018-06-30, 2019-06-01, 2020-01-13-preview, 2022-08-08, 2023-05-15-preview, 2023-11-01, 2024-10-23'. The supported locations are 'japaneast, eastus2, westeurope, southafricanorth, ukwest, switzerlandnorth, brazilsoutheast, norwayeast, germanywestcentral, uaenorth, switzerlandwest, japanwest, uaecentral, australiacentral2, southindia, francesouth, norwaywest, westus3, koreasouth, swedencentral, southeastasia, southcentralus, northcentralus, eastasia, centralus, westus, australiacentral, australiaeast, koreacentral, eastus, westus2, brazilsouth, uksouth, westcentralus, northeurope, canadacentral, australiasoutheast, centralindia, francecentral, jioindiawest, jioindiacentral, qatarcentral, southafricawest, polandcentral, israelcentral, germanynorth, italynorth, canadaeast, spaincentral'."}}
ERROR: Failed to fetch job output: {"error":{"code":"NoRegisteredProviderFound","message":"No registered resource provider found for location 'swedencentral' and API version '2021-06-22' for type 'automationAccounts/jobs'. The supported api-versions are '2015-01-01-preview, 2015-10-31, 2017-05-15-preview, 2018-01-15, 2018-06-30, 2019-06-01, 2020-01-13-preview, 2022-08-08, 2023-05-15-preview, 2023-11-01, 2024-10-23'. The supported locations are 'japaneast, eastus2, westeurope, southafricanorth, ukwest, switzerlandnorth, brazilsoutheast, norwayeast, germanywestcentral, uaenorth, switzerlandwest, japanwest, uaecentral, australiacentral2, southindia, francesouth, norwaywest, westus3, koreasouth, swedencentral, southeastasia, southcentralus, northcentralus, eastasia, centralus, westus, australiacentral, australiaeast, koreacentral, eastus, westus2, brazilsouth, uksouth, westcentralus, northeurope, canadacentral, australiasoutheast, centralindia, francecentral, jioindiawest, jioindiacentral, qatarcentral, southafricawest, polandcentral, israelcentral, germanynorth, italynorth, canadaeast, spaincentral'."}}
