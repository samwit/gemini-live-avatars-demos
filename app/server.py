"""
The web server: static pages, a tiny JSON API, and one WebSocket per demo session.

Run it:
    uv run python -m app.server          # then open http://localhost:8000

Why a backend at all? Two reasons:
  1. Credentials stay on the server. The browser never sees your API key or token.
  2. Tools run in Python, next to your data and business rules (see the
     Interrogation demo, where the server decides whether the suspect may confess).
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

import uvicorn
from fastapi import FastAPI, WebSocket
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import config
from .avatars import AVATARS, VOICES
from .browser_link import BrowserLink
from .demos import DEMOS
from .demos.polyglot import CITIES
from .demos.studio import PERSONAS

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("server")

STATIC = Path(__file__).parent / "static"
app = FastAPI(title="Gemini Live Avatar demos")


@app.get("/")
async def home():
    return FileResponse(STATIC / "index.html")


@app.get("/api/catalog")
async def catalog():
    """Everything the pages need to render pickers and the demo gallery."""
    return JSONResponse({
        "model": config.MODEL,
        "demos": [
            {"id": d.id, "title": d.title, "tagline": d.tagline, "emoji": d.emoji,
             "features": d.features, "avatar": d.avatar}
            for d in DEMOS.values()
        ],
        "avatars": AVATARS,
        "voices": VOICES,
        "personas": PERSONAS,
        "cities": CITIES,
    })


@app.websocket("/ws/{demo_id}")
async def demo_socket(ws: WebSocket, demo_id: str):
    """One browser tab = one WebSocket = one (or two) Gemini Live sessions."""
    await ws.accept()
    link = BrowserLink(ws)
    demo = DEMOS.get(demo_id)
    if demo is None:
        await link.send_json({"type": "error", "message": f"Unknown demo {demo_id}"})
        await ws.close()
        return

    # The first message from the page carries the options (avatar, city, motion...).
    start = json.loads(await ws.receive_text())
    options = start.get("options", {}) if start.get("type") == "start" else {}
    log.info("starting demo %s with %s", demo_id, options)

    try:
        await demo.run(link, options)
    except Exception as e:
        log.exception("demo %s failed", demo_id)
        await link.send_json({"type": "error", "message": _friendly(e)})
    finally:
        try:
            await ws.close()
        except Exception:
            pass


def _friendly(e: Exception) -> str:
    """Turn the most common setup errors into advice."""
    msg = str(e)
    if "API_KEY_SERVICE_BLOCKED" in msg or "are blocked" in msg:
        return ("Your API key isn't allowed to call the Agent Platform API. In Cloud Console → APIs & Services → "
                "Credentials, edit the key's API restrictions to include it, or use GEMINI_AUTH=adc. (" + msg[:200] + ")")
    if "Maximum concurrent sessions" in msg:
        return "Too many avatar sessions are open at once for this project. Close other tabs and try again."
    if "allowlisted" in msg:
        return "This project isn't allowlisted for that feature (custom avatars/voices). " + msg[:200]
    return msg[:500]


# Static assets (JS, CSS, images, and one HTML page per demo).
app.mount("/", StaticFiles(directory=STATIC, html=True), name="static")


if __name__ == "__main__":
    uvicorn.run("app.server:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")), reload=False)
