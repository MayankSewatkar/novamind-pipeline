"""
Feedback loop: persist what content patterns drive engagement,
inject that knowledge into the next generation cycle.
"""

import json
from pathlib import Path
from datetime import datetime

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import DATA_DIR

MEMORY_PATH = Path(DATA_DIR) / "performance_memory.json"

_EMPTY = {
    "updated_at": None,
    "campaigns_analyzed": 0,
    "persona_trends": {},
    "top_subject_patterns": [],
    "top_cta_patterns": [],
    "underperforming_topics": [],
    "top_topics": [],
}


def load() -> dict:
    if MEMORY_PATH.exists():
        try:
            return json.loads(MEMORY_PATH.read_text())
        except json.JSONDecodeError:
            pass
    return dict(_EMPTY)


def update(blog: dict, newsletters: dict, metrics: dict) -> None:
    """
    After a campaign completes, extract what worked and persist it so the
    next content generation cycle can learn from it.
    """
    memory = load()
    memory["campaigns_analyzed"] = memory.get("campaigns_analyzed", 0) + 1
    memory["updated_at"] = datetime.utcnow().isoformat()

    # Per-persona rolling averages
    persona_trends = memory.setdefault("persona_trends", {})
    for persona_key, m in metrics.items():
        trend = persona_trends.setdefault(persona_key, {"open_rates": [], "click_rates": [], "unsub_rates": []})
        trend["open_rates"].append(m["open_rate"])
        trend["click_rates"].append(m["click_rate"])
        trend["unsub_rates"].append(m["unsubscribe_rate"])
        # Keep last 10 campaigns only
        for k in ("open_rates", "click_rates", "unsub_rates"):
            trend[k] = trend[k][-10:]
        trend["avg_open"] = round(sum(trend["open_rates"]) / len(trend["open_rates"]), 4)
        trend["avg_click"] = round(sum(trend["click_rates"]) / len(trend["click_rates"]), 4)
        trend["avg_unsub"] = round(sum(trend["unsub_rates"]) / len(trend["unsub_rates"]), 4)

    # Track subject lines that beat the persona's own average click rate
    top_subjects = memory.setdefault("top_subject_patterns", [])
    for persona_key, nl in newsletters.items():
        m = metrics.get(persona_key, {})
        persona_avg = persona_trends.get(persona_key, {}).get("avg_click", 0)
        if m.get("click_rate", 0) > persona_avg:
            entry = {
                "subject": nl.get("subject_line", ""),
                "cta": nl.get("cta_text", ""),
                "persona": persona_key,
                "click_rate": m["click_rate"],
            }
            top_subjects.append(entry)
    memory["top_subject_patterns"] = top_subjects[-15:]

    # Track blog topics by engagement tier
    best_persona = max(metrics, key=lambda p: metrics[p].get("click_rate", 0))
    best_click = metrics[best_persona].get("click_rate", 0)
    avg_all = sum(m.get("click_rate", 0) for m in metrics.values()) / max(len(metrics), 1)

    topic_entry = {"title": blog.get("title", ""), "tags": blog.get("tags", []), "avg_click": round(avg_all, 4)}
    if avg_all >= 0.10:
        tops = memory.setdefault("top_topics", [])
        tops.append(topic_entry)
        memory["top_topics"] = tops[-10:]
    elif avg_all < 0.06:
        under = memory.setdefault("underperforming_topics", [])
        under.append(topic_entry)
        memory["underperforming_topics"] = under[-10:]

    MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    MEMORY_PATH.write_text(json.dumps(memory, indent=2))
    print(f"[memory] Feedback loop updated → {MEMORY_PATH}")


def as_prompt_context() -> str:
    """Return a concise string summarizing past performance for Claude's system prompt."""
    memory = load()
    if not memory.get("campaigns_analyzed"):
        return ""

    lines = [f"PERFORMANCE MEMORY ({memory['campaigns_analyzed']} campaigns analyzed):"]

    trends = memory.get("persona_trends", {})
    if trends:
        lines.append("Persona engagement averages:")
        for persona, t in trends.items():
            lines.append(
                f"  {persona}: open={t.get('avg_open', 0):.1%} "
                f"click={t.get('avg_click', 0):.1%} "
                f"unsub={t.get('avg_unsub', 0):.1%}"
            )

    top_subjects = memory.get("top_subject_patterns", [])
    if top_subjects:
        lines.append("High-click subject lines (learn from these patterns):")
        for s in top_subjects[-5:]:
            lines.append(f"  [{s['persona']}] \"{s['subject']}\" → CTA: \"{s['cta']}\" ({s['click_rate']:.1%} CTR)")

    top_topics = memory.get("top_topics", [])
    if top_topics:
        lines.append("Top-performing blog topics:")
        for t in top_topics[-3:]:
            lines.append(f"  \"{t['title']}\" ({t['avg_click']:.1%} avg CTR)")

    under = memory.get("underperforming_topics", [])
    if under:
        lines.append("Underperforming topic areas to avoid:")
        for t in under[-3:]:
            lines.append(f"  \"{t['title']}\" ({t['avg_click']:.1%} avg CTR)")

    return "\n".join(lines)
