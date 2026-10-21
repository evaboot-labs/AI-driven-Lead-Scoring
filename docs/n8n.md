# Run it in n8n

Import [`n8n/hubspot-ai-lead-scoring.json`](../n8n/hubspot-ai-lead-scoring.json) into n8n
(Workflows > Import from file). Add a **HubSpot Service Key** credential with your service
key and an **OpenAI** credential, paste your ICP into **Set your ICP**, then click
**Execute workflow**. It runs every morning at 8am once activated. The JSON is generated
by `n8n/build_workflow.py` from `ICP.md`.

Back to the [README](../README.md).
