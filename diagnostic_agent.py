#################################################################################################
## DIAGNOSTIC AGENT WITH FULL TIME LOGGER
#################################################################################################

import logging
import time
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential, AzureCliCredential
from azure.ai.agents.models import ListSortOrder
from azure.mgmt.automation import AutomationClient
import config

logger = logging.getLogger("diagnostic_agent")

default_credential = DefaultAzureCredential()
automation_client = AutomationClient(default_credential, config.SUBSCRIPTION_ID)

ai_project_client = AIProjectClient(
    credential=AzureCliCredential(),
    endpoint=config.MODEL_ENDPOINT
)

diagnostic_agent = ai_project_client.agents.get_agent(config.DIAGNOSTIC_AGENT_ID)


def _start(tlog: dict, key: str):
    tlog[key] = {"start": time.time()}


def _end(tlog: dict, key: str):
    tlog[key]["end"] = time.time()
    tlog[key]["duration_sec"] = round(tlog[key]["end"] - tlog[key]["start"], 4)


def process_issue(issue: str):
    """
    Diagnostic Agent with Detailed Internal Time Logger
    """
    time_logger = {}

    try:
        logger.info("Processing diagnostic issue: %s", issue)

        # Step 1: Create thread
        _start(time_logger, "Thread_Create")
        thread = ai_project_client.agents.threads.create()
        _end(time_logger, "Thread_Create")

        # Step 2: Send user message
        _start(time_logger, "Message_Post")
        ai_project_client.agents.messages.create(
            thread_id=thread.id,
            role="user",
            content=issue
        )
        _end(time_logger, "Message_Post")

        # Step 3: Run AI agent
        _start(time_logger, "Run_Create_Process")
        run = ai_project_client.agents.runs.create_and_process(
            thread_id=thread.id,
            agent_id=diagnostic_agent.id
        )
        _end(time_logger, "Run_Create_Process")

        if run.status == "failed":
            return None, time_logger

        # Step 4: Fetch messages
        _start(time_logger, "Fetch_Messages")
        messages = ai_project_client.agents.messages.list(
            thread_id=thread.id,
            order=ListSortOrder.ASCENDING
        )
        _end(time_logger, "Fetch_Messages")

        # Step 5: Extract runbook
        _start(time_logger, "Runbook_Extract")
        runbook_name = None
        for message in messages:
            if message.text_messages:
                runbook_name = message.text_messages[-1].text.value
        _end(time_logger, "Runbook_Extract")

        return runbook_name, time_logger

    except Exception as exc:
        logger.exception("Error: %s", exc)
        return None, time_logger
