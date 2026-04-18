#!/usr/bin/env python3
"""NovaMind Marketing Pipeline — CLI entrypoint."""

import argparse
import json
from pathlib import Path

from pipeline import content_generator, crm_manager, analytics
from config import CAMPAIGNS_DIR, CONTENT_DIR


def cmd_generate(topic: str) -> None:
    """Stage 1: generate content + register in HubSpot as draft. Waits for approval."""
    print(f"\n{'='*60}")
    print("  NOVAMIND · STAGE 1: GENERATE")
    print(f"{'='*60}\n")

    campaign_id, blog, newsletters = content_generator.run(topic)
    newsletter_ids = crm_manager.run(campaign_id, blog, newsletters)

    print(f"""
Content generated and saved. Campaign is PENDING APPROVAL.

Review the content:
  cat data/content/{campaign_id}/blog.json
  cat data/content/{campaign_id}/newsletters.json

When ready to send:
  python3 main.py --approve {campaign_id}

Or approve from the dashboard:
  python3 main.py --serve
""")


def cmd_approve(campaign_id: str) -> None:
    """Stage 2: approve a pending campaign — send emails + run analytics."""
    print(f"\n{'='*60}")
    print(f"  NOVAMIND · STAGE 2: APPROVE & SEND")
    print(f"{'='*60}\n")

    campaign_path = Path(CAMPAIGNS_DIR) / f"{campaign_id}.json"
    if not campaign_path.exists():
        print(f"ERROR: Campaign '{campaign_id}' not found in {CAMPAIGNS_DIR}")
        return

    campaign = json.loads(campaign_path.read_text())
    if campaign["status"] == "SENT":
        print(f"Campaign {campaign_id} is already SENT.")
        return

    # Load newsletters for email sending and feedback loop
    nl_path = Path(CONTENT_DIR) / campaign_id / "newsletters.json"
    newsletters = json.loads(nl_path.read_text()) if nl_path.exists() else {}

    blog_path = Path(CONTENT_DIR) / campaign_id / "blog.json"
    blog = json.loads(blog_path.read_text()) if blog_path.exists() else {"title": campaign["blog_title"]}

    newsletter_ids = crm_manager.approve_and_send(campaign_id, newsletters)

    print("\nRunning analytics...")
    analytics.run(campaign_id, blog, newsletter_ids, newsletters=newsletters)

    print(f"\nCampaign {campaign_id} complete.")


def cmd_list() -> None:
    """List all campaigns and their status."""
    p = Path(CAMPAIGNS_DIR)
    if not p.exists() or not list(p.glob("*.json")):
        print("No campaigns found.")
        return
    print(f"\n{'Campaign ID':<35} {'Status':<20} {'Title'}")
    print("-" * 90)
    for f in sorted(p.glob("*.json"), reverse=True):
        c = json.loads(f.read_text())
        print(f"{c['campaign_id']:<35} {c['status']:<20} {c['blog_title'][:45]}")


def main():
    parser = argparse.ArgumentParser(
        description="NovaMind AI Marketing Content Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Workflow:
  python3 main.py --generate "AI in creative automation"   # Stage 1: create + save as draft
  python3 main.py --list                                   # See pending campaigns
  python3 main.py --approve campaign_20260418_143022       # Stage 2: send + analyze
  python3 main.py --serve                                  # Web dashboard (all stages)

Legacy (auto-approve, skips review):
  python3 main.py --topic "AI in creative automation"
        """,
    )
    parser.add_argument("--generate", metavar="TOPIC", help="Generate content (awaits approval before sending)")
    parser.add_argument("--approve", metavar="CAMPAIGN_ID", help="Approve and send a pending campaign")
    parser.add_argument("--list", action="store_true", help="List all campaigns and their status")
    parser.add_argument("--topic", metavar="TOPIC", help="Run full pipeline immediately (no approval gate)")
    parser.add_argument("--serve", action="store_true", help="Start the web dashboard")
    args = parser.parse_args()

    if args.serve:
        import uvicorn
        print("Starting NovaMind dashboard at http://localhost:8000")
        uvicorn.run("dashboard.app:app", host="0.0.0.0", port=8000, reload=True)
        return

    if args.generate:
        cmd_generate(args.generate)
        return

    if args.approve:
        cmd_approve(args.approve)
        return

    if getattr(args, "list"):
        cmd_list()
        return

    # Legacy single-command path (auto-approve)
    topic = args.topic or "AI in creative automation: how small agencies are saving 10 hours a week"
    print(f"\n{'='*60}\n  NOVAMIND MARKETING PIPELINE (auto-approve)\n{'='*60}\n")
    campaign_id, blog, newsletters = content_generator.run(topic)
    newsletter_ids = crm_manager.run(campaign_id, blog, newsletters)
    crm_manager.approve_and_send(campaign_id, newsletters)
    analytics.run(campaign_id, blog, newsletter_ids, newsletters=newsletters)
    print(f"\nPipeline complete. Campaign ID: {campaign_id}")


if __name__ == "__main__":
    main()
