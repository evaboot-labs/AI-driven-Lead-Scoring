# Set up and run the script

## Install

You need Python 3.9 or later. No packages to install.

1. **Get a HubSpot service key.** In HubSpot, open Development > Keys > Service Keys and
   click **Create service key**. Name it, then add these five scopes:
   `crm.objects.contacts.read`, `crm.objects.contacts.write`,
   `crm.schemas.contacts.read`, `crm.schemas.contacts.write`,
   `crm.objects.companies.read`.
   Click **Create**, then **Show** to copy the key (it starts with `pat-`).
   Service keys replace the old private apps, which HubSpot now calls legacy apps.
2. **Get an OpenAI key** at https://platform.openai.com/api-keys.
3. **Copy the env file** and fill it in:
   ```bash
   cp .env.example .env
   ```
4. **Write your ICP.** Replace the example in [`ICP.md`](../ICP.md) with your own profile.

## Run

Test on 10 contacts without writing anything:

```bash
python3 score_leads.py --dry-run --limit 10
```

```
Scoring 10 contacts with openai...
   12  no_fit       Salesperson at HubSpot
   54  partial_fit  Head of Sales, Israel at Upwind Security
   43  weak_fit     Head of Sales - SDS at Enhesa
   71  partial_fit  VP Sales, Sierra Pacific at Intelligent Technical Solutions
    7  no_fit       Head of CRM at Danske Spil
   ...
Dry run: nothing written to HubSpot.
```

If the scores look right, score every unscored contact:

```bash
python3 score_leads.py
```

| Option | Does |
|---|---|
| `--dry-run` | Prints the scores, writes nothing |
| `--limit N` | Scores at most N contacts |
| `--rescore` | Scores contacts that already have a score, for example after you change `ICP.md` |
| `--model jev` | Uses Typesafe JEV instead of OpenAI |

HubSpot's search index updates a few seconds after a write. If you run the script twice
in a row, the second run can score the same contacts again. Wait a minute between runs.

## The four HubSpot properties

The script creates these contact properties on its first run:

| Property | Example | Meaning |
|---|---|---|
| `ai_icp_fit` | Partial fit | No fit, Weak fit, Partial fit, or Strong fit |
| `ai_icp_score` | 68 | 0 to 100 |
| `ai_icp_confidence` | 0.73 | How sure the model is, 0 to 1 |
| `ai_icp_scored_at` | 2026-10-16 | When the contact was scored |

## How it works

```
Sales Navigator ──Evaboot──> HubSpot contacts ──> score_leads.py ──> HubSpot properties
                                                       │
                                     ICP.md + lead ──> OpenAI Decisions API (or JEV)
```

1. The script asks HubSpot for every contact that has no `ai_icp_scored_at` yet.
2. For each contact it sends the lead's details and `ICP.md` to a decision model, as a
   `score` question with four levels.
3. It writes the fit, score and confidence back to the contact in batches of 100.

A decision model returns a fixed answer with a probability, not free text. It is faster,
cheaper and more consistent than a chat model for a yes/no or score task, and the
confidence tells you which leads need a human look.

## Use JEV instead of OpenAI

[JEV](https://typesafe.ai/blog/introducing-system-one-models-and-jev) from Typesafe is a
decision model like OpenAI's, and in our tests it answered in about 0.3 seconds instead
of about 2. It costs $0.042 per million input tokens against OpenAI's $0.10. Access is by
waitlist at https://console.typesafe.ai. When you have a key, add `JEV_API_KEY` to `.env`
and run with `--model jev`.

## Which HubSpot fields are sent

The script sends the contact properties in `LEAD_PROPERTIES` (name, job title, company,
industry, employee count, country, city, LinkedIn URL) and the properties of the
contact's company in `COMPANY_PROPERTIES` (name, domain, industry, employee count,
country, city, description). Add any other property's internal name to those lists.

**The score is only as good as these fields.** If industry or country is empty, the model
cannot confirm those must-haves, and almost no lead reaches Strong fit. Fill them before
you score. An [Evaboot](https://evaboot.com) export of a Sales Navigator search includes
Company Industry, Company Employee Exact Count, Company Location and Sales Team Size for
every lead. Map those columns to HubSpot properties on the Evaboot HubSpot mapping page
(dash.evaboot.com/dash/integrations/hubspot/mapping/) before you push the export.

HubSpot's company **Industry** property is a fixed list of 148 values, and LinkedIn
industry names are not on it, so HubSpot drops them. Map **Profile Industry** to the
contact's Industry (free text), or map **Company Industry** to a custom single-line text
company property.


Back to the [README](../README.md).
