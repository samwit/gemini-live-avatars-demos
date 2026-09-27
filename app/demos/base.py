# Copyright 2026 Sam Witteveen
# SPDX-License-Identifier: Apache-2.0

"""
The Demo base class.

A demo is a persona plus tools plus (optionally) custom orchestration. Most
demos only set class attributes and write their tools. The default `run()`
below does the standard "one avatar and one human" loop:

    1. open an AvatarSession with this demo's avatar/voice/instructions/tools
    2. optionally have the avatar greet the user (`opening`)
    3. pump browser messages (mic audio, camera frames, text) into the session
       until the browser disconnects

The debate demo overrides `run()` to drive two avatars at once.
"""

from __future__ import annotations

import base64
import logging

from fastapi import WebSocketDisconnect

from ..browser_link import BrowserLink
from ..live_session import AvatarSession, Tool

log = logging.getLogger("demo")


class Demo:
    id: str = ""
    title: str = ""
    tagline: str = ""
    emoji: str = ""
    avatar: str = "Kira"
    voice: str = "Aoede"
    features: list[str] = []      # shown on the home page ("Vision", "Async tools"...)

    # -- hooks a demo can override -------------------------------------------------

    def system_instruction(self, options: dict) -> str:
        raise NotImplementedError

    def tools(self) -> list[Tool]:
        return []

    def opening(self, options: dict) -> str | None:
        """Text sent right after connecting so the avatar speaks first."""
        return None

    def session_kwargs(self, options: dict) -> dict:
        """Extra AvatarSession arguments (avatar/voice overrides, search...)."""
        return {}

    async def on_action(self, session: AvatarSession, link: BrowserLink, msg: dict) -> None:
        """Handle demo-specific {"type": "action"} messages from the page."""

    # -- the standard single-avatar loop ------------------------------------------

    async def run(self, link: BrowserLink, options: dict) -> None:
        kwargs = dict(
            avatar=self.avatar,
            voice=self.voice,
            system_instruction=self.system_instruction(options),
            tools=self.tools(),
            on_event=link.forward_events(stream=0),
            label=self.id,
        )
        kwargs.update(self.session_kwargs(options))

        async with AvatarSession(**kwargs) as session:
            await link.send_json({"type": "ready", "avatar": session.avatar, "voice": session.voice})
            if (first := self.opening(options)):
                await session.send_text(first)
            await pump_browser(link, session, self)


async def pump_browser(link: BrowserLink, session: AvatarSession, demo: Demo) -> None:
    """Forward everything the browser sends into the Live session."""
    try:
        while True:
            msg = await link.ws.receive()
            if msg["type"] == "websocket.disconnect":
                return
            if msg.get("bytes") is not None:
                await session.send_audio(msg["bytes"])          # mic PCM
                continue
            data = _json(msg.get("text"))
            kind = data.get("type")
            if kind == "image":
                await session.send_image(base64.b64decode(data["data"]))
            elif kind == "text" and data.get("text"):
                await session.send_text(data["text"])
            elif kind == "action":
                await demo.on_action(session, link, data)
    except WebSocketDisconnect:
        return


def _json(text: str | None) -> dict:
    import json

    try:
        return json.loads(text or "{}")
    except json.JSONDecodeError:
        return {}
