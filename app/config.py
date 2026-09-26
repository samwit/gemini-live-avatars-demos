"""
Configuration and authentication.

Everything that talks to Gemini goes through `make_client()`, so this is the one
place to look if you want to understand how we authenticate.

Live Avatar is a Gemini Enterprise Agent Platform feature (Vertex AI), so the
client is always created with `enterprise=True`. There are two ways to
authenticate:

1. API key. An Agent Platform API key (express mode, or a Cloud API key that
   is allowed to call aiplatform.googleapis.com). Quickest to set up.

2. Application Default Credentials (ADC). The recommended option for
   production. Run `gcloud auth application-default login` once, and set
   GOOGLE_CLOUD_PROJECT. As a convenience for local demos we also fall back to
   your plain `gcloud auth login` user token if ADC hasn't been set up.

A Gemini Developer API (AI Studio) key will NOT work: that endpoint accepts
`response_modalities=["VIDEO"]` but has no avatar fields, so you silently get
audio only.
"""

from __future__ import annotations

import os
import subprocess
import time

from dotenv import load_dotenv
from google import genai

# Load .env from the repo root (one directory above this file).
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

# The Live model that supports avatars.
MODEL = os.getenv("GEMINI_LIVE_MODEL", "gemini-3.8-live")

# Avatar video is ~5 Mbps by default. 1.5 Mbps still looks great at 704x1280 and
# is much kinder to Wi-Fi when you're demoing on stage. Set to 0 for the default.
VIDEO_BITRATE = int(os.getenv("AVATAR_VIDEO_BITRATE", "1500000")) or None

API_KEY = os.getenv("GOOGLE_API_KEY") or None
PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT") or None
LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
AUTH_MODE = os.getenv("GEMINI_AUTH", "auto").lower()  # auto | api_key | adc


def make_client() -> genai.Client:
    """Create a Gen AI client pointed at Gemini Enterprise Agent Platform."""
    use_key = AUTH_MODE == "api_key" or (AUTH_MODE == "auto" and API_KEY)

    if use_key:
        if not API_KEY:
            raise RuntimeError("GEMINI_AUTH=api_key but GOOGLE_API_KEY is not set")
        # Express mode: the key identifies the project, we only choose a region.
        # (Without a location the Live endpoint rejects the model resource name.)
        return genai.Client(enterprise=True, api_key=API_KEY, location=LOCATION)

    if not PROJECT:
        raise RuntimeError(
            "Set GOOGLE_API_KEY, or GOOGLE_CLOUD_PROJECT for ADC auth (see .env.example)"
        )
    return genai.Client(
        enterprise=True,
        project=PROJECT,
        location=LOCATION,
        credentials=_credentials(),
    )


# --- ADC with a gcloud fallback --------------------------------------------------

_cached_token: tuple[str, float] | None = None


def _credentials():
    """Return ADC credentials, or a short-lived token from the gcloud CLI."""
    import google.auth
    from google.auth.exceptions import DefaultCredentialsError, RefreshError
    from google.auth.transport.requests import Request

    try:
        creds, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        creds.refresh(Request())  # fail fast on stale/expired ADC files
        return creds
    except (DefaultCredentialsError, RefreshError):
        pass

    # Fallback: `gcloud auth print-access-token` (valid for ~60 minutes).
    # We cache it for 45 minutes. Each Live session is created with a fresh
    # client, so a long-running server keeps working.
    from google.oauth2.credentials import Credentials

    global _cached_token
    if _cached_token is None or time.time() - _cached_token[1] > 45 * 60:
        token = subprocess.check_output(
            ["gcloud", "auth", "print-access-token"], text=True
        ).strip()
        _cached_token = (token, time.time())
    return Credentials(_cached_token[0])
