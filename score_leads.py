#!/usr/bin/env python3
"""Score HubSpot contacts against ICP.md with the OpenAI Decisions API (or Typesafe JEV).

Usage:
    python3 score_leads.py --dry-run --limit 10   # score, print, write nothing
    python3 score_leads.py                        # score every unscored contact
    python3 score_leads.py --rescore              # score every contact again
    python3 score_leads.py --model jev            # use JEV instead of OpenAI

Needs only the Python standard library. Reads keys from the environment or .env.
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).parent
HUBSPOT = "https://api.hubapi.com"

# Contact properties sent to the model. Add any custom property your CRM fills.
LEAD_PROPERTIES = [
    "firstname", "lastname", "jobtitle", "company", "industry",
    "numemployees", "country", "city", "hs_linkedin_url",
]

# Properties of the contact's primary company, also sent to the model.
COMPANY_PROPERTIES = [
    "name", "domain", "industry", "numberofemployees", "country", "city", "description",
]

# The four fit levels, lowest first. The model returns a weighted score from 0 to 3.
LEVELS = [
    ("no_fit", "No fit", "Fails a disqualifier, or matches none of the must-haves."),
    ("weak_fit", "Weak fit", "Matches one must-have. The other must-haves fail or are unknown."),
    ("partial_fit", "Partial fit", "Matches most must-haves, but one fails or is unknown."),
    ("strong_fit", "Strong fit", "Matches every must-have and no disqualifier."),
]

# Properties this script writes back to HubSpot. Created on the first run.
SCORE_PROPERTIES = [
    {"name": "ai_icp_fit", "label": "AI ICP fit", "type": "enumeration", "fieldType": "select",
     "options": [{"label": label, "value": value, "displayOrder": i}
                 for i, (value, label, _) in enumerate(LEVELS)]},
    {"name": "ai_icp_score", "label": "AI ICP score", "type": "number", "fieldType": "number"},
    {"name": "ai_icp_confidence", "label": "AI ICP confidence", "type": "number", "fieldType": "number"},
    {"name": "ai_icp_scored_at", "label": "AI ICP scored at", "type": "datetime", "fieldType": "date"},
]


def load_env():
    env_file = HERE / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip())


def request(method, url, token, body=None):
    req = urllib.request.Request(
        url, method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as err:
        return err.code, json.loads(err.read() or b"{}")


def ensure_score_properties(token):
    for prop in SCORE_PROPERTIES:
        status, body = request("POST", f"{HUBSPOT}/crm/v3/properties/contacts", token,
                               {**prop, "groupName": "contactinformation"})
        if status not in (201, 409):  # 409 = the property already exists
            sys.exit(f"Could not create property {prop['name']}: {status} {body}")


def fetch_contacts(token, rescore, limit):
    # Before the first real run the property does not exist, so every contact is unscored.
    status, _ = request("GET", f"{HUBSPOT}/crm/v3/properties/contacts/ai_icp_scored_at", token)
    scored_before = status == 200
    filters = [] if rescore or not scored_before else [
        {"propertyName": "ai_icp_scored_at", "operator": "NOT_HAS_PROPERTY"}]
    contacts, after = [], None
    while True:
        body = {"filterGroups": [{"filters": filters}] if filters else [],
                "properties": LEAD_PROPERTIES, "limit": 100}
        if after:
            body["after"] = after
        status, page = request("POST", f"{HUBSPOT}/crm/v3/objects/contacts/search", token, body)
        if status != 200:
            sys.exit(f"HubSpot search failed: {status} {page}")
        contacts += page["results"]
        after = page.get("paging", {}).get("next", {}).get("after")
        if not after or (limit and len(contacts) >= limit):
            return contacts[:limit] if limit else contacts


def attach_companies(token, contacts):
    """Add each contact's company properties under contact["company"]."""
    for i in range(0, len(contacts), 100):
        chunk = contacts[i:i + 100]
        status, links = request("POST", f"{HUBSPOT}/crm/v4/associations/contacts/companies/batch/read", token,
                                {"inputs": [{"id": c["id"]} for c in chunk]})
        if status not in (200, 207):
            sys.exit(f"HubSpot associations failed: {status} {links}")
        company_of = {r["from"]["id"]: r["to"][0]["toObjectId"] for r in links["results"] if r["to"]}
        ids = sorted({str(v) for v in company_of.values()})
        if not ids:
            continue
        status, companies = request("POST", f"{HUBSPOT}/crm/v3/objects/companies/batch/read", token,
                                    {"inputs": [{"id": i} for i in ids], "properties": COMPANY_PROPERTIES})
        if status not in (200, 207):
            sys.exit(f"HubSpot company read failed: {status} {companies}")
        by_id = {c["id"]: c["properties"] for c in companies["results"]}
        for c in chunk:
            c["company"] = by_id.get(str(company_of.get(c["id"])), {})


def describe(contact):
    props, company = contact["properties"], contact.get("company", {})
    lines = [f"{name}: {props[name]}" for name in LEAD_PROPERTIES if props.get(name)]
    lines += [f"company {name}: {company[name]}" for name in COMPANY_PROPERTIES if company.get(name)]
    return "\n".join(lines)


def score_openai(icp, lead):
    status, body = request("POST", "https://api.openai.com/v1/decisions", os.environ["OPENAI_API_KEY"], {
        "model": "gpt-6-luna",
        "input": lead,
        "questions": [{
            "type": "score",
            "name": "icp_fit",
            "instructions": f"How well does this lead match the ideal customer profile below?\n\n{icp}",
            "levels": [{"label": label, "description": desc} for _, label, desc in LEVELS],
        }],
    })
    if status != 200:
        raise RuntimeError(f"OpenAI {status}: {body}")
    answer = body["answers"][0]
    return answer["score"], answer["confidence"]


def score_jev(icp, lead):
    status, body = request("POST", "https://api.typesafe.ai/v1/systemone", os.environ["JEV_API_KEY"], {
        "model": "jev-latest",
        "state": f"Ideal customer profile:\n{icp}\n\nLead:\n{lead}",
        "questions": {"icp_fit": {
            "type": "score",
            "instructions": "How well does this lead match the ideal customer profile?",
            "criteria": [f"{label}: {desc}" for _, label, desc in LEVELS],
        }},
    })
    if status != 200:
        raise RuntimeError(f"JEV {status}: {body}")
    answer = body["answers"]["icp_fit"]
    return answer["score"], answer["confidence"]


def to_update(contact, score, confidence):
    return {"id": contact["id"], "properties": {
        "ai_icp_fit": LEVELS[round(score)][0],
        "ai_icp_score": round(score / (len(LEVELS) - 1) * 100),
        "ai_icp_confidence": round(confidence, 2),
        "ai_icp_scored_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", choices=["openai", "jev"], default="openai")
    parser.add_argument("--limit", type=int, default=0, help="score at most N contacts")
    parser.add_argument("--rescore", action="store_true", help="score contacts that already have a score")
    parser.add_argument("--dry-run", action="store_true", help="print the scores, write nothing to HubSpot")
    args = parser.parse_args()

    load_env()
    token = os.environ.get("HUBSPOT_TOKEN") or sys.exit("Set HUBSPOT_TOKEN (see README).")
    key = "OPENAI_API_KEY" if args.model == "openai" else "JEV_API_KEY"
    os.environ.get(key) or sys.exit(f"Set {key} (see README).")
    icp = (HERE / "ICP.md").read_text()
    score = score_openai if args.model == "openai" else score_jev

    if not args.dry_run:
        ensure_score_properties(token)
    contacts = fetch_contacts(token, args.rescore, args.limit)
    attach_companies(token, contacts)
    print(f"Scoring {len(contacts)} contacts with {args.model}...")

    def run(contact):
        try:
            return contact, *score(icp, describe(contact))
        except Exception as err:  # one failed lead must not stop the batch
            print(f"  skipped {contact['id']}: {err}", file=sys.stderr)
            return None

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = [r for r in pool.map(run, contacts) if r]

    updates = [to_update(*r) for r in results]
    for (contact, _, _), update in zip(results, updates):
        p, u = contact["properties"], update["properties"]
        lead = f"{p.get('jobtitle') or '?'} at {p.get('company') or '?'}"
        print(f"  {u['ai_icp_score']:>3}  {u['ai_icp_fit']:<12} {lead if len(lead) <= 52 else lead[:51] + '…'}")

    if args.dry_run:
        print("Dry run: nothing written to HubSpot.")
        return
    for i in range(0, len(updates), 100):
        status, body = request("POST", f"{HUBSPOT}/crm/v3/objects/contacts/batch/update", token,
                               {"inputs": updates[i:i + 100]})
        if status != 200:
            sys.exit(f"HubSpot update failed: {status} {body}")
    print(f"Wrote {len(updates)} scores to HubSpot.")


if __name__ == "__main__":
    main()
