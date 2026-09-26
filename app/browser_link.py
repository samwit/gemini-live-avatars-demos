"""
BrowserLink: the server side of the WebSocket between our page and our backend.

The wire protocol is deliberately tiny. The rule is: binary frames carry media,
text frames carry JSON.

Browser -> server
  binary                      16 kHz 16-bit mono PCM from the microphone
  {"type": "start", "options": {...}}   first message, demo-specific options
  {"type": "image", "data": b64}        a JPEG camera frame (~1 fps)
  {"type": "text",  "text": "..."}      typed message
  {"type": "action", ...}               demo-specific buttons (switch city, vote...)

Server -> browser
  binary   [1 byte stream index][fMP4 chunk]
           The index says which <video> to feed (0 normally; 0/1 in the debate).
  {"type": "ready"}
  {"type": "transcript", "stream": 0, "role": "user"|"model", "text": "..."}
  {"type": "turn_complete" | "interrupted", "stream": 0}
  {"type": "tool", "stream": 0, "name": "...", "args": {...}}   (for the log)
  {"type": "ui", "event": "...", "data": {...}}                (demo widgets)
  {"type": "error", "message": "..."}

The browser never sees credentials. It only talks to this server, which holds
the key or ADC token and talks to Gemini.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import WebSocket


class BrowserLink:
    def __init__(self, ws: WebSocket):
        self.ws = ws
        # Several tasks send concurrently (video, transcripts, tool results),
        # so serialize writes to the socket.
        self._lock = asyncio.Lock()
        self.closed = False

    async def send_json(self, payload: dict) -> None:
        if self.closed:
            return
        async with self._lock:
            try:
                await self.ws.send_text(json.dumps(payload))
            except Exception:
                self.closed = True

    async def send_video(self, stream: int, chunk: bytes) -> None:
        if self.closed:
            return
        async with self._lock:
            try:
                await self.ws.send_bytes(bytes([stream]) + chunk)
            except Exception:
                self.closed = True

    async def ui(self, event: str, data: Any = None) -> None:
        await self.send_json({"type": "ui", "event": event, "data": data})

    def forward_events(self, stream: int = 0):
        """Build an AvatarSession on_event callback that relays events to the page."""

        async def on_event(name: str, payload: Any) -> None:
            if name == "video":
                await self.send_video(stream, payload)
            elif name == "transcript":
                await self.send_json({"type": "transcript", "stream": stream, **payload})
            elif name in ("turn_complete", "interrupted"):
                await self.send_json({"type": name, "stream": stream})
            elif name == "tool_call":
                await self.send_json({"type": "tool", "stream": stream, **payload})
            elif name == "ui":
                await self.send_json({"type": "ui", "stream": stream, **payload})
            elif name == "go_away":
                await self.send_json({"type": "notice", "message": "Session ends in about a minute (10-minute connection limit)."})
            elif name == "error":
                await self.send_json({"type": "error", **payload})

        return on_event
