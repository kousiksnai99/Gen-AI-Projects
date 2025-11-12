#####################################################################################
## Project name : Agentic AI POC - Configuration                                     #
## Business owner, Team : Data and AIA                                               #
## Notebook Author, Team: POC Team                                                   #
## Date: 2025-11-12                                                                  #
## Purpose of File: Centralized configuration loader. Uses Akeyless or environment.  #
## Connections: Used by diagnostic_agent.py and troubleshooting_agent.py and utils.py#
## Notes: Avoid hardcoding environment values. Provide ENVIRONMENT variable for CI/CD.#
#####################################################################################

###############  IMPORT PACKAGES  ###############
from dotenv import load_dotenv
import os
import json
import logging

# Optional Akeyless secrets manager integration (keeps behaviour from original project).
# If AKEYLESS_* variables are present, load secrets from Akeyless. Otherwise, rely on env vars.
try:
    import akeyless
    from akeyless.rest import ApiException
except Exception:
    akeyless = None

###############  LOAD ENV FILES  ###############
# Load .env for local dev (CI/CD uses env vars).
load_dotenv()

logger = logging.getLogger("config")

###############  ENVIRONMENT VARIABLES  ###############
ENVIRONMENT = os.getenv("ENVIRONMENT", "dev").lower()

# Akeyless credentials (optional)
AKEYLESS_ACCESS_ID = os.getenv("AKEYLESS_ID")
AKEYLESS_SECRET = os.getenv("AKEYLESS_SECRET")
AGENT_VARIABLE_DICT = os.getenv("AGENT_VARIABLE_DICT")
AUTOMATION_VARIABLE_DICT = os.getenv("AUTOMATION_VARIABLE")

# Fallback/defaults: values that must be present in env or retrieved from secret store
# (These are not hard-coded for environments. CI/CD should inject values for each environment.)
MODEL_ENDPOINT = os.getenv("MODEL_ENDPOINT")
MODEL_NAME = os.getenv("MODEL_NAME")
MODEL_DEPLOYMENT = os.getenv("MODEL_DEPLOYMENT")
API_KEY = os.getenv("API_KEY")
API_VERSION = os.getenv("API_VERSION")
DIAGNOSTIC_AGENT_ID = os.getenv("DIAGNOSTIC_AGENT_ID")
TROUBLESHOOTING_AGENT_ID = os.getenv("TROUBLESHOOTING_AGENT_ID")

SUBSCRIPTION_ID = os.getenv("AZ_SUBSCRIPTION_ID")
RESOURCE_GROUP = os.getenv("AZ_RESOURCE_GROUP")
AUTOMATION_ACCOUNT = os.getenv("AZ_AUTOMATION_ACCOUNT")
LOCATION = os.getenv("LOCATION")

# Event Hub telemetry (optional). If set, utils will attempt to emit events
EVENTHUB_CONNECTION_STRING = os.getenv("EVENTHUB_CONNECTION_STRING")
EVENTHUB_NAME = os.getenv("EVENTHUB_NAME")

###############  OPTIONAL: LOAD FROM AKEYLESS IF CONFIGURED  ###############
if akeyless and AKEYLESS_ACCESS_ID and AKEYLESS_SECRET and AGENT_VARIABLE_DICT and AUTOMATION_VARIABLE_DICT:
    try:
        akeyless_configuration = akeyless.Configuration(host="https://api.akeyless.io")
        api_client = akeyless.ApiClient(akeyless_configuration)
        api = akeyless.V2Api(api_client)
        body = akeyless.Auth(access_id=AKEYLESS_ACCESS_ID, access_key=AKEYLESS_SECRET)
        res = api.auth(body)
        token = res.token
        body = akeyless.GetSecretValue(names=[AGENT_VARIABLE_DICT, AUTOMATION_VARIABLE_DICT], token=token)
        res = api.get_secret_value(body)
        Foundry_Variable = json.loads(res[AGENT_VARIABLE_DICT])
        Automation_Variable = json.loads(res[AUTOMATION_VARIABLE_DICT])

        # Map to our config values if not already set via ENV
        MODEL_ENDPOINT = MODEL_ENDPOINT or Foundry_Variable.get('Endpoint')
        MODEL_NAME = MODEL_NAME or Foundry_Variable.get('Model_Name')
        MODEL_DEPLOYMENT = MODEL_DEPLOYMENT or Foundry_Variable.get('Deployment')
        API_KEY = API_KEY or Foundry_Variable.get('API_Key')
        API_VERSION = API_VERSION or Foundry_Variable.get('API_Version')
        DIAGNOSTIC_AGENT_ID = DIAGNOSTIC_AGENT_ID or Foundry_Variable.get('DIAGNOSTIC_Agent_ID')
        TROUBLESHOOTING_AGENT_ID = TROUBLESHOOTING_AGENT_ID or Foundry_Variable.get('TROUBLESHOOT_Agent_ID')

        SUBSCRIPTION_ID = SUBSCRIPTION_ID or Automation_Variable.get('AZ_SUBSCRIPTION_ID')
        RESOURCE_GROUP = RESOURCE_GROUP or Automation_Variable.get('AZ_RESOURCE_GROUP')
        AUTOMATION_ACCOUNT = AUTOMATION_ACCOUNT or Automation_Variable.get('AZ_AUTOMATION_ACCOUNT')
        LOCATION = LOCATION or Automation_Variable.get('LOCATION')

        logger.info("Loaded configuration from Akeyless secret store.")
    except ApiException as e:
        logger.error("Akeyless API Error: %s", getattr(e, "body", str(e)))
    except Exception as e:
        logger.error("Unexpected Error loading config from Akeyless: %s", e)

# Validate that required values are present for runtime operations (log warnings)
_required = {
    "MODEL_ENDPOINT": MODEL_ENDPOINT,
    "DIAGNOSTIC_AGENT_ID": DIAGNOSTIC_AGENT_ID,
    "TROUBLESHOOTING_AGENT_ID": TROUBLESHOOTING_AGENT_ID,
    "SUBSCRIPTION_ID": SUBSCRIPTION_ID,
    "RESOURCE_GROUP": RESOURCE_GROUP,
    "AUTOMATION_ACCOUNT": AUTOMATION_ACCOUNT,
}
for name, value in _required.items():
    if not value:
        logger.warning("%s is not set. Ensure CI/CD injects this per-environment.", name)
