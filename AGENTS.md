# Agent instructions

This repo scores HubSpot contacts against `ICP.md` with an AI decision model (the OpenAI Decisions API, or Typesafe JEV) and writes the fit back to HubSpot as four contact properties. When the user asks to score, qualify or rank their leads or contacts:

1. Follow the skill in `skills/score-leads/SKILL.md` step by step.
2. Check that `.env` has `HUBSPOT_TOKEN` and `OPENAI_API_KEY` (or `JEV_API_KEY` for `--model jev`). If one is missing, tell the user how to get it from `docs/setup.md` and stop.
3. Read `ICP.md`. If it still holds the example profile, ask the user for their own and rewrite the file first.
4. Run `python3 score_leads.py --dry-run --limit 20` and show the user the results as a table. Point out scores that look wrong, for example a likely competitor or a company outside the ICP.
5. Ask the user if the scores look right. If not, sharpen `ICP.md` and repeat step 4.
6. When the user agrees, run `python3 score_leads.py` (add `--rescore` if `ICP.md` changed since the last run).
7. Report how many contacts were scored, and how many landed in each fit level.

For n8n, see `docs/n8n.md`.

Confirm with the user before every call that saves, sends or changes anything: never write to HubSpot without the user's yes after a dry run. Never ask for or handle an API key in the chat: the user writes the keys into `.env`. Never commit `.env`.
