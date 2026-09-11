import requests
import os
from dotenv import load_dotenv
import time
from datetime import datetime, timezone
load_dotenv()

TENANT_ID = "3f991a7b-ea93-4169-b28c-c36ff3e5b0d1"
CLIENT_ID = "e91e93ca-955f-47d5-a491-a41985414c57"
CLIENT_SECRET = "1c98Q~KxkROmy8Uyw8gSixhI6Dv7tdhnAzIO1a2n"
SCOPE = "api://7f70f393-ab7d-4e6b-a92e-952c23dbcba9/.default"
BASE_URL="https://apidev.tevapharm.com/gateway/serviceNowTicketingAPI/1.0"
RESOURCE_PATH="a96d6adb3ba2cf1079901b9aa4e45a2f"

def get_token():
    token_validation_url = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token"
    payload = {
        "client_id" : CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "scope": SCOPE,
        "grant_type": "client_credentials"
    }
    response = requests.post(token_validation_url, data=payload)
    return response.json()["access_token"]



def get_ticket_detail(incident_number, access_token):
    url = (
        f"{BASE_URL}/api/tpi/tevagenericwebservice/incident/{RESOURCE_PATH}"
        f"?sysparm_query=number={incident_number}"
    )

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json"
    }

    params = {
        "sysparam_query": f"number={incident_number}"
    }

    response= requests.get(
        url,
        headers=headers,
        timeout=30
    )
    response.status_code
    return response.json()

header = get_token()
test=get_ticket_detail(incident_number="INC09485371", access_token=header)
print(test)
