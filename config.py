#################################################################################################
## Project Name   : Agentic AI POC
## Business Owner : Data and AIA
## Author/Team    : POC Team
## Date           : 24th Oct 2025
##
## Purpose:
##   Load configuration settings and secrets for the Agentic AI POC.
##
## Responsibilities:
##     - Load environment variables from `.env`
##     - Authenticate with Akeyless secret manager
##     - Retrieve Foundry agent settings and Azure Automation settings
##     - Expose configuration variables for other modules
##
## Notes:
##   * No new logic added — only cleanup, structure, and standardization.
##   * API exceptions and unexpected errors are logged and exit gracefully.
#################################################################################################


# ############### Imports ###############
import os
import json
import sys
import logging
from dotenv import load_dotenv

import akeyless
from akeyless.rest import ApiException


# ############### Logging Setup ###############
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger("config")


# ############### Load Environment Variables ###############
load_dotenv()

AKEYLESS_ACCESS_ID = os.getenv("AKEYLESS_ID")
AKEYLESS_SECRET = os.getenv("AKEYLESS_SECRET")
AGENT_VARIABLE_DICT = os.getenv("AGENT_VARIABLE_DICT")
AUTOMATION_VARIABLE_DICT = os.getenv("AUTOMATION_VARIABLE")

if not all([AKEYLESS_ACCESS_ID, AKEYLESS_SECRET, AGENT_VARIABLE_DICT, AUTOMATION_VARIABLE_DICT]):
    logger.error("Missing required environment variables for Akeyless or dict names.")
    sys.exit(1)


# ############### Akeyless Client Setup ###############
akeyless_config = akeyless.Configuration(host="https://api.akeyless.io")

api_client = akeyless.ApiClient(akeyless_config)
akeyless_api = akeyless.V2Api(api_client)


# ############### Authenticate with Akeyless ###############
try:
    auth_req = akeyless.Auth(
        access_id=AKEYLESS_ACCESS_ID,
        access_key=AKEYLESS_SECRET,
    )
    auth_resp = akeyless_api.auth(auth_req)
    token = auth_resp.token

    logger.info("Successfully authenticated with Akeyless.")

except ApiException as exc:
    logger.error("Akeyless authentication failed: %s", exc.body or str(exc))
    sys.exit(1)
except Exception as exc:
    logger.exception("Unexpected error during Akeyless authentication: %s", exc)
    sys.exit(1)


# ############### Retrieve Secrets from Akeyless ###############
try:
    secret_req = akeyless.GetSecretValue(
        names=[AGENT_VARIABLE_DICT, AUTOMATION_VARIABLE_DICT],
        token=token,
    )

    secret_resp = akeyless_api.get_secret_value(secret_req)

    # Parse JSON dictionaries
    foundry_variables = json.loads(secret_resp[AGENT_VARIABLE_DICT])
    automation_variables = json.loads(secret_resp[AUTOMATION_VARIABLE_DICT])

    logger.info("Successfully retrieved and parsed Akeyless secrets.")

except ApiException as exc:
    logger.error("Akeyless API error retrieving secrets: %s", exc.body or str(exc))
    sys.exit(1)
except KeyError as exc:
    logger.error("Missing expected key in Akeyless secrets: %s", exc)
    sys.exit(1)
except Exception as exc:
    logger.exception("Unexpected error retrieving secrets: %s", exc)
    sys.exit(1)


# ############### Foundry Agent Configuration ###############
MODEL_ENDPOINT = foundry_variables["Endpoint"]
MODEL_NAME = foundry_variables["Model_Name"]
MODEL_DEPLOYMENT = foundry_variables["Deployment"]
API_KEY = foundry_variables["API_Key"]
API_VERSION = foundry_variables["API_Version"]
DIAGNOSTIC_AGENT_ID = foundry_variables["DIAGNOSTIC_Agent_ID"]
TROUBLESHOOTING_AGENT_ID = foundry_variables["TROUBLESHOOT_Agent_ID"]


# ############### Azure Automation Configuration ###############
SUBSCRIPTION_ID = automation_variables["AZ_SUBSCRIPTION_ID"]
RESOURCE_GROUP = automation_variables["AZ_RESOURCE_GROUP"]
AUTOMATION_ACCOUNT = automation_variables["AZ_AUTOMATION_ACCOUNT"]
LOCATION = automation_variables["LOCATION"]
