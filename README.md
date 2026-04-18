# NovaMind — AI-Powered Marketing Content Pipeline

An end-to-end, mostly hands-free content automation system for NovaMind, a fictional AI startup serving small creative agencies. Give it a topic and it produces a blog post, three persona-targeted newsletters, distributes them via HubSpot, and generates an AI-powered performance report.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                         CLI / Web UI                             │
│               python main.py --topic "..."                       │
│               python main.py --serve  (FastAPI dashboard)        │
└───────────────────────┬──────────────────────────────────────────┘
                        │
          ┌─────────────▼─────────────┐
          │   Stage 1: Content Gen    │
          │  pipeline/content_generator│
          │  ─────────────────────    │
          │  Claude claude-sonnet-4-6       │
          │  • Blog outline + draft   │
          │  • 3 persona newsletters  │
          │  • Save to data/content/  │
          └─────────────┬─────────────┘
                        │
          ┌─────────────▼─────────────┐
          │  Stage 2: CRM + Distribute│
          │  pipeline/crm_manager     │
          │  ─────────────────────    │
          │  HubSpot API              │
          │  • Upsert contacts        │
          │  • Tag by persona         │
          │  • Create email per seg.  │
          │  • Log to data/campaigns/ │
          └─────────────┬─────────────┘
                        │
          ┌─────────────▼─────────────┐
          │  Stage 3: Analytics       │
          │  pipeline/analytics       │
          │  ─────────────────────    │
          │  Simulated engagement     │
          │  • Open / click / unsub   │
          │  • Claude AI summary      │
          │  • Next topic suggestions │
          │  • Save to data/analytics/│
          └───────────────────────────┘
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
| Web Dashboard | FastAPI + Jinja2 |
| Data Storage | Local JSON files under `data/` |
| Language | Python 3.11+ |

---

## Assumptions & Simplifications

- **Engagement data is simulated.** HubSpot's email send/analytics API requires a paid Marketing Hub account. The pipeline simulates realistic open/click/unsub rates per persona with per-persona baseline variance.
- **Mock contacts.** Nine contacts (3 per persona) are seeded into HubSpot on every run. Real runs dedup by email via HubSpot's 409 conflict response.
- **HubSpot email creation** requires Marketing Hub. If the token lacks that scope, the pipeline falls back to a mock ID and continues without crashing.
- **No email is physically sent.** HubSpot emails are created as `DRAFT` to avoid accidentally spamming test contacts.
- **Storage** is local JSON — no database required.

---

## Local Setup

### 1. Clone & install

```bash
git clone https://github.com/MayankSewatkar/novamind-pipeline
cd novamind-pipeline
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env and add your keys
```

Required:
- `ANTHROPIC_API_KEY` — from [console.anthropic.com](https://console.anthropic.com)

Optional (pipeline degrades gracefully without it):
- `HUBSPOT_ACCESS_TOKEN` — HubSpot Private App token with CRM + Marketing scopes

### 3. Run the CLI pipeline

```bash
python main.py --topic "AI in creative automation: how agencies save 10 hours a week"
```

### 4. Launch the web dashboard

```bash
python main.py --serve
# Open http://localhost:8000
```

---

## Output Structure

```
data/
├── content/
│   └── campaign_20260418_143022/
│       ├── blog.json          # title, slug, outline, draft, tags
│       └── newsletters.json   # per-persona subject, preview, body, CTA
├── campaigns/
│   └── campaign_20260418_143022.json   # send log + HubSpot IDs
└── analytics/
    └── campaign_20260418_143022.json   # metrics + AI summary + next topics
```

---

## Bonus Features Implemented

- **AI-driven next topic suggestions** — after every run, Claude analyzes historical performance and recommends 3 high-potential blog topics
- **Web dashboard** — view all campaigns, drill into blog + newsletters + metrics per campaign, trigger new runs from the UI
- **Graceful HubSpot degradation** — works end-to-end without a HubSpot token (uses mock IDs)
