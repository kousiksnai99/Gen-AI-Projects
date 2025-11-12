#################################################################################################
## Project Name: Agentic AI POC                                                                ##
## Business Owner / Team: Data and AIA                                                         ##
## Author / Team: POC Team                                                                     ##
## Date: 24th Oct 2025                                                                         ##
## Purpose: Configuration loader for credentials and environment settings via Akeyless.        ##
## Dependencies: dotenv, akeyless, os, json                                                    ##
#################################################################################################

###############  IMPORT PACKAGES  ###############
from dotenv import load_dotenv
import os
import akeyless
from akeyless.rest import ApiException
import json
import logging

###############  LOGGING CONFIGURATION  ###############
logging.basicConfig(
    filename="agent_api.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

###############  LOAD ENVIRONMENT VARIABLES  ###############
load_dotenv()

AKEYLESS_ACCESS_ID = os.getenv("AKEYLESS_ID")
AKEYLESS_SECRET = os.getenv("AKEYLESS_SECRET")
AGENT_VARIABLE_DICT = os.getenv("AGENT_VARIABLE_DICT")
AUTOMATION_VARIABLE_DICT = os.getenv("AUTOMATION_VARIABLE")
ENVIRONMENT = os.getenv("ENVIRONMENT", "dev")

###############  AKEYLESS AUTHENTICATION  ###############
akeyless_configuration = akeyless.Configuration(host="https://api.akeyless.io")
api_client = akeyless.ApiClient(akeyless_configuration)
api = akeyless.V2Api(api_client)

try:
    body = akeyless.Auth(access_id=AKEYLESS_ACCESS_ID, access_key=AKEYLESS_SECRET)
    res = api.auth(body)
    token = res.token

    body = akeyless.GetSecretValue(names=[AGENT_VARIABLE_DICT, AUTOMATION_VARIABLE_DICT], token=token)
    res = api.get_secret_value(body)

    Foundry_Variable = json.loads(res[AGENT_VARIABLE_DICT])
    Automation_Variable = json.loads(res[AUTOMATION_VARIABLE_DICT])

    MODEL_ENDPOINT = Foundry_Variable["Endpoint"]
    MODEL_NAME = Foundry_Variable["Model_Name"]
    MODEL_DEPLOYMENT = Foundry_Variable["Deployment"]
    API_KEY = Foundry_Variable["API_Key"]
    API_VERSION = Foundry_Variable["API_Version"]
    DIAGNOSTIC_AGENT_ID = Foundry_Variable["DIAGNOSTIC_Agent_ID"]
    TROUBLESHOOTING_AGENT_ID = Foundry_Variable["TROUBLESHOOT_Agent_ID"]

    SUBSCRIPTION_ID = Automation_Variable["AZ_SUBSCRIPTION_ID"]
    RESOURCE_GROUP = Automation_Variable["AZ_RESOURCE_GROUP"]
    AUTOMATION_ACCOUNT = Automation_Variable["AZ_AUTOMATION_ACCOUNT"]
    LOCATION = Automation_Variable["LOCATION"]

    logging.info("Configuration successfully loaded from Akeyless.")
except ApiException as e:
    logging.error(f"Akeyless API Error: {e.body or str(e)}")
except Exception as e:
    logging.error(f"Unexpected configuration load error: {e}")
