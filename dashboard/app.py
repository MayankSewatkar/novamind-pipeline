"""FastAPI web dashboard for the NovaMind pipeline."""

import json
import sys
from pathlib import Path

import anthropic as anthropic_lib
from fastapi import FastAPI, Request, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import ANALYTICS_DIR, ANTHROPIC_API_KEY, CAMPAIGNS_DIR, CLAUDE_MODEL, CONTENT_DIR
from pipeline import content_generator, crm_manager, analytics as analytics_module

app = FastAPI(title="NovaMind Pipeline Dashboard")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)


# ── JSON API models ────────────────────────────────────────────────────────────

class GenerateRequest(BaseModel):
    topic: str
    tone: str = "professional"


class AnalyzeRequest(BaseModel):
    campaign_name: str
    open_rate: int
    click_rate: int
    sent: int
    unsub: int
    persona_clicks: dict


# ── JSON API endpoints ─────────────────────────────────────────────────────────

@app.post("/api/generate-content")
async def api_generate_content(body: GenerateRequest):
    blog = content_generator.generate_blog(body.topic)
    newsletters = content_generator.generate_newsletters(blog)

    def fmt(nl: dict) -> str:
        return f"Subject: {nl.get('subject_line', '')}\nPreview: {nl.get('preview_text', '')}\n\n{nl.get('body', '')}"

    return JSONResponse({
        "blog": blog.get("draft", ""),
        "creative": fmt(newsletters.get("creative_freelancer", {})),
        "solo": fmt(newsletters.get("agency_owner", {})),
        "ops": fmt(newsletters.get("marketing_manager", {})),
    })


@app.post("/api/analyze")
async def api_analyze(body: AnalyzeRequest):
    client = anthropic_lib.Anthropic(api_key=ANTHROPIC_API_KEY)
    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=400,
        system=(
            "You are a growth analyst at NovaMind. Write crisp, data-forward performance "
            "summaries. Be specific — reference actual numbers from the data."
        ),
        messages=[{
            "role": "user",
            "content": (
                f"Campaign: \"{body.campaign_name}\"\n"
                f"Open rate: {body.open_rate}% (industry avg 42%)\n"
                f"Click rate: {body.click_rate}% (industry avg 14%)\n"
                f"Sent: {body.sent} contacts | Unsubscribes: {body.unsub}\n"
                f"Clicks by persona: Creative Directors {body.persona_clicks.get('creative', 0)}%, "
                f"Solopreneurs {body.persona_clicks.get('solo', 0)}%, "
                f"Ops Managers {body.persona_clicks.get('ops', 0)}%\n\n"
                "Write 3 sentences: (1) what performed well, "
                "(2) which persona to prioritize, (3) one specific next-campaign recommendation."
            ),
        }],
    )
    return JSONResponse({"summary": response.content[0].text})
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


def _load_json_dir(directory: str) -> list[dict]:
    p = Path(directory)
    if not p.exists():
        return []
    records = []
    for f in sorted(p.glob("*.json"), reverse=True):
        try:
            records.append(json.loads(f.read_text()))
        except json.JSONDecodeError:
            pass
    return records


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    campaigns = _load_json_dir(CAMPAIGNS_DIR)
    analytics_data = _load_json_dir(ANALYTICS_DIR)

    analytics_by_id = {a["campaign_id"]: a for a in analytics_data}
    for c in campaigns:
        c["analytics"] = analytics_by_id.get(c["campaign_id"])

    pending = [c for c in campaigns if c.get("status") == "PENDING_APPROVAL"]
    sent = [c for c in campaigns if c.get("status") == "SENT"]

    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "pending": pending,
            "sent": sent,
            "total": len(campaigns),
        },
    )


@app.get("/campaign/{campaign_id}", response_class=HTMLResponse)
async def campaign_detail(request: Request, campaign_id: str):
    content_dir = Path(CONTENT_DIR) / campaign_id
    blog = analytics_record = newsletters = campaign_meta = None

    camp_path = Path(CAMPAIGNS_DIR) / f"{campaign_id}.json"
    if camp_path.exists():
        campaign_meta = json.loads(camp_path.read_text())

    blog_path = content_dir / "blog.json"
    if blog_path.exists():
        blog = json.loads(blog_path.read_text())

    nl_path = content_dir / "newsletters.json"
    if nl_path.exists():
        newsletters = json.loads(nl_path.read_text())

    a_path = Path(ANALYTICS_DIR) / f"{campaign_id}.json"
    if a_path.exists():
        analytics_record = json.loads(a_path.read_text())

    return templates.TemplateResponse(
        request,
        "campaign.html",
        {
            "campaign_id": campaign_id,
            "campaign_meta": campaign_meta,
            "blog": blog,
            "newsletters": newsletters,
            "analytics": analytics_record,
        },
    )


@app.post("/generate", response_class=HTMLResponse)
async def generate(request: Request, topic: str = Form(...)):
    """Stage 1: generate content, register as PENDING_APPROVAL."""
    campaign_id, blog, newsletters = content_generator.run(topic)
    crm_manager.run(campaign_id, blog, newsletters)
    return RedirectResponse(url=f"/campaign/{campaign_id}", status_code=303)


@app.post("/approve/{campaign_id}", response_class=HTMLResponse)
async def approve(request: Request, campaign_id: str):
    """Stage 2: approve pending campaign — send + run analytics."""
    nl_path = Path(CONTENT_DIR) / campaign_id / "newsletters.json"
    newsletters = json.loads(nl_path.read_text()) if nl_path.exists() else {}

    blog_path = Path(CONTENT_DIR) / campaign_id / "blog.json"
    blog = json.loads(blog_path.read_text()) if blog_path.exists() else {}

    newsletter_ids = crm_manager.approve_and_send(campaign_id, newsletters)
    analytics_module.run(campaign_id, blog, newsletter_ids, newsletters=newsletters)
    return RedirectResponse(url=f"/campaign/{campaign_id}", status_code=303)


# Keep legacy /run endpoint for backwards compatibility
@app.post("/run", response_class=HTMLResponse)
async def run_pipeline(request: Request, topic: str = Form(...)):
    campaign_id, blog, newsletters = content_generator.run(topic)
    newsletter_ids = crm_manager.run(campaign_id, blog, newsletters)
    crm_manager.approve_and_send(campaign_id, newsletters)
    analytics_module.run(campaign_id, blog, newsletter_ids, newsletters=newsletters)
    return RedirectResponse(url=f"/campaign/{campaign_id}", status_code=303)
