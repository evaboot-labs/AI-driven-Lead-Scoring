"""Build the n8n template JSON for this workflow. Run: python3 n8n/build_workflow.py"""
import json
import uuid
from pathlib import Path

HERE = Path(__file__).parent
ICP = (HERE.parent / "ICP.md").read_text()
HUBSPOT_CRED = {"hubspotAppToken": {"id": "", "name": "HubSpot service key"}}
OPENAI_CRED = {"openAiApi": {"id": "", "name": "OpenAI"}}


def node(name, type_, version, position, parameters, **extra):
    return {"id": str(uuid.uuid5(uuid.NAMESPACE_URL, name)), "name": name, "type": type_,
            "typeVersion": version, "position": position, "parameters": parameters, **extra}


def sticky(name, position, width, height, content, color=7):
    return node(name, "n8n-nodes-base.stickyNote", 1, position,
                {"color": color, "width": width, "height": height, "content": content})


def http(name, position, method, url, cred_type, body=None, **extra):
    params = {"method": method, "url": url, "authentication": "predefinedCredentialType",
              "nodeCredentialType": cred_type, "options": {}}
    if body is not None:
        params.update({"sendBody": True, "specifyBody": "json", "jsonBody": body})
    creds = HUBSPOT_CRED if cred_type == "hubspotAppToken" else OPENAI_CRED
    return node(name, "n8n-nodes-base.httpRequest", 4.2, position, params, credentials=creds, **extra)


DESCRIBE_LEAD = """// Turn the contact and its company into the text the model reads.
const contact = $('One contact per item').item.json;
const company = $json.properties || {};
const p = contact.properties;
const lines = [
  ['Job title', p.jobtitle], ['Company', p.company], ['Industry', p.industry],
  ['Location', p.country], ['City', p.city],
  ['Company domain', company.domain], ['Company industry', company.industry],
  ['Company employees', company.numberofemployees], ['Company location', company.country],
  ['Company description', company.description],
].filter(([, v]) => v).map(([k, v]) => `${k}: ${v}`);
return { id: contact.id, name: `${p.firstname || ''} ${p.lastname || ''}`.trim(), lead: lines.join('\\n') };"""

DECISION_BODY = """={{ JSON.stringify({
  model: 'gpt-6-luna',
  input: $json.lead,
  questions: [{
    type: 'score',
    name: 'icp_fit',
    instructions: 'How well does this lead match the ideal customer profile below?\\n\\n' + $('Set your ICP').first().json.icp,
    levels: [
      { label: 'No fit', description: 'Fails a disqualifier, or matches none of the must-haves.' },
      { label: 'Weak fit', description: 'Matches one must-have. The other must-haves fail or are unknown.' },
      { label: 'Partial fit', description: 'Matches most must-haves, but one fails or is unknown.' },
      { label: 'Strong fit', description: 'Matches every must-have and no disqualifier.' }
    ]
  }]
}) }}"""

MAP_SCORE = """// Decision score is 0-3. Store the label, a 0-100 score and the confidence.
const answer = $json.answers[0];
const fits = ['no_fit', 'weak_fit', 'partial_fit', 'strong_fit'];
return {
  id: $('Describe the lead').item.json.id,
  properties: {
    ai_icp_fit: fits[Math.round(answer.score)],
    ai_icp_score: Math.round(answer.score / 3 * 100),
    ai_icp_confidence: Math.round(answer.confidence * 100) / 100,
    ai_icp_scored_at: new Date().toISOString().slice(0, 19) + 'Z',
  },
};"""

CREATE_PROPERTIES = json.dumps({"inputs": [
    {"name": "ai_icp_fit", "label": "AI ICP fit", "type": "enumeration", "fieldType": "select",
     "groupName": "contactinformation", "options": [
         {"label": l, "value": v, "displayOrder": i} for i, (v, l) in enumerate(
             [("no_fit", "No fit"), ("weak_fit", "Weak fit"), ("partial_fit", "Partial fit"), ("strong_fit", "Strong fit")])]},
    {"name": "ai_icp_score", "label": "AI ICP score", "type": "number", "fieldType": "number", "groupName": "contactinformation"},
    {"name": "ai_icp_confidence", "label": "AI ICP confidence", "type": "number", "fieldType": "number", "groupName": "contactinformation"},
    {"name": "ai_icp_scored_at", "label": "AI ICP scored at", "type": "datetime", "fieldType": "date", "groupName": "contactinformation"},
]}, indent=2)

SEARCH_BODY = """={{ JSON.stringify({
  filterGroups: [{ filters: [{ propertyName: 'ai_icp_scored_at', operator: 'NOT_HAS_PROPERTY' }] }],
  properties: ['firstname', 'lastname', 'jobtitle', 'company', 'industry', 'country', 'city'],
  limit: 100
}) }}"""

OVERVIEW = f"""## Score HubSpot leads against your ICP with AI

**Who it's for:** sales teams that keep their leads in HubSpot and want every new contact ranked by how well it fits their ideal customer profile.

**What it does:** every morning, the workflow finds HubSpot contacts with no score yet. For each one it reads the contact and its company, and asks the OpenAI Decisions API one question: how well does this lead match your ICP? It writes four properties back to the contact: **AI ICP fit** (No / Weak / Partial / Strong fit), **AI ICP score** (0-100), **AI ICP confidence** and **AI ICP scored at**.

### How to set up
1. Add credentials: **HubSpot Service Key** (paste a HubSpot service key with the scopes `crm.objects.contacts.read`, `crm.objects.contacts.write`, `crm.schemas.contacts.write`, `crm.objects.companies.read`) and **OpenAI**.
2. Paste your ideal customer profile into **Set your ICP**. Start from the ICP.md template in the GitHub repo.
3. Click **Execute workflow** once to test, then activate it.

### Requirements
HubSpot (the free plan works), an OpenAI API key.

### How to customize
Send more fields to the model in **Describe the lead**. Change the four fit levels in **Score against ICP**. The same workflow as a Python script with agent instructions: github.com/evaboot-labs/AI-driven-Lead-Scoring"""

nodes = [
    sticky("Template overview", [-760, -300], 520, 860, OVERVIEW),
    sticky("Step 1", [-180, -120], 660, 420,
           "### 1. Prepare\nRuns every morning. Creates the four AI ICP properties in HubSpot (an error on later runs only means they already exist), then loads your ICP."),
    sticky("Step 2", [520, -120], 900, 420,
           "### 2. Find unscored contacts\nHubSpot search returns up to 100 contacts with no **AI ICP scored at** yet. Each contact's company is read, because size, industry and location usually live on the company."),
    sticky("Step 3", [1460, -120], 900, 420,
           "### 3. Score and write back\nThe OpenAI Decisions API answers one `score` question with four levels and a confidence. The result is written to the contact. Sort HubSpot by **AI ICP score**, not only by the fit label: 80 can still be Partial fit."),
    node("Every morning at 8am", "n8n-nodes-base.scheduleTrigger", 1.2, [-140, -20],
         {"rule": {"interval": [{"field": "days", "triggerAtHour": 8}]}}),
    node("Test run", "n8n-nodes-base.manualTrigger", 1, [-140, 160], {}),
    http("Create score properties", [60, 60], "POST",
         "https://api.hubapi.com/crm/v3/properties/contacts/batch/create", "hubspotAppToken",
         "=" + CREATE_PROPERTIES, onError="continueRegularOutput"),
    node("Set your ICP", "n8n-nodes-base.set", 3.4, [260, 60], {
        "mode": "manual",
        "assignments": {"assignments": [{"id": "icp", "name": "icp", "type": "string", "value": ICP}]},
        "options": {}}, executeOnce=True),
    http("Find unscored contacts", [560, 60], "POST",
         "https://api.hubapi.com/crm/v3/objects/contacts/search", "hubspotAppToken", SEARCH_BODY),
    node("One contact per item", "n8n-nodes-base.splitOut", 1, [760, 60], {"fieldToSplitOut": "results", "options": {}}),
    http("Get company ID", [960, 60], "GET",
         "=https://api.hubapi.com/crm/v4/objects/contacts/{{ $json.id }}/associations/companies", "hubspotAppToken"),
    http("Get company", [1160, 60], "GET",
         "=https://api.hubapi.com/crm/v3/objects/companies/{{ $json.results[0]?.toObjectId }}?properties=domain,industry,numberofemployees,country,description",
         "hubspotAppToken", onError="continueRegularOutput", alwaysOutputData=True),
    node("Describe the lead", "n8n-nodes-base.code", 2, [1500, 60], {"mode": "runOnceForEachItem", "jsCode": DESCRIBE_LEAD}),
    http("Score against ICP", [1700, 60], "POST", "https://api.openai.com/v1/decisions", "openAiApi", DECISION_BODY),
    node("Map the score", "n8n-nodes-base.code", 2, [1900, 60], {"mode": "runOnceForEachItem", "jsCode": MAP_SCORE}),
    http("Write score to HubSpot", [2100, 60], "PATCH",
         "=https://api.hubapi.com/crm/v3/objects/contacts/{{ $json.id }}", "hubspotAppToken",
         "={{ JSON.stringify({ properties: $json.properties }) }}"),
]

order = ["Every morning at 8am", "Create score properties", "Set your ICP", "Find unscored contacts",
         "One contact per item", "Get company ID", "Get company", "Describe the lead",
         "Score against ICP", "Map the score", "Write score to HubSpot"]
connections = {a: {"main": [[{"node": b, "type": "main", "index": 0}]]} for a, b in zip(order, order[1:])}
connections["Test run"] = connections["Every morning at 8am"]

workflow = {"name": "Score HubSpot leads against your ICP with AI", "nodes": nodes,
            "connections": connections, "settings": {"executionOrder": "v1"}}
out = HERE / "hubspot-ai-lead-scoring.json"
out.write_text(json.dumps(workflow, indent=2, ensure_ascii=False) + "\n")
print(f"Wrote {out} ({len(nodes)} nodes)")
