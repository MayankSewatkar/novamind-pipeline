# NovaMind — AI-Powered Marketing Content Pipeline

**Live site:** https://mayanksewatkar.github.io/novamind-pipeline/

## What This Does (Plain English)

You type in a topic — say, *"AI tools for creative agencies"* — and the system does the rest automatically:

1. **Writes a blog post** — a fully drafted 400–600 word article with a headline, structure, and SEO description, ready to publish.
2. **Writes three different newsletter emails** — one for each audience type (agency owners, freelance creatives, and marketing managers), each with its own tone, angle, and subject line tailored to what that reader actually cares about.
3. **Holds for your approval** — nothing goes out until a human reviews and clicks "Approve & Send" in the web dashboard. You stay in control.
4. **Sends the emails** — delivers each version to the right audience segment.
5. **Reports on what worked** — after sending, it produces an AI-written performance summary: which audience opened and clicked the most, which showed warning signs, and exactly what to do differently next time.
6. **Gets smarter over time** — every campaign teaches the system what subject lines, topics, and calls-to-action drive the best results. The next blog it writes already knows what worked last time.

**What you get out of it:** a publish-ready blog post, three audience-specific newsletters, a campaign performance report, and three suggested topics for your next campaign — all from a single topic input, in minutes.

---

## What Makes This Different

Most AI content pipelines are one-shot: generate → send → forget. This one is designed to get smarter with every campaign. Three deliberate design choices set it apart:

### 1. Real Email Delivery via Resend
Every other pipeline in this category simulates sending. This one actually sends. [Resend](https://resend.com) integration (`pipeline/email_sender.py`) delivers HTML emails to real inboxes — free tier, no credit card. Resend's API returns delivery status per recipient so the system knows what was delivered vs bounced, not just what was "queued." No RESEND_API_KEY? The pipeline degrades gracefully and logs a skip — every other stage still runs.

### 2. A Feedback Loop That Closes
Engagement data doesn't just appear in a report — it feeds back into the *next* generation cycle. After every campaign, `pipeline/performance_memory.py` extracts which subject line patterns, CTA styles, and content topics drove the highest click rates for each persona, and writes them to `data/performance_memory.json`. The next time Claude generates a blog or newsletter, that memory is injected directly into the system prompt. Campaigns compound — early wins inform later content decisions automatically.

### 3. Human-in-the-Loop Approval Before Send
Content goes out in two stages, not one. `--generate` creates the blog and newsletters and saves them as `PENDING_APPROVAL` — nothing is sent. A human reviews the content (CLI or dashboard), then `--approve <id>` triggers actual delivery and analytics. The dashboard surfaces pending campaigns with a prominent "Approve & Send" button distinct from sent ones. This is the difference between a demo toy and a tool you'd trust with real contacts.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                            CLI / Web Dashboard                               │
│  python3 main.py --generate "topic"    →  saves as PENDING_APPROVAL         │
│  python3 main.py --approve <id>        →  sends + analyzes                  │
│  python3 main.py --serve               →  FastAPI dashboard (both stages)   │
└───────────────────────┬──────────────────────────────────────────────────────┘
                        │
          ┌─────────────▼─────────────┐         ┌─────────────────────────┐
          │   Stage 1: Content Gen    │         │   Performance Memory     │
          │  pipeline/content_generator         │  data/performance_memory │
          │  ─────────────────────    │◄────────│  .json                  │
          │  Claude claude-sonnet-4-6       │         │                         │
          │  • Blog outline + draft   │         │  Per-persona click/open  │
          │  • 3 persona newsletters  │         │  trends, top subject      │
          │  • Injects past winners   │         │  patterns, topic history  │
          │  • Save to data/content/  │         └────────────▲────────────┘
          └─────────────┬─────────────┘                      │ update()
                        │ PENDING_APPROVAL                   │
          ┌─────────────▼─────────────┐                      │
          │  Stage 2: CRM + Send      │         ┌────────────┴────────────┐
          │  pipeline/crm_manager     │         │   Stage 3: Analytics    │
          │  pipeline/email_sender    │────────►│  pipeline/analytics     │
          │  ─────────────────────    │  SENT   │  ─────────────────────  │
          │  HubSpot: upsert contacts │         │  Simulated engagement   │
          │  HubSpot: create drafts   │         │  Claude AI summary      │
          │  Resend: real delivery    │         │  Next topic suggestions │
          │  Log to data/campaigns/   │         │  Save to data/analytics/│
          └───────────────────────────┘         └─────────────────────────┘
```

### Personas

| Key | Name | Focus |
|-----|------|-------|
| `agency_owner` | Agency Owner | ROI, scaling, reducing overhead |
| `creative_freelancer` | Creative Freelancer | Practical tools, time savings |
| `marketing_manager` | Marketing Manager | Metrics, campaigns, reporting |

---

## Tools & APIs

| Layer | Tool |
|-------|------|
| AI Model | Anthropic Claude (`claude-sonnet-4-6`) via `anthropic` Python SDK |
| CRM | HubSpot (Contacts v3, Marketing Emails v3) |
| Email Delivery | Resend (real delivery, free tier, HTML templates) |
| Feedback Loop | `pipeline/performance_memory.py` → `data/performance_memory.json` |
| Web Dashboard | FastAPI + Jinja2 |
| Data Storage | Local JSON files under `data/` |
| Language | Python 3.11+ |

---

## Assumptions & Simplifications

- **Engagement data is simulated.** HubSpot's email send/analytics API requires a paid Marketing Hub account. The pipeline simulates realistic open/click/unsub rates per persona with per-persona baseline variance. Resend provides real delivery status; open/click tracking would require webhook endpoints (stub architecture is in place).
- **Mock contacts.** Nine contacts (3 per persona) are seeded into HubSpot on every run. Real runs dedup by email via HubSpot's 409 conflict response.
- **HubSpot email creation** requires Marketing Hub. If the token lacks that scope, the pipeline falls back to a mock ID and continues without crashing.
- **Resend free tier** uses `onboarding@resend.dev` as the from-address. A verified custom domain is needed for production from-addresses.
- **Storage** is local JSON — no database required.

---

## Local Setup

### 1. Clone & install

```bash
git clone https://github.com/MayankSewatkar/novamind-pipeline
cd novamind-pipeline
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env and add your keys
```

Required:
- `ANTHROPIC_API_KEY` — from [console.anthropic.com](https://console.anthropic.com)

Optional (each degrades gracefully if omitted):
- `HUBSPOT_ACCESS_TOKEN` — HubSpot Private App token with CRM + Marketing scopes
- `RESEND_API_KEY` — from [resend.com](https://resend.com) (free, no credit card)

### 3. Two-stage workflow (recommended)

```bash
# Stage 1: generate content, save as draft
python3 main.py --generate "AI in creative automation: how agencies save 10 hours a week"

# Review the draft
python3 main.py --list

# Stage 2: approve and send
python3 main.py --approve campaign_20260418_143022
```

### 4. Single-command (auto-approve, skips review)

```bash
python3 main.py --topic "AI in creative automation"
```

### 5. Launch the web dashboard

```bash
python3 main.py --serve
# Open http://localhost:8000
```

---

## Output Structure

```
data/
├── content/
│   └── campaign_20260418_143022/
│       ├── blog.json              # title, slug, outline, draft, tags
│       └── newsletters.json       # per-persona subject, preview, body, CTA
├── campaigns/
│   └── campaign_20260418_143022.json   # status, send log, HubSpot IDs
├── analytics/
│   └── campaign_20260418_143022.json   # metrics + AI summary + next topics
└── performance_memory.json             # rolling feedback loop across all campaigns
```
