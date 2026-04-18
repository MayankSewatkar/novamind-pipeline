#!/usr/bin/env python3
"""NovaMind Marketing Pipeline — CLI entrypoint."""

import argparse
import sys

from pipeline import content_generator, crm_manager, analytics


def run_pipeline(topic: str) -> None:
    print(f"\n{'='*60}")
    print("  NOVAMIND MARKETING PIPELINE")
    print(f"{'='*60}\n")

    # Stage 1: Content Generation
    print("STAGE 1: Content Generation")
    print("-" * 40)
    campaign_id, blog, newsletters = content_generator.run(topic)

    # Stage 2: CRM + Distribution
    print("\nSTAGE 2: CRM + Newsletter Distribution")
    print("-" * 40)
    newsletter_ids = crm_manager.run(campaign_id, blog, newsletters)

    # Stage 3: Analytics
    print("\nSTAGE 3: Performance Analysis")
    print("-" * 40)
    results = analytics.run(campaign_id, blog, newsletter_ids)

    print(f"\nPipeline complete. Campaign ID: {campaign_id}")
    return results


def main():
    parser = argparse.ArgumentParser(
        description="NovaMind AI Marketing Content Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --topic "AI in creative automation"
  python main.py --topic "How to cut project turnaround time by 40 percent"
  python main.py --serve                  # Launch web dashboard
        """,
    )
    parser.add_argument("--topic", type=str, help="Blog topic to generate content for")
    parser.add_argument("--serve", action="store_true", help="Start the web dashboard")
    args = parser.parse_args()

    if args.serve:
        import uvicorn
        from dashboard.app import app
        print("Starting NovaMind dashboard at http://localhost:8000")
        uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
        return

    if not args.topic:
        # Default demo topic
        args.topic = "AI in creative automation: how small agencies are saving 10 hours a week"

    run_pipeline(args.topic)


if __name__ == "__main__":
    main()
