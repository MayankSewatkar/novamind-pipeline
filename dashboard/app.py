"""FastAPI web dashboard for the NovaMind pipeline."""

import json
import sys
from pathlib import Path

from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import ANALYTICS_DIR, CAMPAIGNS_DIR, CONTENT_DIR
from pipeline import content_generator, crm_manager, analytics as analytics_module

app = FastAPI(title="NovaMind Pipeline Dashboard")
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

    # Attach analytics to campaigns
    analytics_by_id = {a["campaign_id"]: a for a in analytics_data}
    for c in campaigns:
        cid = c["campaign_id"]
        c["analytics"] = analytics_by_id.get(cid)

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "campaigns": campaigns,
            "total": len(campaigns),
        },
    )


@app.get("/campaign/{campaign_id}", response_class=HTMLResponse)
async def campaign_detail(request: Request, campaign_id: str):
    content_dir = Path(CONTENT_DIR) / campaign_id
    blog = analytics_record = newsletters = None

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
        "campaign.html",
        {
            "request": request,
            "campaign_id": campaign_id,
            "blog": blog,
            "newsletters": newsletters,
            "analytics": analytics_record,
        },
    )


@app.post("/run", response_class=HTMLResponse)
async def run_pipeline(request: Request, topic: str = Form(...)):
    campaign_id, blog, newsletters = content_generator.run(topic)
    newsletter_ids = crm_manager.run(campaign_id, blog, newsletters)
    analytics_module.run(campaign_id, blog, newsletter_ids)
    return RedirectResponse(url=f"/campaign/{campaign_id}", status_code=303)
