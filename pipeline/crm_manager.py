"""HubSpot CRM integration — contacts, segmentation, and campaign logging."""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import requests

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import HUBSPOT_ACCESS_TOKEN, PERSONAS, CAMPAIGNS_DIR

BASE_URL = "https://api.hubapi.com"
HEADERS = {
    "Authorization": f"Bearer {HUBSPOT_ACCESS_TOKEN}",
    "Content-Type": "application/json",
}

# Mock contacts seeded per persona for demo purposes
MOCK_CONTACTS = {
    "agency_owner": [
        {"email": "sarah.chen@pixelcraft.io", "firstname": "Sarah", "lastname": "Chen", "company": "PixelCraft Studio"},
        {"email": "marcus.r@brandflow.co", "firstname": "Marcus", "lastname": "Rivera", "company": "BrandFlow Agency"},
        {"email": "priya.k@createhub.com", "firstname": "Priya", "lastname": "Kapoor", "company": "CreateHub"},
    ],
    "creative_freelancer": [
        {"email": "alex.m@freelance.design", "firstname": "Alex", "lastname": "Morgan", "company": "Independent"},
        {"email": "jamie.l@colorwave.art", "firstname": "Jamie", "lastname": "Lee", "company": "Colorwave"},
        {"email": "taylor.w@motioncraft.io", "firstname": "Taylor", "lastname": "Walsh", "company": "Independent"},
    ],
    "marketing_manager": [
        {"email": "diana.f@nexusagency.com", "firstname": "Diana", "lastname": "Foster", "company": "Nexus Agency"},
        {"email": "rob.n@launchpad.co", "firstname": "Rob", "lastname": "Nguyen", "company": "Launchpad Creative"},
        {"email": "chloe.b@vividmedia.io", "firstname": "Chloe", "lastname": "Barnes", "company": "Vivid Media"},
    ],
}


def _hs_post(path: str, payload: dict) -> dict:
    resp = requests.post(f"{BASE_URL}{path}", headers=HEADERS, json=payload, timeout=15)
    resp.raise_for_status()
    return resp.json()


def _hs_get(path: str, params: Optional[dict] = None) -> dict:
    resp = requests.get(f"{BASE_URL}{path}", headers=HEADERS, params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()


def upsert_contact(contact_data: dict, persona_key: str) -> str:
    """Create or update a contact in HubSpot; returns HubSpot contact ID."""
    payload = {
        "properties": {
            "email": contact_data["email"],
            "firstname": contact_data["firstname"],
            "lastname": contact_data["lastname"],
            "company": contact_data.get("company", ""),
            "novamind_persona": persona_key,
            "hs_lead_status": "NEW",
        }
    }
    try:
        result = _hs_post("/crm/v3/objects/contacts", payload)
        contact_id = result["id"]
        print(f"  [crm] Created contact {contact_data['email']} → id={contact_id}")
        return contact_id
    except requests.HTTPError as e:
        if e.response.status_code == 409:
            # Contact exists — extract id from conflict response
            existing_id = e.response.json().get("message", "").split("with ID: ")[-1].strip()
            print(f"  [crm] Contact exists {contact_data['email']} → id={existing_id}")
            return existing_id
        raise


def seed_contacts() -> dict[str, list[str]]:
    """Upsert all mock contacts into HubSpot; returns {persona: [contact_ids]}."""
    persona_contact_ids: dict[str, list[str]] = {}
    for persona_key, contacts in MOCK_CONTACTS.items():
        ids = []
        print(f"[crm] Seeding {len(contacts)} contacts for persona '{persona_key}'")
        for c in contacts:
            cid = upsert_contact(c, persona_key)
            ids.append(cid)
        persona_contact_ids[persona_key] = ids
    return persona_contact_ids


def create_email_campaign(newsletter: dict, persona_key: str, blog_title: str) -> str:
    """
    Create a Marketing Email in HubSpot for one persona newsletter.
    Returns the HubSpot email ID.
    """
    persona_name = PERSONAS[persona_key]["name"]
    payload = {
        "name": f"[NovaMind] {blog_title[:60]} — {persona_name}",
        "subject": newsletter["subject_line"],
        "previewText": newsletter["preview_text"],
        "fromName": "NovaMind Team",
        "replyTo": "hello@novamind.ai",
        "content": {
            "body": newsletter["body"],
        },
        "state": "DRAFT",
        "campaign": f"novamind-weekly-{datetime.now(timezone.utc).strftime('%Y%m')}",
        "customProperties": {
            "persona_segment": persona_key,
        },
    }
    try:
        result = _hs_post("/marketing/v3/emails", payload)
        email_id = str(result.get("id", f"mock_{uuid.uuid4().hex[:8]}"))
        print(f"  [crm] Created HubSpot email id={email_id} for persona '{persona_key}'")
        return email_id
    except Exception as e:
        # Fall back to mock ID so pipeline continues without a live HubSpot account
        mock_id = f"mock_{uuid.uuid4().hex[:8]}"
        print(f"  [crm] HubSpot email creation failed ({e}); using mock id={mock_id}")
        return mock_id


def log_campaign(campaign_id: str, blog: dict, newsletter_ids: dict[str, str]) -> None:
    """Persist campaign metadata to local JSON as the CRM campaign log."""
    Path(CAMPAIGNS_DIR).mkdir(parents=True, exist_ok=True)
    log = {
        "campaign_id": campaign_id,
        "blog_title": blog["title"],
        "blog_slug": blog.get("slug", ""),
        "send_date": datetime.utcnow().isoformat(),
        "newsletter_ids": newsletter_ids,
        "status": "SENT",
    }
    log_path = Path(CAMPAIGNS_DIR) / f"{campaign_id}.json"
    log_path.write_text(json.dumps(log, indent=2))
    print(f"[crm] Campaign logged → {log_path}")


def run(campaign_id: str, blog: dict, newsletters: dict) -> dict[str, str]:
    """Seed contacts, create per-persona emails, log campaign. Returns newsletter_ids map."""
    seed_contacts()

    newsletter_ids: dict[str, str] = {}
    for persona_key, newsletter in newsletters.items():
        email_id = create_email_campaign(newsletter, persona_key, blog["title"])
        newsletter_ids[persona_key] = email_id

    log_campaign(campaign_id, blog, newsletter_ids)
    return newsletter_ids
