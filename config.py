##################################################################################### 
## Project name : Agentic AI POC                                                    #
## Business owner , Team : Data and AIA                                             #
## Notebook Author , Team: POC Team                                                 #
## Date: 2025-10-24                                                                #
## Purpose of Notebook: Central configuration loader.                               #
## Connections: This file is imported by diagnostic_agent, troubleshooting_agent and utils.
#####################################################################################

from __future__ import annotations

###############  IMPORT PACKAGES  ###############
import os
import json
from dotenv import load_dotenv
import akeyless
from akeyless.rest import ApiException
##################################################

# ###############  ENV LOADING & DEFAULTS ###############
# Loads variables from .env into environment. Keep behavior unchanged.
load_dotenv()

# Environment descriptor (used by CI/CD to avoid hardcoding)
ENVIRONMENT = os.getenv("ENVIRONMENT", "dev")  # e.g., dev/test/prod - set via CI/CD
# ######################################################

# ###############  AKEYLESS AUTH & SECRET RETRIEVAL ###############
AKEYLESS_ACCESS_ID = os.getenv("AKEYLESS_ID")
AKEYLESS_SECRET = os.getenv("AKEYLESS_SECRET")
AGENT_VARIABLE_DICT = os.getenv("AGENT_VARIABLE_DICT")
AUTOMATION_VARIABLE_DICT = os.getenv("AUTOMATION_VARIABLE")

# Build akeyless client (same as existing code - no KeyVault changes)
akeyless_configuration = akeyless.Configuration(
    host="https://api.akeyless.io"
)
api_client = akeyless.ApiClient(akeyless_configuration)
api = akeyless.V2Api(api_client)

# Authenticate and load secrets into module-level constants.
# This code intentionally mirrors existing behavior and will raise / print if secrets fail.
try:
    body = akeyless.Auth(access_id=AKEYLESS_ACCESS_ID, access_key=AKEYLESS_SECRET)
    res = api.auth(body)
    token = res.token

    body = akeyless.GetSecretValue(names=[AGENT_VARIABLE_DICT, AUTOMATION_VARIABLE_DICT], token=token)
    res = api.get_secret_value(body)

    Foundry_Variable = json.loads(res[AGENT_VARIABLE_DICT])
    Automation_Variable = json.loads(res[AUTOMATION_VARIABLE_DICT])

    MODEL_ENDPOINT = Foundry_Variable.get("Endpoint")
    MODEL_NAME = Foundry_Variable.get("Model_Name")
    MODEL_DEPLOYMENT = Foundry_Variable.get("Deployment")
    API_KEY = Foundry_Variable.get("API_Key")
    API_VERSION = Foundry_Variable.get("API_Version")
    DIAGNOSTIC_AGENT_ID = Foundry_Variable.get("DIAGNOSTIC_Agent_ID")
    TROUBLESHOOTING_AGENT_ID = Foundry_Variable.get("TROUBLESHOOT_Agent_ID")

    SUBSCRIPTION_ID = Automation_Variable.get("AZ_SUBSCRIPTION_ID")
    RESOURCE_GROUP = Automation_Variable.get("AZ_RESOURCE_GROUP")
    AUTOMATION_ACCOUNT = Automation_Variable.get("AZ_AUTOMATION_ACCOUNT")
    LOCATION = Automation_Variable.get("LOCATION")

except ApiException as e:
    # Keep same behavior: print error to console (this file is executed during import)
    # Caller code should handle missing config variables gracefully.
    print("Akeyless API Error:", e.body or str(e))
    # Provide minimal fallbacks as None so modules can check for None.
    MODEL_ENDPOINT = MODEL_NAME = MODEL_DEPLOYMENT = API_KEY = API_VERSION = DIAGNOSTIC_AGENT_ID = TROUBLESHOOTING_AGENT_ID = None
    SUBSCRIPTION_ID = RESOURCE_GROUP = AUTOMATION_ACCOUNT = LOCATION = None
except Exception as e:
    print("Unexpected Error:", e)
    MODEL_ENDPOINT = MODEL_NAME = MODEL_DEPLOYMENT = API_KEY = API_VERSION = DIAGNOSTIC_AGENT_ID = TROUBLESHOOTING_AGENT_ID = None
    SUBSCRIPTION_ID = RESOURCE_GROUP = AUTOMATION_ACCOUNT = LOCATION = None
