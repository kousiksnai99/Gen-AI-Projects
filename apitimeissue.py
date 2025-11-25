##################################################################################### 
## Project name : Agentic AI POC                                                    #
## Business owner , Team : Data and AIA                                             #
## Notebook Author , Team: POC Team                                                 #
## Date: 17th Nov 2025                                                              #
## Puprose of Notebook:                                                             #
##  HTTP-triggered Azure Function that:                                             #
##      1. Recieves and issue description from a caller [Service Desk/App].         #
##      2. Uses Azure AI Foundry diagnostic agent to resolve the issue to an        #
##         Azure Automation Runbook.                                                #
##      3. Clones the runbook with additional metadata [eg. target machine] and     #
##         publish it for execution.                                                #
## Code 
#####################################################################################

# # Load all the libraries
import json
import logging
import os
import uuid
from datetime import datetime
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

import azure.functions as func
from azure.eventhub import EventHubProducerClient, EventData
from pydantic import BaseModel, ValidationError

# Auth / SDKs
from azure.identity import DefaultAzureCredential
from azure.mgmt.automation import AutomationClient


# Optional: Azure AI Projects
from azure.ai.projects import AIProjectClient
from azure.ai.agents.models import ListSortOrder
import requests

# Access the storage account
from azure.storage.blob import BlobServiceClient, BlobClient, ContainerClient
from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError

from dotenv import load_dotenv
load_dotenv()


# Akeyless [Fetch Secrets]
import akeyless
from akeyless_cloud_id import CloudId


#=============================Logging Setup========================================================
# Azure function configures root logger but we are ensuring the level.
logging.getLogger().setLevel(logging.INFO)

#=============================Data Class Module==========================================================
@dataclass
class AutomationConfig:
    """Configuration required for Azure Automation interactions."""
    subscription_id:str
    resource_group: str
    automation_account: str
    location: str

@dataclass
class FoundryConfig:
    """Configuration required for Azure AI Foundry interactions."""
    endpoint:str
    diagnostic_agent_id: str
    troubleshoot_agent_id: str
    deployment: str
    api_version: str

@dataclass
class AppConfig:
    """Configuration object for the function."""
    environment:str
    automation: AutomationConfig
    foundry: FoundryConfig

#=========================================Helpers: Setting Akeyless===========================================
def read_akeyless_dicts():
    """ FETCH ID AND SECRET FROM AKEYLESS DICTIONARY
        - AGENT VARIABLES
        - AUTOMATION VARIABLES
        All the secrets are stored in akeyless
    """
    logging.info("Reading Condiguration dictionaries from Akeyless.")
    
    Automation_Variable= {
        "AZ_SUBSCRIPTION_ID": "4c85c528-9da9-48ac-a5c3-41bd351728eb",
        "AZ_RESOURCE_GROUP": "rg-fbntf-ais-swce-poc",
        "AZ_AUTOMATION_ACCOUNT": "aa-mbfin-ais-swce-poc",
        "LOCATION":"Sweden Central"
        }
    Foundry_Variable={
        "Endpoint": "https://aifoundry-rjteh-ais-swce-poc.services.ai.azure.com/api/projects/aifp-uqqnf-ais-swce-poc",
        "Model_Name": "gpt-5-mini",
        "Deployment": "ITOA-Service_Desk-Agentic_AI_POC-gpt-5-mini",
        "API_Version": "2024-12-01-preview",
        "DIAGNOSTIC_Agent_ID": "asst_MxWLoHuCHSwnPxyZfzUe2EOb",
        "TROUBLESHOOT_Agent_ID": "asst_fP3eyPFbOQGjFvH7m909Kdi6"}
    logging.info("Akeyless dictionaries loaded successfully.")
    return Foundry_Variable, Automation_Variable

#=========================================Helpers: Loading Configuration===========================================
def load_config_from_akeyless() ->Tuple[AppConfig, Dict[str, Any], Dict[str, Any]]:
    """
    Build AppConfig from Akeyless dictionaries and environment.
    """
    app_env= "dev"
    foundry_dict, automation_dict= read_akeyless_dicts()
    automation_cfg =AutomationConfig(
        subscription_id= automation_dict['AZ_SUBSCRIPTION_ID'],
        resource_group = automation_dict['AZ_RESOURCE_GROUP'],
        automation_account = automation_dict['AZ_AUTOMATION_ACCOUNT'],
        location = automation_dict['LOCATION']
        )
    foundry_cfg = FoundryConfig(
        endpoint= foundry_dict['Endpoint'],
        diagnostic_agent_id= foundry_dict['DIAGNOSTIC_Agent_ID'],
        troubleshoot_agent_id= foundry_dict['TROUBLESHOOT_Agent_ID'],
        deployment= foundry_dict['Deployment'],
        api_version= foundry_dict['API_Version']
        )
    config = AppConfig(environment= app_env, automation = automation_cfg, foundry = foundry_cfg)
    return config, foundry_dict, automation_dict

#==============================================Utilities========================================================

def json_response(payload: Dict[str, Any], status: int =200) ->func.HttpResponse:
    """Returns a JSON-formatted HTTP response within consistent headers."""
    return func.HttpResponse(
        body = json.dumps(payload),
        status_code= status,
        mimetype ="application/json",
        )

def validate_request_body(body: Dict[str, Any]) -> Tuple [str, bool, str]:
    """
    Validate and parse incoming HTTP JSON payload.
    Expected Schema:
    {
        "issue" : "string, required",
        "execute": true/false, optional, default= true,
        "target_machine" : "string, required"  
    }
    """
    issue = body.get("issue")
    if not isinstance(issue, str) or not issue.strip():
        raise ValueError("Field 'issue' is required and must be a non-empty string.")
    
    execute = bool(body.get("execute", True))
    target_machine = body.get("target_machine", "").strip() or "UNSPECIFIED"
    if not isinstance(target_machine, str):
        raise ValueError("Field 'target_machine' is required and must be a non-empty string.")

    return issue.strip(), execute, target_machine

def get_default_credential() ->DefaultAzureCredential:
    """ Create a Default Azure Credentialinstance suitable for functionapps."""
    return DefaultAzureCredential(
        exclude_interactive_browser_credential=True,
        exclude_visual_studio_code_credential=True,
        exclude_shared_token_cache_credential=True,
        exclude_powershell_credential=True)


#============================================Event Hub Logging==========================================
class EventHubLogger:
    """
    Simple wrapper for sending JSON events to Azure Event Hub using AAD
    authentication. No connection string is user.
    """
    def __init__(self, automation_dict: Dict[str, Any], credential: DefaultAzureCredential):
        namespace ="ehn-hrmqc-ais-swce-poc"
        name="evh-okvkc-ais-swce-poc"

        if not namespace or not name:
            logging.warning(
                "Event Hub namespace/name not configured. Event will not be sent."
                )
            self.producer: Optional[EventHubProducerClient] = None
            return
        
        try:
            self.producer= EventHubProducerClient(
                fully_qualified_namespace = namespace,
                eventhub_name = name,
                credential= credential
            )
            logging.info("Event Hub Logger initialised for hub '%s'.", name)
        except Exception:
            logging.exception("Failed to initialise Eventhub producer client.")
            self.producer=None
    
    def send_event(self, event: Dict[str, Any]) -> None:
        """
        Send a single JSON event to Event Hub. Failure is looged but doesn't
        break the main flow.
        """
        if not self.producer:
            return
        
        try:
            paylod = json.dumps(event)
            event_data =EventData(payload)
            with self.producer:
                batch = self.producer.create_batch()
                batch.add(event_data)
                self.producer.send_batch(batch)
            logging.info("Event sent to Event Hub: %s", event.get("event_type"))
        except Exception:
            logging.exception("Failed to send event to eventhub.")

#==============================================AZURE AUTOMATION===================================
class AzureautomationService:
    """Wrapper around azure automation operations (Runbook CRUD, REST content)."""

    def __init__(self, config: AutomationConfig, credential: DefaultAzureCredential):
        self.config=config
        self.credential=credential
        self.client = AutomationClient(credential, config.subscription_id)

    def get_rest_token(self) -> str:
        """Acquire a token for Azure Resource Manager using managed identity."""
        token = self.credential.get_token("https://management.azure.com/.default").token
        return token

    def fetch_runbook_content(self, runbook_name: str) -> Optional[str]:
        """
        Fetch runbook content directly from Azure via REST API.
        Returns the runbook powershell script as string or None if not found.
        """
        token=self.get_rest_token()
        url = (
            f"https://management.azure.com/subscriptions/{self.config.subscription_id}"
            f"/resourceGroups/{self.config.resource_group}"
            f"/providers/Microsoft.Automation/automationAccounts/{self.config.automation_account}"
            f"/runbooks/{runbook_name}/content?api-version=2024-10-23"
            )
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/octet-stream"
            }
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            logging.info("Fetched content for runbook '%s'.", runbook_name)
            return response.content.decode("utf-8", errors="ignore")
        logging.warning(
            "Failed to fetch content for runbook '%s'. status: %s, Bodr: %s",
            runbook_name,
            response.status_code,
            response.text,
            )
        return None

    def create_or_update_runbook(self, runbook_name: str, runbook_content: str) -> None:
        """
        Creates Runbook [Powershell] and uploads the content, then publishes it.
        STEPS:
            1. Ensure that meta data exists [create_or_update].
            2. Upload the draft content.
            3. Publishes the Runbook.
            4. Run the Runbook
        """
        logging.info("Creating or updating runbook '%s'.", runbook_name)

        # 1. Create or Update Meta Data
        runbook = self.client.runbook.create_or_update(
            resource_group_name = self.config.resource_group,
            automation_account_name= self.config.automation_account,
            runbook_name = runbook_name,
            parameters={
                "location": self.config.location,
                "properties" : {
                    "runbookType": "PowerShell",
                    "logProgress": True,
                    "logVerbose": True,
                }
            }
        )
        logging.info(
            "Runbook metadata ensured for '%s'.Resource ID: %s",
            runbook_name,
            runbook.id
            )
      
        # 2. Upload Content to Draft Runbook
        draft_poller = self.client.runbook_draft.begin_replace_content(
            resource_group_name= self.config.resource_group,
            automation_account_name=self.config.automation_account,
            runbook_name = runbook_name,
            runbook_content = runbook_content
        )

        draft_poller.result()
        logging.info("Runbook draft content uploaded for'%s'", runbook_name)

        # 3. Publish the script into automation account
        publish_poller=self.client.runbook.begin_publish(
            resource_group_name=self.config.resource_group,
            automation_account_name=self.config.automation_account,
            runbook_name = runbook_name,
        )
        publish_poller.result()
        logging.info("Runbook '%s' published successfully.", runbook_name)

        # 4. Execute the script in user machine via SCCM
        logging.info("Starting runbook execution on Hybrid Worker Group: %s", runbook_name)
        job_name = f"job_{runbook_name}"
        job = self.client.job.create(
            resource_group_name=self.config.resource_group,
            automation_account_name=self.config.automation_account,
            job_name=job_name,
            parameters={
                "properties": {
                    "runbook": {"name": runbook_name},
                    "parameters": {},  # no params passed
                    "runOn": "Agentic_AI_POC_SCCM"   # <-- 🔥 IMPORTANT
                }
            }
        )

        logging.info(
            "Runbook execution started on Hybrid Worker Group. Job ID = %s",
            job.id
        )

        return job_name, job.job_id

    # ###############  FUNCTION: get_output_by_runbook_name ###############
    def get_runbook_output(self,job_name: str, job_id: str) -> str:
        """
        Fetch Azure Automation runbook output using JOB ID.
        Works for all regions including Sweden Central.
        """

        while True:
            job_status = self.client.job.get(
                resource_group_name=self.config.resource_group,
                automation_account_name=self.config.automation_account,
                job_name=job_name
            ).status

            if job_status.lower() in ["completed", "failed","stopped"]:
                break
            time.sleep(5)
        token=self.get_rest_token()
        output_url = (
            f"https://management.azure.com/subscriptions/{self.config.subscription_id}"
            f"/resourceGroups/{self.config.resource_group}"
            f"/providers/Microsoft.Automation/automationAccounts/{self.config.automation_account}"
            f"/jobs/{job_id}/output?api-version=2023-11-01"
        )
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/octet-stream"
            }
        response = requests.get(output_url, headers=headers)
        if response.status_code == 200:
            logging.info("Fetched output for the job '%s'.", job_id)
            return response.text

        logging.warning(
            "Failed to fetch the output '%s'. status: %s, Bodr: %s",
            job_id,
            response.status_code,
            response.text,
            )
        return None

    def clone_runbook_with_metadata(self, source_runbook_name: str, system_name: str, issue_text: str, environment: str) -> str:
        """
        Creates a new runbook by cloning an existing runbook's content and
        adding contextual metadata as a header comment.
        Returns:
            Name of the newly created runbook.
        """
        original_content=  self.fetch_runbook_content(source_runbook_name)
        if original_content is None:
            raise ValueError(f"No content returned for runbook '{source_runbook_name}'")
        timestamp= datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        source_script = f"$SystemName:{system_name}\n"
        new_runbook_name = f"{source_runbook_name}_{system_name}_{timestamp}"

        header_block = [
            f"# Generated by Agentic Automation Team- ",
            f"$ScriptName = 'Detectlaunch_123'",
            f"$DeviceName = '{system_name}' ",
            ]
        annotated_content = "\n".join(header_block) + original_content

        job_name, job_id=self.create_or_update_runbook(new_runbook_name, annotated_content)
        return new_runbook_name,job_name,job_id

#=============================================Azure AI Foundry==========================================

class FoundryAgentService:
    """
    Service wrapper for interacting with Azure AI Foundry agents.
    """
    def __init__(self, config: FoundryConfig, credential: DefaultAzureCredential):
        self.config = config
        self.project = AIProjectClient(endpoint= config.endpoint, credential=credential)
        self.agent = self.project.agents.get_agent(self.config.diagnostic_agent_id)
    
    
    def resolve_runbook_from_issue(self, issue_text: str) ->Optional[str]:
        """
        Sends the issue to the diagnostic agent and expects a final message
        that contains the resolved runbook name.
        Returns:
            Resolved runbook name or None if no mapping was found.
        """
        Resolve_Logger={}

        logging.info("Sending issue to Foundry diagnostic agent.")
        Resolve_Logger['Thread_Start']=datetime.utcnow().isoformat() +'Z'
        thread = self.project.agents.threads.create()
        Resolve_Logger['Thread_End']=datetime.utcnow().isoformat() +'Z'
        Resolve_Logger['Message_Start']=datetime.utcnow().isoformat() +'Z'
        self.project.agents.messages.create(
            thread_id=thread.id,
            role='user',
            content=issue_text
        )
        Resolve_Logger['Message_End']=datetime.utcnow().isoformat() +'Z'
        Resolve_Logger['Run_Start']=datetime.utcnow().isoformat() +'Z'
        run = self.project.agents.runs.create_and_process(
            thread_id=thread.id,
            agent_id=self.agent.id,
            )
        Resolve_Logger['Run_End']=datetime.utcnow().isoformat() +'Z'
        if run.status == "failed":
            logging.error("Foundry run failed. Error: %s")
            return None
        Resolve_Logger['Order_Start']=datetime.utcnow().isoformat() +'Z'
        messages = self.project.agents.messages.list(
            thread_id = thread.id,
            order = ListSortOrder.ASCENDING,
        )
        Resolve_Logger['Order_End']=datetime.utcnow().isoformat() +'Z'
        resolved_runbook_name: Optional[str] = None
        Resolve_Logger['Msg_Read_Start']=datetime.utcnow().isoformat() +'Z'
        for message in messages:
            if not message.text_messages:
                continue
            resolved_runbook_name= message.text_messages[-1].text.value
        Resolve_Logger['Msg_Read_End']=datetime.utcnow().isoformat() +'Z'
        if resolved_runbook_name:
            logging.info(
                "Foundry diagnostic agent resolved runbook '%s'.",
                resolved_runbook_name,
            )
        else:
            logging.warning(
                "Foundry diagnostic agent did not return a runbook name."
            )
        
        return resolved_runbook_name, Resolve_Logger

#==============================================Azure Function Entry======================================

def main(req: func.HttpRequest) -> func.HttpResponse:
    """
    HTTP-triggered Azure Function entry point.
    Responsibilities:
    - Validate and parse request body.
    - Load configuration (environment, automation, foundry).
    - Resolve runbook name via Foundry agent.
    - Optionally clone and publish an new runbook.
    - Return a structured JSON response with detailed status.
    """
    correlation_id = req.headers.get("x-correlation-id", str(uuid.uuid4()))
    logging.info("Request recieved for Agentic Automationfunction. CORRELATIONID = %s", correlation_id)
    time_logger={}
    try:
        # 1. Parse JSON body
        try:
            time_logger['JSON_Parser_Start']=datetime.utcnow().isoformat() +'Z'
            request_body = req.get_json()
            time_logger['JSON_Parser_End']=datetime.utcnow().isoformat() +'Z'
        except ValueError:
            logging.warning("Invalid JSON in request body.")
            return json_response(
                {"Success": False, "error": {"message":"Invalid JSOn payload."}},
                status = 400
            )
        
        # 2. Validate Schema
        try:
            time_logger['Schema_Validation_Start']=datetime.utcnow().isoformat() +'Z'
            issue, execute, target_machine = validate_request_body(request_body)
            time_logger['Schema_Validation_End']=datetime.utcnow().isoformat() +'Z'
        except ValueError as value_error:
            logging.warning("Request validation failed: %s", value_error)
            return json_response(
                {"Success": False, "error":{"message": str(value_error)}},
                status= 400
            )

        #3. Load configuration [Env, Automation, Foundry]
        try:
            time_logger['Config_Start']=datetime.utcnow().isoformat() +'Z'
            config, foundey_dict, automation_dict = load_config_from_akeyless()
            time_logger['Config_End']=datetime.utcnow().isoformat() +'Z'
        except EnvironmentError as environment_error:
            logging.exception("Configuration loading failed.")
            return json_response(
                {"Success":False, 
                "error":{
                    "message":f"Configuration error.",
                    "details": str(environment_error)
                    }
                },
                status = 500
            )
        credential = get_default_credential()
        automation_service = AzureautomationService(config.automation, credential)
        foundry_service = FoundryAgentService(config.foundry, credential)
        event_logger= EventHubLogger(automation_dict, credential)

        # 1. Log "Issue Recieved"
        event_logger.send_event(
            {
                "event_type": "issue recieved",
                "correlation_id": correlation_id,
                "environment": config.environment,
                "target_machine": target_machine,
                "execute": execute,
                "timestamp_utc": datetime.utcnow().isoformat() +'Z',
            }
        )
        #4. Resolve runbook using AI Foundry Agent
        runbook_name, Resolve_Logger = foundry_service.resolve_runbook_from_issue(issue)
        if not runbook_name:
            event_logger.send_event(
                {
                    "event_type": "Runbook Resolution Failed",
                    "correlation_id": correlation_id,
                    "environment": config.environment,
                    "timestamp_utc": datetime.utcnow().isoformat() +'Z',
                }
            )
            return json_response(
                {"Success": False, "error": {"message":(
                    "No Runbook could be resolved for the given issue.",
                    "Please contact the agentic AI POC team."
                    )}},
                    status =404
            )

        #5. Execute path: Clone runbook with metadata, publish and Run
        try:
            cloned_name, job_name, job_id = automation_service.clone_runbook_with_metadata(
                source_runbook_name= runbook_name,
                system_name = target_machine,
                issue_text = issue,
                environment = config.environment
            )
        except Exception as unknown_exception:
            logging.exception("Runbook cloning failed.")
            event_logger.send_event(
                {
                    "event_type": "Runbook Clone Failed",
                    "correlation_id": correlation_id,
                    "environment": config.environment,
                    "Original Runbook": runbook_name,
                    "error": str(unknown_exception),
                    "timestamp_utc": datetime.utcnow().isoformat() +'Z',
                }
            )
            return json_response(
                {"Success": False,
                "error":{
                    "message":"Runbook cloning or publishing failed.",
                    "details": str(unknown_exception)
                    }
                },
                status = 502
            )

        logging.info("Runbook cloned successfully: %s", cloned_name)
        event_logger.send_event(
            {
                "event_type": "Runbook cloned successfully",
                "correlation_id": correlation_id,
                "environment": config.environment,
                "Original Runbook": runbook_name,
                "Cloned_Runbook": cloned_name,
                "target_machine": target_machine,
                "timestamp_utc": datetime.utcnow().isoformat() +'Z',
            }
        )

        diagnostic_agent_message=automation_service.get_runbook_output(job_name, job_id)
        
        return json_response(
            {
                "Success": True,
                "original_runbook_name": runbook_name,
                "cloned_runbook_name": cloned_name,
                "job_name":job_name,
                "job_id": job_id,
                "executed": True,
                "target_machine": target_machine,
                "environment": config.environment,
                "message": (
                    f"Script to diagnose the issue is saved as runbook"
                    f"{diagnostic_agent_message}"
                    ),
                "Time_Logger":time_logger,
                "Resolution_Logger":Resolve_Logger
            },
            status = 200
        )

    
    except Exception as unhandled_exception:
        #Final safeguard: log and return generic error
        logging.exception("Unhandled exception in agentic automation function.")
        return json_response(
            {
                "Success": False,
                "error":{
                    "message": "Unhandled Server error. Please contact the automation team.",
                    "details": str(unhandled_exception),
                }
            },
            status= 500
        )





{
    "Success": true,
    "original_runbook_name": "Diagnose_KB0010265",
    "cloned_runbook_name": "Diagnose_KB0010265_demo_syetem_20251125_051106",
    "job_name": "job_Diagnose_KB0010265_demo_syetem_20251125_051106",
    "job_id": "82ee0b2d-bddf-492e-9a6d-b0f4f9d21522",
    "executed": true,
    "target_machine": "demo_syetem",
    "environment": "dev",
    "message": "Script to diagnose the issue is saved as runbook{\r\n    \"CheckStarted\":  {\r\n                         \"value\":  \"\/Date(1764047513042)\/\",\r\n                         \"DisplayHint\":  2,\r\n                         \"DateTime\":  \"Tuesday, November 25, 2025 5:11:53 AM\"\r\n                     },\r\n    \"Action\":  \"Diagnose Outlook install, user profile, and OST presence\",\r\n    \"UserDetection\":  \"Failed to detect logged-in user.\",\r\n    \"UserProfilePath\":  null,\r\n    \"OutlookInstallCheck\":  \"Outlook is NOT installed\",\r\n    \"OutlookProcessCheck\":  \"OUTLOOK.EXE is not running\"\r\n}\r\n\r\n",
    "Time_Logger": {
        "JSON_Parser_Start": "2025-11-25T05:10:43.372110Z",
        "JSON_Parser_End": "2025-11-25T05:10:43.381332Z",
        "Schema_Validation_Start": "2025-11-25T05:10:43.381339Z",
        "Schema_Validation_End": "2025-11-25T05:10:43.381513Z",
        "Config_Start": "2025-11-25T05:10:43.381517Z",
        "Config_End": "2025-11-25T05:10:43.382286Z"
    },
    "Resolution_Logger": {
        "Thread_Start": "2025-11-25T05:10:50.327426Z",
        "Thread_End": "2025-11-25T05:10:50.994943Z",
        "Message_Start": "2025-11-25T05:10:50.994951Z",
        "Message_End": "2025-11-25T05:10:51.359884Z",
        "Run_Start": "2025-11-25T05:10:51.359892Z",
        "Run_End": "2025-11-25T05:11:04.781597Z",
        "Order_Start": "2025-11-25T05:11:04.781614Z",
        "Order_End": "2025-11-25T05:11:04.783052Z",
        "Msg_Read_Start": "2025-11-25T05:11:04.783056Z",
        "Msg_Read_End": "2025-11-25T05:11:05.664474Z"
    }
}
