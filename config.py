###############################################################################################
## Project Name   : Agentic AI POC
## Business Owner : Data and AIA
## Author/Team    : POC Team
## Date           : 24th Oct 2025
##
## Purpose:
##   Configuration script to securely load credentials and environment variables
##   for the Agentic AI Proof of Concept.
##
##   The script performs the following:
##     - Loads environment variables from a `.env` file.
##     - Authenticates to Akeyless secret management service.
##     - Retrieves agent and automation-related configuration secrets.
##     - Exposes the credentials and identifiers for downstream modules.
###############################################################################################

# -----------------------------------------------------------------------------------------------
# Library Imports
# -----------------------------------------------------------------------------------------------
from dotenv import load_dotenv
import os
import akeyless
from akeyless.rest import ApiException
import json
import sys

# -----------------------------------------------------------------------------------------------
# Load Environment Variables
# -----------------------------------------------------------------------------------------------
load_dotenv()

AKEYLESS_ACCESS_ID = os.getenv("AKEYLESS_ID")
AKEYLESS_SECRET = os.getenv("AKEYLESS_SECRET")
AGENT_VARIABLE_DICT = os.getenv("AGENT_VARIABLE_DICT")
AUTOMATION_VARIABLE_DICT = os.getenv("AUTOMATION_VARIABLE")

# -----------------------------------------------------------------------------------------------
# Akeyless Configuration
# -----------------------------------------------------------------------------------------------
akeyless_configuration = akeyless.Configuration(
    # Default: Public API Gateway
    host="https://api.akeyless.io"

    # Alternate internal gateway examples:
    # host="https://gateway.company.com:8081"
    # host="https://gateway.company.com:8080/v2"
    # host="https://akl-gw.teva.corp:8000/api/v2"
)

# Initialize Akeyless API client
api_client = akeyless.ApiClient(akeyless_configuration)
api = akeyless.V2Api(api_client)

# -----------------------------------------------------------------------------------------------
# Authenticate with Akeyless
# -----------------------------------------------------------------------------------------------
try:
    auth_request = akeyless.Auth(
        access_id=AKEYLESS_ACCESS_ID,
        access_key=AKEYLESS_SECRET
    )
    auth_response = api.auth(auth_request)
    token = auth_response.token
except ApiException as e:
    print(f"[AKEYLESS AUTH ERROR] Failed to authenticate: {e.body or str(e)}")
    sys.exit(1)
except Exception as e:
    print(f"[UNEXPECTED ERROR] During authentication: {e}")
    sys.exit(1)

# -----------------------------------------------------------------------------------------------
# Retrieve Secrets from Akeyless
# -----------------------------------------------------------------------------------------------
try:
    # Prepare request to fetch secrets
    secret_request = akeyless.GetSecretValue(
        names=[AGENT_VARIABLE_DICT, AUTOMATION_VARIABLE_DICT],
        token=token
    )

    # Fetch secrets
    secret_response = api.get_secret_value(secret_request)

    # Parse JSON values into Python dictionaries
    foundry_variables = json.loads(secret_response[AGENT_VARIABLE_DICT])
    automation_variables = json.loads(secret_response[AUTOMATION_VARIABLE_DICT])

    # -------------------------------------------------------------------------------------------
    # Foundry Agent (AI Model) Configuration
    # -------------------------------------------------------------------------------------------
    MODEL_ENDPOINT = foundry_variables["Endpoint"]
    MODEL_NAME = foundry_variables["Model_Name"]
    MODEL_DEPLOYMENT = foundry_variables["Deployment"]
    API_KEY = foundry_variables["API_Key"]
    API_VERSION = foundry_variables["API_Version"]
    DIAGNOSTIC_AGENT_ID = foundry_variables["DIAGNOSTIC_Agent_ID"]
    TROUBLESHOOTING_AGENT_ID = foundry_variables["TROUBLESHOOT_Agent_ID"]

    # -------------------------------------------------------------------------------------------
    # Azure Automation Configuration
    # -------------------------------------------------------------------------------------------
    SUBSCRIPTION_ID = automation_variables["AZ_SUBSCRIPTION_ID"]
    RESOURCE_GROUP = automation_variables["AZ_RESOURCE_GROUP"]
    AUTOMATION_ACCOUNT = automation_variables["AZ_AUTOMATION_ACCOUNT"]
    LOCATION = automation_variables["LOCATION"]

except ApiException as e:
    print(f"[AKEYLESS API ERROR] Unable to retrieve secrets: {e.body or str(e)}")
    sys.exit(1)
except KeyError as e:
    print(f"[CONFIG ERROR] Missing expected key in secrets: {e}")
    sys.exit(1)
except Exception as e:
    print(f"[UNEXPECTED ERROR] During secret retrieval: {e}")
    sys.exit(1)
