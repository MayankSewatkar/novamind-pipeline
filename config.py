import os
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
HUBSPOT_ACCESS_TOKEN = os.getenv("HUBSPOT_ACCESS_TOKEN", "")

CLAUDE_MODEL = "claude-sonnet-4-6"

PERSONAS = {
    "agency_owner": {
        "name": "Agency Owner",
        "description": "Founders and owners of small creative agencies (5–30 people). Focus on ROI, scaling, and reducing operational overhead.",
        "tone": "executive, results-driven, concise",
        "pain_points": ["burning cash on manual workflows", "scaling the team without scaling costs", "competing with larger agencies"],
    },
    "creative_freelancer": {
        "name": "Creative Freelancer",
        "description": "Independent designers, copywriters, and video creators. Focus on practical tools, time savings, and getting more done solo.",
        "tone": "casual, practical, peer-to-peer",
        "pain_points": ["juggling too many clients", "admin overhead eating into creative time", "staying competitive"],
    },
    "marketing_manager": {
        "name": "Marketing Manager",
        "description": "In-house marketing managers at small agencies or SMBs. Focus on campaign metrics, team alignment, and reporting.",
        "tone": "professional, data-forward, collaborative",
        "pain_points": ["proving content ROI to leadership", "coordinating cross-channel campaigns", "scaling content output without more headcount"],
    },
}

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
CAMPAIGNS_DIR = os.path.join(DATA_DIR, "campaigns")
ANALYTICS_DIR = os.path.join(DATA_DIR, "analytics")
CONTENT_DIR = os.path.join(DATA_DIR, "content")
