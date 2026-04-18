"""
Real email delivery via Resend (resend.com).
Free tier: 3,000 emails/month, no credit card required.
Requires a verified sending domain for production; falls back gracefully in dev.

To enable:
  1. Sign up at https://resend.com
  2. Add RESEND_API_KEY to your .env
  3. (Optional) Verify a domain for custom from-addresses
"""

import json
import sys
from pathlib import Path
from typing import Optional

import requests

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import RESEND_API_KEY, PERSONAS

RESEND_URL = "https://api.resend.com/emails"
# Resend's onboarding address works without domain verification (dev only)
DEFAULT_FROM = "NovaMind Team <onboarding@resend.dev>"


def _markdown_to_html(md: str) -> str:
    """Minimal markdown → HTML — keeps the dependency list lean."""
    import re
    html = md
    html = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html)
    html = re.sub(r"\*(.+?)\*", r"<em>\1</em>", html)
    html = re.sub(r"^# (.+)$", r"<h1>\1</h1>", html, flags=re.MULTILINE)
    html = re.sub(r"^## (.+)$", r"<h2>\1</h2>", html, flags=re.MULTILINE)
    html = re.sub(r"^### (.+)$", r"<h3>\1</h3>", html, flags=re.MULTILINE)
    paragraphs = re.split(r"\n{2,}", html.strip())
    html = "".join(
        p if p.startswith("<h") else f"<p>{p.replace(chr(10), '<br>')}</p>"
        for p in paragraphs
    )
    return html


def _build_html(newsletter: dict, persona_key: str) -> str:
    body_html = _markdown_to_html(newsletter.get("body", ""))
    cta = newsletter.get("cta_text", "Read the blog")
    persona_name = PERSONAS[persona_key]["name"]
    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: #f4f4f5; margin: 0; padding: 32px 16px; }}
    .wrap {{ max-width: 580px; margin: 0 auto; background: white;
             border-radius: 12px; overflow: hidden; box-shadow: 0 2px 12px rgba(0,0,0,.08); }}
    .header {{ background: linear-gradient(135deg, #6c3de8, #a855f7);
               padding: 28px 32px; color: white; }}
    .header h1 {{ margin: 0; font-size: 1.1rem; font-weight: 700; }}
    .header p {{ margin: 4px 0 0; font-size: 0.8rem; opacity: 0.8; }}
    .body {{ padding: 28px 32px; color: #1e293b; font-size: 0.92rem; line-height: 1.7; }}
    .cta {{ display: block; margin: 24px auto; width: fit-content;
            background: #7c3aed; color: white; padding: 12px 28px;
            border-radius: 8px; text-decoration: none; font-weight: 600; }}
    .footer {{ padding: 16px 32px; font-size: 0.75rem; color: #94a3b8;
               text-align: center; border-top: 1px solid #f1f5f9; }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="header">
      <h1>NovaMind Weekly</h1>
      <p>For {persona_name}s</p>
    </div>
    <div class="body">
      {body_html}
      <a class="cta" href="https://novamind.ai/blog">{cta}</a>
    </div>
    <div class="footer">
      You're receiving this because you're part of the NovaMind {persona_name} list.<br>
      <a href="https://novamind.ai/unsubscribe" style="color:#7c3aed">Unsubscribe</a>
    </div>
  </div>
</body>
</html>"""


def send(
    to_email: str,
    newsletter: dict,
    persona_key: str,
    from_address: Optional[str] = None,
) -> dict:
    """
    Send one newsletter email via Resend. Returns Resend response dict.
    Falls back gracefully if RESEND_API_KEY is not set.
    """
    if not RESEND_API_KEY:
        print(f"  [email] No RESEND_API_KEY — skipping send to {to_email} (set key to enable real delivery)")
        return {"id": None, "status": "skipped_no_key"}

    payload = {
        "from": from_address or DEFAULT_FROM,
        "to": [to_email],
        "subject": newsletter["subject_line"],
        "html": _build_html(newsletter, persona_key),
        "headers": {
            "X-NovaMind-Persona": persona_key,
        },
    }
    try:
        resp = requests.post(
            RESEND_URL,
            headers={"Authorization": f"Bearer {RESEND_API_KEY}", "Content-Type": "application/json"},
            json=payload,
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        print(f"  [email] Sent to {to_email} → Resend id={data.get('id')}")
        return data
    except requests.HTTPError as e:
        print(f"  [email] Resend error for {to_email}: {e.response.text}")
        return {"id": None, "status": "error", "detail": e.response.text}


def send_campaign(contacts_by_persona: dict, newsletters: dict) -> dict[str, list[dict]]:
    """
    Send each persona's newsletter to their contacts.
    contacts_by_persona: {persona_key: [{"email": ..., "firstname": ...}, ...]}
    Returns {persona_key: [send_result, ...]}
    """
    results: dict[str, list[dict]] = {}
    for persona_key, contacts in contacts_by_persona.items():
        nl = newsletters.get(persona_key)
        if not nl:
            continue
        persona_results = []
        for contact in contacts:
            result = send(contact["email"], nl, persona_key)
            result["recipient"] = contact["email"]
            persona_results.append(result)
        results[persona_key] = persona_results
        sent = sum(1 for r in persona_results if r.get("id") or r.get("status") == "skipped_no_key")
        print(f"  [email] {persona_key}: {sent}/{len(contacts)} processed")
    return results
