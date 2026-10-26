# Run it in n8n

Import [`n8n/hubspot-ai-lead-scoring.json`](../n8n/hubspot-ai-lead-scoring.json) into n8n
(Workflows > Import from file). Add a **HubSpot Service Key** credential with your service
key and an **OpenAI** credential, paste your ICP into **Set your ICP**, then click
**Execute workflow**. It runs every morning at 8am once activated. The JSON is generated
by `n8n/build_workflow.py` from `ICP.md`.

Back to the [README](../README.md).

## Use JEV instead of OpenAI

If you have a [Typesafe JEV](https://typesafe.ai) key, import [`n8n/hubspot-ai-lead-scoring-jev.json`](../n8n/hubspot-ai-lead-scoring-jev.json) instead. It asks the same
question with the same four fit levels. Its **Score against ICP** node uses a **Header Auth**
credential: name `Authorization`, value `Bearer YOUR_JEV_API_KEY`. The template is pinned to
`jev-1.14.0`, so a new JEV release does not move your scores.
