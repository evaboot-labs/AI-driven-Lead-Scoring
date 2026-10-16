---
name: score-leads
description: Score HubSpot contacts against ICP.md with an AI decision model and write the fit back to HubSpot. Use when the user asks to score, qualify or rank their leads or contacts.
---

1. Check that `.env` has `HUBSPOT_TOKEN` and `OPENAI_API_KEY` (or `JEV_API_KEY` for `--model jev`). If one is missing, tell the user how to get it from README.md and stop.
2. Read `ICP.md`. If it still holds the example profile, ask the user for their own and rewrite the file first.
3. Run `python3 score_leads.py --dry-run --limit 20` and show the user the results as a table.
4. Ask the user if the scores look right. If not, sharpen `ICP.md` and repeat step 3.
5. When the user agrees, run `python3 score_leads.py` (add `--rescore` if `ICP.md` changed since the last run).
6. Report how many contacts were scored, and how many landed in each fit level.
