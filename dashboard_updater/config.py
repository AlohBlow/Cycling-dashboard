"""
Configuration — reads from environment variables.
For local development, copy .env.example → .env and fill in your values.
Never commit real credentials to this file.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env when running locally (no-op in GitHub Actions where env vars are injected)
load_dotenv(Path(__file__).parent / '.env')


def _require(key):
    val = os.getenv(key)
    if not val:
        raise EnvironmentError(
            f"Required environment variable '{key}' is not set.\n"
            f"  Local dev: add it to dashboard_updater/.env\n"
            f"  GitHub Actions: add it as a repository secret."
        )
    return val


INTERVALS_ATHLETE_ID = _require("INTERVALS_ATHLETE_ID")
INTERVALS_API_KEY    = _require("INTERVALS_API_KEY")
INTERVALS_BASE_URL   = "https://intervals.icu/api/v1"

XERT_EMAIL    = os.getenv("XERT_EMAIL", "")     # optional — Xert skipped if blank
XERT_PASSWORD = os.getenv("XERT_PASSWORD", "")
XERT_BASE_URL = "https://www.xertonline.com/api/v1"

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")  # optional — coaching notes skipped if blank

OUTPUT_HTML   = "../index.html"
TEMPLATE_HTML = "../cycling-dashboard-template.html"
