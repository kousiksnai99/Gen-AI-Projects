#################################################################################################
## Project name : Agentic AI POC - Utilities                                                  #
## Business owner, Team : Data and AIA                                                         #
## Notebook Author, Team: POC Team                                                            #
## Date: 2025-11-12                                                                           #
## Purpose of File: Helpers for runbook management, content retrieval, telemetry, and logging. ##
## Connections: Used by main.py and agents.                                                    #
#################################################################################################

###############  IMPORT PACKAGES  ###############
from datetime import datetime
import os
import logging
from azure.identity import DefaultAzureCredential
from azure.mgmt.automation import AutomationClient
import requests
import config

# Optional Event Hub telemetry
try:
    from azure.eventhub import EventHubProducerClient, EventData
except Exception:
    EventHubProducerClient = None
    EventData = None

###############  LOGGER  ###############
logger = logging.getLogger("utils")

# Ensure a default credential is available (prefer managed identity)
try:
    _credential = DefaultAzureCredential()
    logger.info("DefaultAzureCredential initialized for utils.")
except Exception as e:
    logger.exception("Could not initialize DefaultAzureCredential: %s", e)
    _credential = None

###############  CONSTANTS  ###############
RUNBOOK_API_VERSION = "2024-10-23"

###############  HELPERS: EventHub telemetry (optional)  ###############
def send_telemetry_event(payload: dict):
    """
    Send a telemetry event to Event Hub if configured. Non-blocking best-effort.
    payload: plain JSON-serializable dict
    """
    try:
        if not config.EVENTHUB_CONNECTION_STRING or not config.EVENTHUB_NAME:
            logger.debug("EventHub not configured; skipping telemetry send.")
            return

        if EventHubProducerClient is None:
            logger.debug("azure-eventhub package not available; skipping telemetry send.")
            return

        producer = EventHubProducerClient.from_connection_string(conn_str=config.EVENTHUB_CONNECTION_STRING, eventhub_name=config.EVENTHUB_NAME)
        event = EventData(str(payload))
        with producer:
            producer.send_batch([event])
        logger.info("Telemetry event sent to EventHub: %s", payload)
    except Exception as e:
        # Telemetry failures must not break main flows
        logger.exception("Failed to send telemetry event: %s", e)

###############  HELPER: get_source_content via REST fallback  ###############
def get_source_content(runbook_name: str):
    """
    Fetch runbook content directly from Azure REST API (draft or published).
    Returns runbook content string or None.
    """
    if not _credential:
        logger.warning("No credential available to call management REST API.")
        return None

    try:
        token = _credential.get_token("https://management.azure.com/.default").token
    except Exception as e:
        logger.exception("Failed to acquire management token: %s", e)
        return None

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

    try:
        response = requests.get(url, headers=headers, timeout=30)
        if response.status_code == 200:
            runbook_content = response.content.decode("utf-8", errors="ignore")
            logger.info("Successfully fetched content for %s via REST API", runbook_name)
            return runbook_content
        else:
            logger.warning("Failed to fetch content for %s: %s - %s", runbook_name, response.status_code, response.text)
            return None
    except Exception as e:
        logger.exception("Exception while fetching runbook content via REST: %s", e)
        return None

###############  PUBLIC: create_new_runbook  ###############
def create_new_runbook(runbook_name: str, system_name: str):
    """
    Create a new runbook in the Azure Automation Account by copying content from an existing runbook.
    This preserves the original behaviour but adds robust logging, optional REST fallback, and local file creation.
    """
    if not _credential:
        logger.warning("No credential available - create_new_runbook cannot proceed.")
        return

    client = AutomationClient(_credential, config.SUBSCRIPTION_ID)
    time_stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    os.makedirs("generated_runbooks", exist_ok=True)

    new_runbook_name = f"{runbook_name}_{system_name}_{time_stamp}"
    file_name = f"{new_runbook_name}.ps1"
    file_path = os.path.join("generated_runbooks", file_name)

    logger.info("Retrieving script from existing runbook: %s", runbook_name)
    source_script = None

    # Try to read draft content first
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
    except Exception as e:
        logger.debug("No draft version found or error reading draft: %s", e)

    # Try published runbook content
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
        except Exception as e:
            logger.debug("Could not fetch published runbook content: %s", e)
            logger.info("Trying REST API fallback to fetch runbook content.")
            source_script = get_source_content(runbook_name)

    # If still not available, generate a minimal runbook scaffold
    if not source_script:
        source_script = (
            f"# Auto-generated Runbook\n# Name: {file_name}\n# System: {system_name}\n"
            f"# Created: {time_stamp}\n\nWrite-Output 'Running {file_name}'\n"
        )
        logger.warning("Using auto-generated fallback runbook content for %s", runbook_name)

    # Save to local file for auditing / packaging
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(source_script)
        logger.info("Runbook file created locally: %s", file_path)
    except Exception as e:
        logger.exception("Failed to write local runbook file: %s", e)

    # Create runbook record in Azure Automation
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
    except Exception as e:
        logger.exception("Error creating runbook in Azure Automation: %s", e)
        return

    # Replace content using the draft API and publish
    try:
        poller = client.runbook_draft.begin_replace_content(
            resource_group_name=config.RESOURCE_GROUP,
            automation_account_name=config.AUTOMATION_ACCOUNT,
            runbook_name=new_runbook_name,
            runbook_content=source_script
        )
        poller.result()
        logger.info("Runbook content uploaded successfully for: %s", file_name)
    except Exception as e:
        logger.exception("Error replacing runbook content: %s", e)

    try:
        client.runbook.begin_publish(
            resource_group_name=config.RESOURCE_GROUP,
            automation_account_name=config.AUTOMATION_ACCOUNT,
            runbook_name=new_runbook_name
        ).result()
        logger.info("Runbook published successfully: %s", file_name)
    except Exception as e:
        logger.exception("Error publishing runbook: %s", e)

    # Send telemetry event
    send_telemetry_event({"event": "runbook_created", "runbook": new_runbook_name, "system": system_name})

###############  DATA VALIDATION (BASIC)  ###############
def validate_runbook_metadata(runbook_content: str):
    """
    Basic placeholder data validation for runbook content.
    Extend this to assert expected parameters, module imports, or schema.
    Returns True if validation passes, False otherwise.
    """
    if not runbook_content:
        logger.warning("validate_runbook_metadata: empty content")
        return False
    # Example check: ensure the runbook contains a descriptive header and at least one Write-Output
    header_present = "#" in runbook_content[:200]
    has_write_output = "Write-Output" in runbook_content or "Write-Host" in runbook_content
    valid = header_present and has_write_output
    logger.debug("validate_runbook_metadata -> header_present=%s, has_write_output=%s, valid=%s",
                 header_present, has_write_output, valid)
    return valid
