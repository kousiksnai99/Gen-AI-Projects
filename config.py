##################################################################################### 
## Project name : Agentic AI POC                                                    #
## Business owner , Team : Data and AIA                                             #
## Notebook Author , Team: POC Team                                                 #
##Date: 24th Oct 2025                                                               #
##Puprose of Notebook: This is a configuration notbook to load all the credentials. #
#####################################################################################

# # Load all the libraries

from dotenv import load_dotenv
import os
import akeyless
from akeyless.rest import ApiException
import json
import sys   

# Load Variables from .env
load_dotenv()
AKEYLESS_ACCESS_ID = os.getenv("AKEYLESS_ID")
AKEYLESS_SECRET = os.getenv("AKEYLESS_SECRET")
AGENT_VARIABLE_DICT = os.getenv("AGENT_VARIABLE_DICT")
AUTOMATION_VARIABLE_DICT = os.getenv("AUTOMATION_VARIABLE")
akeyless_configuration = akeyless.Configuration(
        # default: public API Gateway
        host = "https://api.akeyless.io"
        # use port 8081 exposed by the deployment:
        # host = "https://gateway.company.com:8081"
        # use port 8080 exposed by the deployment with /v2 prefix:
        # host = "https://gateway.company.com:8080/v2"
        # host="https://akl-gw.teva.corp:8000/api/v2"
)

api_client=akeyless.ApiClient(akeyless_configuration)
api = akeyless.V2Api(api_client)

body = akeyless.Auth(access_id=AKEYLESS_ACCESS_ID, access_key=AKEYLESS_SECRET)
res = api.auth(body)
token = res.token
# body = akeyless.GetSecretValue(names=[AGENT_VARIABLE_DICT, FUNCTION_APP_DICT, AZURE_AUTOMATION_DICT],token=token)
body = akeyless.GetSecretValue(names=[AGENT_VARIABLE_DICT,AUTOMATION_VARIABLE_DICT],token=token)

try:
        res=api.get_secret_value(body)
        Foundry_Variable=json.loads(res[AGENT_VARIABLE_DICT])
        # Function_Variable=json.loads(res[FUNCTION_APP_DICT])
        Automation_Variable=json.loads(res[AUTOMATION_VARIABLE_DICT])

        MODEL_ENDPOINT = Foundry_Variable['Endpoint']
        MODEL_NAME = Foundry_Variable['Model_Name']
        MODEL_DEPLOYMENT = Foundry_Variable['Deployment']
        API_KEY= Foundry_Variable['API_Key']
        API_VERSION = Foundry_Variable['API_Version']
        DIAGNOSTIC_AGENT_ID = Foundry_Variable['DIAGNOSTIC_Agent_ID']
        TROUBLESHOOTING_AGENT_ID = Foundry_Variable['TROUBLESHOOT_Agent_ID']

        SUBSCRIPTION_ID = Automation_Variable['AZ_SUBSCRIPTION_ID']
        RESOURCE_GROUP = Automation_Variable['AZ_RESOURCE_GROUP']
        AUTOMATION_ACCOUNT = Automation_Variable['AZ_AUTOMATION_ACCOUNT']
        LOCATION = Automation_Variable['LOCATION']
except ApiException as e:
        print("Akeyless API Error:", e.body or str(e))
except Exception as e:
        print("Unexpected Error:", e)
