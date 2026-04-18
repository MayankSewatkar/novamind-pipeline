"""Performance data simulation, storage, and AI-powered analysis."""

import json
import random
from datetime import datetime
from pathlib import Path

import anthropic

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import ANTHROPIC_API_KEY, CLAUDE_MODEL, PERSONAS, ANALYTICS_DIR, CAMPAIGNS_DIR
from pipeline import performance_memory

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# Baseline engagement rates — personas have realistic variance baked in
PERSONA_BASELINES = {
    "agency_owner":       {"open": (0.28, 0.38), "click": (0.06, 0.14), "unsub": (0.005, 0.015)},
    "creative_freelancer": {"open": (0.32, 0.45), "click": (0.08, 0.18), "unsub": (0.003, 0.010)},
    "marketing_manager":  {"open": (0.22, 0.35), "click": (0.05, 0.12), "unsub": (0.008, 0.020)},
}


def simulate_engagement(newsletter_ids: dict[str, str], recipients_per_persona: int = 3) -> dict:
    """Simulate engagement metrics for each persona newsletter."""
    metrics = {}
    for persona_key, email_id in newsletter_ids.items():
        baseline = PERSONA_BASELINES.get(persona_key, {"open": (0.25, 0.35), "click": (0.05, 0.12), "unsub": (0.005, 0.015)})
        open_rate = round(random.uniform(*baseline["open"]), 4)
        click_rate = round(random.uniform(*baseline["click"]), 4)
        unsub_rate = round(random.uniform(*baseline["unsub"]), 4)
        sent = recipients_per_persona
        metrics[persona_key] = {
            "email_id": email_id,
            "sent": sent,
            "opens": round(sent * open_rate),
            "clicks": round(sent * click_rate),
            "unsubscribes": max(0, round(sent * unsub_rate)),
            "open_rate": open_rate,
            "click_rate": click_rate,
            "unsubscribe_rate": unsub_rate,
        }
    return metrics


def load_historical(limit: int = 5) -> list[dict]:
    """Load the last N campaign analytics records for trend analysis."""
    analytics_path = Path(ANALYTICS_DIR)
    if not analytics_path.exists():
        return []
    files = sorted(analytics_path.glob("*.json"), reverse=True)[:limit]
    history = []
    for f in files:
        try:
            history.append(json.loads(f.read_text()))
        except json.JSONDecodeError:
            pass
    return history


def generate_ai_summary(campaign_id: str, blog_title: str, metrics: dict, history: list[dict]) -> str:
    """Ask Claude to write a performance summary + next-campaign recommendations."""
    metrics_text = json.dumps(metrics, indent=2)
    history_text = json.dumps(history[-3:], indent=2) if history else "No prior campaigns yet."

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=600,
        system=(
            "You are a growth analyst at NovaMind. Write crisp, data-forward performance summaries "
            "that highlight what worked, what didn't, and give 2-3 actionable next steps. "
            "Be specific — reference actual numbers from the data."
        ),
        messages=[
            {
                "role": "user",
                "content": f"""Analyze this newsletter campaign performance and provide recommendations.

Campaign: {campaign_id}
Blog title: {blog_title}

Current campaign metrics (by persona):
{metrics_text}

Historical campaigns (last 3):
{history_text}

Write a 150-200 word performance summary covering:
1. Which persona performed best and why
2. Any concerning signals (high unsub, low clicks)
3. 2-3 specific recommendations for the next campaign""",
            }
        ],
    )
    return response.content[0].text


def suggest_next_topics(history: list[dict]) -> list[str]:
    """Use Claude to suggest next blog topics based on engagement trends."""
    if not history:
        return ["How AI Is Reshaping Creative Agency Workflows in 2025"]

    history_text = json.dumps(history[-5:], indent=2)
    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=400,
        system="You are a content strategist specializing in AI and creative industry content.",
        messages=[
            {
                "role": "user",
                "content": f"""Based on these campaign performance trends, suggest 3 high-potential blog topics for NovaMind's next newsletter.

Historical data:
{history_text}

Return a JSON array of exactly 3 topic strings. No other text.""",
            }
        ],
    )
    raw = response.content[0].text.strip()
    import re
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return [line.strip("- •123. ") for line in raw.splitlines() if line.strip()][:3]


def save_analytics(campaign_id: str, blog_title: str, metrics: dict, summary: str) -> None:
    Path(ANALYTICS_DIR).mkdir(parents=True, exist_ok=True)
    record = {
        "campaign_id": campaign_id,
        "blog_title": blog_title,
        "recorded_at": datetime.utcnow().isoformat(),
        "metrics": metrics,
        "ai_summary": summary,
    }
    out = Path(ANALYTICS_DIR) / f"{campaign_id}.json"
    out.write_text(json.dumps(record, indent=2))
    print(f"[analytics] Saved → {out}")


def run(campaign_id: str, blog: dict, newsletter_ids: dict[str, str], newsletters: dict = None) -> dict:
    """Simulate engagement, generate AI summary, update feedback loop, persist."""
    print("[analytics] Simulating engagement metrics...")
    metrics = simulate_engagement(newsletter_ids)
    for p, m in metrics.items():
        print(f"  {PERSONAS[p]['name']}: open={m['open_rate']:.1%} click={m['click_rate']:.1%} unsub={m['unsubscribe_rate']:.1%}")

    history = load_historical()
    print("[analytics] Generating AI performance summary...")
    summary = generate_ai_summary(campaign_id, blog["title"], metrics, history)
    print(f"\n{'='*60}\nPERFORMANCE SUMMARY\n{'='*60}\n{summary}\n{'='*60}\n")

    save_analytics(campaign_id, blog["title"], metrics, summary)

    # Update feedback loop so the next generation cycle learns from this campaign
    if newsletters:
        performance_memory.update(blog, newsletters, metrics)

    print("[analytics] Suggesting next blog topics...")
    next_topics = suggest_next_topics(load_historical())
    print("Next topic suggestions:")
    for i, t in enumerate(next_topics, 1):
        print(f"  {i}. {t}")

    return {
        "campaign_id": campaign_id,
        "metrics": metrics,
        "summary": summary,
        "next_topics": next_topics,
    }
