################################################################################################# 
## Project name : Agentic AI POC                                                                #
## Business owner , Team : Data and AIA                                                         #
## Notebook Author , Team: POC Team                                                             #
## Date: 2025-10-29                                                                              #
## Purpose of Notebook: Utility helpers for runbook retrieval, validation and creation.         #
## Connections: Called by main.py to perform create_new_runbook, and diagnostic/troubleshooting #
## Notes: This file intentionally does NOT add any external integrations (KeyVault/EventHub).    #
#################################################################################################

from __future__ import annotations

###############  IMPORT PACKAGES  ###############
import os
from datetime import datetime
from typing import Optional

from logger_config import get_logger

from azure.identity import DefaultAzureCredential
from azure.mgmt.automation import AutomationClient
import requests

import config
##################################################

logger = get_logger(__name__)

# ###############  SETTINGS & CONSTANTS ###############
GENERATED_RUNBOOKS_DIR = os.getenv("GENERATED_RUNBOOKS_DIR", "generated_runbooks")
RUNBOOK_API_VERSION = os.getenv("AZURE_RUNBOOK_API_VERSION", "2024-10-23")
# #####################################################

# Ensure output directory exists
os.makedirs(GENERATED_RUNBOOKS_DIR, exist_ok=True)


def validate_runbook_name(candidate_name: str) -> bool:
    """
    Basic validation for runbook names to detect obviously invalid results from agents.
    Rules (best-effort):
      - non-empty
      - length limit
      - allowed characters (letters, numbers, underscore, dash)
    This does NOT enforce Azure naming rules exactly; it is a simple guardrail.
    """
    if not candidate_name or not isinstance(candidate_name, str):
        return False
    trimmed = candidate_name.strip()
    if len(trimmed) == 0 or len(trimmed) > 200:
        return False
    # allow letters, numbers, underscores, dashes, and spaces (space trimmed)
    for ch in trimmed:
        if not (ch.isalnum() or ch in ("_", "-", " ")):
            return False
    return True


def get_source_content_via_rest(runbook_name: str) -> Optional[str]:
    """
    Fetch runbook content directly from Azure REST API fallback.
    This function mirrors previous get_source_content behavior and will use
    DefaultAzureCredential to obtain tokens.
    """
    credential = DefaultAzureCredential()
    token = credential.get_token("https://management.azure.com/.default").token

    url = (
        f"https://management.azure.com/subscriptions/{config.SUBSCRIPTION_ID}"
        f"/resourceGroups/{config.RESOURCE_GROUP}"
        f"/providers/Microsoft.Automation/automationAccounts/{config.AUTOMATION_ACCOUNT}"
        f"/runbooks/{runbook_name}/content?api-version={RUNBOOK_API_VERSION}"
    )

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/octet-stream"
    }

    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        runbook_content = response.content.decode("utf-8", errors="ignore")
        logger.info("Successfully fetched content for runbook '%s' using REST fallback", runbook_name)
        return runbook_content
    else:
        logger.warning("Failed to fetch content for %s via REST fallback: %s - %s", runbook_name, response.status_code, response.text)
        return None


def create_new_runbook(runbook_name: str, system_name: str) -> None:
    """
    Create a new runbook in Azure Automation by copying from an existing runbook.

    Steps:
      1. Attempt to read the draft content via AutomationClient.runbook_draft.get_content.
      2. If that fails, attempt to read published content via AutomationClient.runbook.get_content.
      3. If both fail, attempt REST fallback (get_source_content_via_rest).
      4. If still nothing, generate a minimal runbook stub locally.
      5. Create new runbook with a timestamped name under generated_runbooks directory and push to Azure Automation.
    """
    if not runbook_name:
        logger.error("create_new_runbook called with empty runbook_name.")
        return

    if not validate_runbook_name(runbook_name):
        logger.warning("Runbook name '%s' did not pass validation; continuing but recording issue.", runbook_name)

    credential = DefaultAzureCredential()
    client = AutomationClient(credential, config.SUBSCRIPTION_ID)
    time_stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    new_runbook_name = f"{runbook_name}_{system_name}_{time_stamp}"
    file_name = f"{new_runbook_name}.ps1"
    file_path = os.path.join(GENERATED_RUNBOOKS_DIR, file_name)

    logger.info("Retrieving script from existing runbook: %s", runbook_name)
    source_script: Optional[str] = None

    # Try draft content
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
        logger.info("Successfully retrieved draft content from runbook: %s", runbook_name)
    except Exception as exc:
        logger.debug("No draft version found or error reading draft for runbook %s: %s", runbook_name, exc)

    # Try published content if draft didn't work
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
            logger.info("Successfully retrieved published content from runbook: %s", runbook_name)
        except Exception as exc:
            logger.debug("Could not fetch published runbook content for %s: %s", runbook_name, exc)
            logger.info("Trying to fetch using REST API fallback method for runbook: %s", runbook_name)
            source_script = get_source_content_via_rest(runbook_name)

    # If still no script, generate a minimal stub
    if not source_script:
        source_script = (
            f"# Auto-generated Runbook\n# Name: {file_name}\n# System: {system_name}\n"
            f"# Created: {time_stamp}\n\nWrite-Output 'Running {file_name}'\n"
        )
        logger.warning("No source script could be fetched; creating minimal stub for %s", new_runbook_name)

    # Write to local file (so there's a record even if Azure operations fail)
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(source_script)
        logger.info("Runbook file created locally: %s", file_path)
    except Exception as exc:
        logger.exception("Failed to write runbook file %s: %s", file_path, exc)

    # Create runbook in Azure Automation and upload content; if errors occur, log them
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
        logger.info("Runbook created in Azure Automation: %s", getattr(runbook, "name", new_runbook_name))
    except Exception as exc:
        logger.exception("Error creating runbook in Azure Automation: %s", exc)
        # Do not raise to preserve previous behavior; calling code expects create_new_runbook to be non-fatal

    # Replace draft content
    try:
        poller = client.runbook_draft.begin_replace_content(
            resource_group_name=config.RESOURCE_GROUP,
            automation_account_name=config.AUTOMATION_ACCOUNT,
            runbook_name=new_runbook_name,
            runbook_content=source_script
        )
        poller.result()
        logger.info("Runbook content uploaded successfully for: %s", file_name)
    except Exception as exc:
        logger.exception("Error replacing runbook content for %s: %s", new_runbook_name, exc)

    # Publish runbook
    try:
        client.runbook.begin_publish(
            resource_group_name=config.RESOURCE_GROUP,
            automation_account_name=config.AUTOMATION_ACCOUNT,
            runbook_name=new_runbook_name
        ).result()
        logger.info("Runbook published successfully: %s", file_name)
    except Exception as exc:
        logger.exception("Error publishing runbook: %s", exc)
