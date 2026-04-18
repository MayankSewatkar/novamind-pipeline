"""Generates blog posts and persona-targeted newsletters using Claude."""

import json
import re
from datetime import datetime
from pathlib import Path

import anthropic

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import ANTHROPIC_API_KEY, CLAUDE_MODEL, PERSONAS, CONTENT_DIR


client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def _call_claude(system: str, user: str, max_tokens: int = 2048) -> str:
    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return response.content[0].text


def generate_blog(topic: str) -> dict:
    """Generate a blog outline + ~400-600 word draft on a given topic."""
    system = (
        "You are a senior content strategist at NovaMind, an AI startup helping small creative "
        "agencies automate their daily workflows. Write engaging, authoritative content that "
        "speaks to agency operators and creatives. Keep writing sharp and jargon-free."
    )
    user = f"""Write a blog post about: "{topic}"

Return valid JSON with exactly this structure:
{{
  "title": "compelling SEO-friendly title",
  "slug": "url-slug",
  "outline": ["Section 1 heading", "Section 2 heading", ...],
  "draft": "Full blog post draft (400-600 words, use markdown headings)",
  "meta_description": "155-char SEO meta description",
  "tags": ["tag1", "tag2", "tag3"]
}}"""

    raw = _call_claude(system, user, max_tokens=2048)
    # Strip markdown code fences if present
    raw = re.sub(r"^```(?:json)?\s*", "", raw.strip())
    raw = re.sub(r"\s*```$", "", raw.strip())
    data = json.loads(raw)
    data["topic"] = topic
    data["generated_at"] = datetime.utcnow().isoformat()
    return data


def generate_newsletters(blog: dict) -> dict:
    """Generate three persona-tailored newsletter versions from a blog post."""
    newsletters = {}

    system = (
        "You are a conversion-focused email copywriter at NovaMind. "
        "Write newsletter emails that feel personal and drive clicks — not corporate blasts."
    )

    for persona_key, persona in PERSONAS.items():
        user = f"""Write a short newsletter email promoting this blog post to the '{persona["name"]}' persona.

Persona profile:
- Description: {persona["description"]}
- Tone: {persona["tone"]}
- Pain points: {", ".join(persona["pain_points"])}

Blog post title: {blog["title"]}
Blog summary: {blog["meta_description"]}

Return valid JSON with exactly this structure:
{{
  "subject_line": "email subject (max 60 chars)",
  "preview_text": "preview snippet (max 90 chars)",
  "body": "email body in markdown (150-250 words, include a clear CTA)",
  "cta_text": "CTA button label",
  "persona": "{persona_key}"
}}"""

        raw = _call_claude(system, user, max_tokens=1024)
        raw = re.sub(r"^```(?:json)?\s*", "", raw.strip())
        raw = re.sub(r"\s*```$", "", raw.strip())
        newsletters[persona_key] = json.loads(raw)

    return newsletters


def save_content(blog: dict, newsletters: dict) -> str:
    """Persist blog + newsletters to disk, return campaign ID."""
    campaign_id = f"campaign_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
    out_dir = Path(CONTENT_DIR) / campaign_id
    out_dir.mkdir(parents=True, exist_ok=True)

    (out_dir / "blog.json").write_text(json.dumps(blog, indent=2))
    (out_dir / "newsletters.json").write_text(json.dumps(newsletters, indent=2))

    print(f"[content] Saved to {out_dir}")
    return campaign_id


def run(topic: str) -> tuple[str, dict, dict]:
    """Full content generation: blog + newsletters. Returns (campaign_id, blog, newsletters)."""
    print(f"[content] Generating blog for: '{topic}'")
    blog = generate_blog(topic)
    print(f"[content] Blog title: {blog['title']}")

    print("[content] Generating persona newsletters...")
    newsletters = generate_newsletters(blog)
    print(f"[content] Generated newsletters for: {list(newsletters.keys())}")

    campaign_id = save_content(blog, newsletters)
    return campaign_id, blog, newsletters
