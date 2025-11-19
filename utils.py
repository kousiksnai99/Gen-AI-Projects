#################################################################################################
## utils.py - automation helpers (instrumented for Time_Logger)
#################################################################################################

import os
import logging
import requests
from datetime import datetime

from azure.identity import DefaultAzureCredential
from azure.mgmt.automation import AutomationClient

import config


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
)
logger = logging.getLogger("automation_helpers")


def _now_isoutc() -> str:
    return datetime.utcnow().isoformat(timespec="microseconds") + "Z"


def get_source_content(runbook_name: str) -> str | None:
    """
    Unchanged; REST fallback to fetch runbook content.
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


def create_new_runbook(runbook_name: str, system_name: str, time_logger: dict | None = None) -> None:
    """
    Create new runbook (duplicate) and populate automation & cloning timestamps
    into provided time_logger dict if present.
    """
    if time_logger is None:
        time_logger = {}

    time_logger.setdefault("Cloning_Start", _now_isoutc())

    try:
        time_logger.setdefault("Automation_Start", _now_isoutc())

        credential = DefaultAzureCredential()
        client = AutomationClient(credential, config.SUBSCRIPTION_ID)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        os.makedirs("generated_runbooks", exist_ok=True)

        new_runbook_name = f"{runbook_name}_{system_name}_{timestamp}"
        file_name = f"{new_runbook_name}.ps1"
        file_path = os.path.join("generated_runbooks", file_name)

        logger.info("Retrieving script content for source runbook: '%s'", runbook_name)

        source_script = None

        # Attempt 1: draft
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
            logger.info("Draft content retrieved for '%s'", runbook_name)
        except Exception:
            logger.debug("No draft content for '%s'", runbook_name)

        # Attempt 2: published
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
                logger.info("Published content retrieved for '%s'", runbook_name)
            except Exception:
                logger.debug("No published content for '%s', trying REST fallback", runbook_name)
                source_script = get_source_content(runbook_name)

        if not source_script:
            source_script = (
                f"# Auto-generated Runbook\n"
                f"# Name: {file_name}\n"
                f"# System: {system_name}\n"
                f"# Created: {timestamp}\n\n"
                f"Write-Output 'Running {file_name}'\n"
            )
            logger.info("Using placeholder script for '%s'", runbook_name)

        # Write file locally
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(source_script)
        logger.info("Runbook written locally at %s", file_path)

        # Create runbook in Azure Automation
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

        # Upload content to draft
        poller = client.runbook_draft.begin_replace_content(
            resource_group_name=config.RESOURCE_GROUP,
            automation_account_name=config.AUTOMATION_ACCOUNT,
            runbook_name=new_runbook_name,
            runbook_content=source_script
        )
        poller.result()
        logger.info("Runbook content uploaded: %s", file_name)

        # Publish runbook
        client.runbook.begin_publish(
            resource_group_name=config.RESOURCE_GROUP,
            automation_account_name=config.AUTOMATION_ACCOUNT,
            runbook_name=new_runbook_name
        ).result()
        logger.info("Runbook published: %s", file_name)

        time_logger["Cloning_End"] = _now_isoutc()
        time_logger["Automation_End"] = _now_isoutc()

    except Exception as exc:
        logger.exception("Failed creating/publishing runbook '%s': %s", runbook_name, exc)
        # Ensure we set end timestamps even on error
        time_logger.setdefault("Cloning_End", _now_isoutc())
        time_logger.setdefault("Automation_End", _now_isoutc())
