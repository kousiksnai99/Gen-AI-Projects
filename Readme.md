Agentic AI POC - Diagnostic & Troubleshooting API
=================================================

Overview
--------
This repository contains a FastAPI application that exposes Diagnostic and Troubleshooting agents backed
by Azure AI Projects and Azure Automation. The API allows generating runbooks and optionally creating/publishing
new runbooks into an Azure Automation Account.

Architecture & CI/CD
--------------------
- The architecture uses Azure AI Projects for LLM-based agents and Azure Automation for runbook management.
- CI/CD must supply environment-specific variables (MODEL_ENDPOINT, DIAGNOSTIC_AGENT_ID, SUBSCRIPTION_ID, etc).
- Use the ENVIRONMENT environment variable (dev/test/prod) for pipeline promotion.
- Ensure same repository name is used across Dev/Test/Prod (per client requirement).
- All promotions between environments must be performed by CI/CD with approval steps.
- Use Azure DevOps (https://dev.azure.com/) for repo, branches and pipeline definitions.

Operational / Security
----------------------
- DefaultAzureCredential is used (managed identity in production). If not available, pipeline or developer credentials should be set.
- Secrets may be retrieved from Akeyless (optional) or provided via environment variables in CI/CD.
- EventHub telemetry and logging are optional and configurable by environment variables.
- Authentication for the webapp should be configured externally (ENTRA ID / Azure AD). The API currently has no auth layer inside the code - CI/CD or deployment must enable ingress auth.

Ticketing / Code Review
-----------------------
- Create a Jira ticket for this work and reference it in the pipeline releases (client requirement).
- Code will be reviewed by external reviewers as part of promotion approvals.

Notes for Developers
--------------------
- All prints were removed; logging is used instead.
- Add or update environment variables in your pipeline for each environment.
- Replace any placeholder values in your CI/CD variable groups and secrets stores.

