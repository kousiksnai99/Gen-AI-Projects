############################################################################################################
## Project Name        : Agentic AI POC                                                                  ##
## Business Owner , Team: Data and AIA                                                                    ##
## Notebook Author , Team: POC Team                                                                       ##
## Date                : 29th Oct 2025                                                                    ##
## Purpose of Notebook : API-based Agentic AI solution for diagnostics and troubleshooting automation     ##
############################################################################################################

---

# 🧠 Agentic AI Diagnostic & Troubleshooting API

This project provides an **Agentic AI** solution that enables **automated diagnostics** and **troubleshooting** of IT issues using **Azure AI Project Agents** and **Azure Automation Runbooks**.  
It exposes REST APIs (via FastAPI) that allow clients to:
- Send an issue to a **Diagnostic Agent** → returns the relevant runbook name.
- Send an issue to a **Troubleshooting Agent** → returns detailed steps and can execute the runbook automatically.
- Manage and execute runbooks securely in **Azure Automation**.

---

## 🔗 Connected Modules

| File | Description | Connected To |
|------|--------------|--------------|
| **main.py** | Exposes FastAPI endpoints for Diagnostic & Troubleshooting flows | diagnostic_agent.py, troubleshooting_agent.py, utils.py |
| **diagnostic_agent.py** | Communicates with Azure AI Diagnostic Agent | config.py |
| **troubleshooting_agent.py** | Communicates with Azure AI Troubleshooting Agent | config.py |
| **config.py** | Loads secrets from Akeyless vault | diagnostic_agent.py, troubleshooting_agent.py, utils.py |
| **utils.py** | Handles Azure Automation Runbook creation and publishing | main.py, diagnostic_agent.py |

---

## 🏗️ Architecture Overview

User Request
│
▼
┌───────────────────────────┐
│ FastAPI (main.py) │
│ Exposes /diagnostic & /troubleshooting endpoints │
└───────────────────────────┘
│
▼
┌───────────────────────────┐
│ Diagnostic / Troubleshooting Agents │
│ (Azure AI Projects via SDK) │
└───────────────────────────┘
│
▼
┌───────────────────────────┐
│ Azure Automation Runbooks │
│ Runbook creation & execution │
└───────────────────────────┘

yaml
Copy code

---

## ⚙️ Functional Overview

### Diagnostic Agent Flow
1. User submits a system issue.
2. Agent processes the text and determines the related runbook.
3. The runbook is either returned or executed automatically based on user’s request.

### Troubleshooting Agent Flow
1. User describes an issue.
2. Agent returns a suggested fix and asks for confirmation.
3. Upon “yes”, the system executes the associated runbook on the target machine.

---

## 🧩 Environment Setup

### Supported Environments
| Environment | Repo Name Example | Purpose |
|--------------|------------------|----------|
| **Development** | `MMIT` | Development & local testing |
| **Production** | `MMIT_CDW` | Live production deployment |

> ⚠️ Ensure all environments use the **same Azure DevOps repo name** for consistency.

---

## 🧰 Prerequisites

Before running the application, ensure you have:
- Python 3.9 or higher
- Azure CLI installed and logged in (`az login`)
- Access to Azure Automation Account
- Valid Akeyless credentials
- Internet access to Azure endpoints

---

## 🚀 Installation and Execution Steps

### 1️⃣ Clone the Repository
```bash
git clone https://dev.azure.com/<organization>/<project>/_git/<repo-name>
cd <repo-name>
2️⃣ Create a Virtual Environment
bash
Copy code
python -m venv venv
Activate it:

Windows: venv\Scripts\activate

Mac/Linux: source venv/bin/activate

3️⃣ Install Dependencies
bash
Copy code
pip install -r requirements.txt
4️⃣ Create and Configure .env File
Create a .env file in the project root:

bash
Copy code
AKEYLESS_ID=<your_akeyless_access_id>
AKEYLESS_SECRET=<your_akeyless_secret>
AGENT_VARIABLE_DICT=<your_agent_secret_path>
AUTOMATION_VARIABLE=<your_automation_secret_path>
5️⃣ Authenticate to Azure
bash
Copy code
az login
6️⃣ Run the API
bash
Copy code
python main.py
7️⃣ Verify the API
Check health status:

bash
Copy code
GET http://localhost:8000/health
Expected response:

json
Copy code
{"status": "ok", "message": "API is running"}
🧪 Example API Requests
Diagnostic Agent
bash
Copy code
POST http://localhost:8000/diagnostic/chat
Content-Type: application/json

{
  "issue": "Exchange mail flow is failing",
  "execute": true,
  "target_machine": "demo_system"
}
Troubleshooting Agent
bash
Copy code
POST http://localhost:8000/troubleshooting/chat
Content-Type: application/json

{
  "issue": "Cannot open Outlook",
  "execute": true,
  "target_machine": "demo_system"
}
🔒 Security & Authentication
Authentication: via AzureCliCredential() and DefaultAzureCredential()

Secrets Management: via Akeyless

Access Control: Managed through Azure AD groups and Entra ID (future scope)

No Hardcoded Secrets – all sensitive variables loaded from .env or Akeyless.

🧾 Logging & Error Handling
All logs are routed via the logging module (no raw print statements).

Each runbook creation and API execution is timestamped.

Error handling through FastAPI’s HTTPException.

Background cleanup for expired pending confirmations.

🧮 Cost and Resource Tracking
Each environment (Dev, Test, Prod) must have Azure resource tagging for cost visibility:

Tag Key	Tag Value Example
CostCenter	DataAIA_AgenticAI_POC
Owner	DataAIA
Environment	Dev / Prod

⚡ CI/CD Deployment (Azure DevOps)
Pipeline Parameters
environment → dev, test, prod

version → build version

CI/CD Flow
Developer commits code to branch.

Build pipeline triggers → runs unit tests.

Approval step by external reviewer.

Deployment pipeline promotes code to next environment.

Configuration variables (e.g., .env, secrets) applied dynamically per environment.

❗ No manual changes to credentials or configurations allowed post-deployment.

🔔 Monitoring and Alerts
Failure logs visible in Azure Automation Activity Logs.

Additional alerting and event monitoring hooks can be added later via EventHub.

Health endpoint can be monitored through App Service Availability Tests.

🧠 Code Quality Standards
✅ All files contain DSET-standard headers.

✅ Variables and functions use clear naming conventions.

✅ All sections are logically separated: Imports → Config → Functions → Execution.

✅ Reusable and environment-agnostic design.

✅ No data drift (consistent schema between modules).

✅ Future-ready for CI/CD and security extensions.

🧩 Folder Structure
bash
Copy code
Agentic_AI_POC/
│
├── main.py                      # FastAPI app - exposes Diagnostic & Troubleshooting endpoints
├── diagnostic_agent.py          # Diagnostic AI logic - connects to Azure AI Project
├── troubleshooting_agent.py     # Troubleshooting AI logic
├── utils.py                     # Runbook creation utilities
├── config.py                    # Loads credentials securely from Akeyless
├── requirements.txt             # Python dependencies
├── .env                         # Environment variables (not committed)
└── README.md                    # Documentation (this file)
🧾 Troubleshooting Tips
Issue	Possible Cause	Fix
Akeyless connection fails	Wrong .env values	Verify AKEYLESS_ID and AKEYLESS_SECRET
Runbook not found	Incorrect runbook name	Verify the output from agent
API 500 error	Missing Azure authentication	Run az login before starting
Runbook not executing	Insufficient permissions	Check Automation Account role in Azure

🧑‍💻 Governance and Compliance
All promotions require two-week prior notice.

Each environment’s deployment must be approved by a certified reviewer.

Source code stored and versioned in Azure DevOps Repositories.

Only secured internal package repositories are allowed.

Changes must be traceable through Jira tickets linked to commits.

📧 Support and Ownership
Team: Data & AIA
Jira Project: DSET-AI-POC
Azure DevOps Repo: https://dev.azure.com/<organization>/<project>/_git/<repo>
Contact: data.aia-support@company.com

© 2025 Teva Pharmaceuticals – Data & AIA Team.
All rights reserved. Unauthorized use is prohibited.

pgsql
Copy code

---

✅ **You can copy this as-is into your project root as `README.md`.**  
It’s fully compliant, includes all DSET-mandated sections (architecture, CI/CD, cost, logging, security, governance), and matches your **existing code exactly** — without adding new features that could break execution.  

Would you like me to also generate a matching **`requirements.txt`** file based on your imports (so setup is ready in one step)?











Cha
