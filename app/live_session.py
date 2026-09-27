# Copyright 2026 Sam Witteveen
# SPDX-License-Identifier: Apache-2.0

"""
AvatarSession: a thin, well-commented wrapper around one Gemini Live session.

Every demo (and both debaters in the debate demo) uses this class. It handles:

  * building the LiveConnectConfig (avatar, voice, tools, transcription)
  * the receive loop, which turns raw server messages into simple events
  * tool calls, both quick blocking ones and slow background (async) ones

The flow of one session looks like this:

    browser mic/camera/text ──► AvatarSession.send_*() ──► Gemini Live
    browser <video> player  ◄── on_event("video", bytes) ◄── fMP4 chunks
    browser transcript/UI   ◄── on_event("transcript"/"ui"/...)

What comes back from an avatar session
--------------------------------------
With response_modalities=["VIDEO"], the model streams a single, continuous
fragmented-MP4 file:

  * the first chunk is the init segment (ftyp + moov): H.264 Constrained
    Baseline 704x1280 @ 24fps plus AAC-LC 24 kHz mono audio
  * after that come moof/mdat fragments, split into ~16 KB chunks
  * the stream starts as soon as you connect and never stops. Between
    turns the avatar idles (blinks, breathes, listens).

So the speech audio is already inside the video, and lip sync is done for
you. The browser just appends every chunk to a MediaSource buffer.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from google.genai import types

from . import config
from .avatars import api_name

log = logging.getLogger("avatar")

# An event callback receives (event_name, payload). See _receive_loop for the list.
EventCallback = Callable[[str, Any], Awaitable[None]]


# ---------------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------------

@dataclass
class Tool:
    """A function the avatar can call, plus the Python code that runs it.

    `declaration` is a standard Gemini function declaration (name, description,
    JSON-schema-style parameters).

    `handler(args, ctx)` does the work and returns a dict that goes back to the
    model. It can also push events to the browser with `await ctx.ui(...)`.

    `background=True` makes it an *asynchronous* function call: the model keeps
    talking while the handler runs. When the result is ready it is delivered
    according to `scheduling`:
        WHEN_IDLE : wait for a natural pause, then talk about the result
        SILENT    : just add it to context, don't say anything
        INTERRUPT : cut in immediately (use sparingly!)
    """

    declaration: dict
    handler: Callable[[dict, "ToolContext"], Awaitable[dict]]
    background: bool = False
    scheduling: str = "WHEN_IDLE"

    @property
    def name(self) -> str:
        return self.declaration["name"]


@dataclass
class ToolContext:
    """What a tool handler gets besides its arguments."""

    ui: Callable[[str, Any], Awaitable[None]]    # push a UI event to the browser
    state: dict = field(default_factory=dict)    # per-session scratchpad (e.g. game state)
    session: "AvatarSession | None" = None


# ---------------------------------------------------------------------------------
# The session
# ---------------------------------------------------------------------------------

class AvatarSession:
    """One Gemini Live session with an avatar.

    Usage:
        async with AvatarSession(avatar="David", voice="Charon",
                                 system_instruction="...", on_event=cb) as s:
            await s.send_text("Hello!")
            ...
    """

    def __init__(
        self,
        *,
        avatar: str,
        voice: str,
        system_instruction: str,
        on_event: EventCallback,
        tools: list[Tool] | None = None,
        google_search: bool = False,
        language_code: str | None = None,
        state: dict | None = None,
        label: str = "avatar",
        custom_image: bytes | None = None,
        custom_image_mime: str = "image/png",
    ):
        self.avatar = avatar
        # A reference photo instead of a prebuilt avatar (allowlisted projects only).
        self.custom_image = custom_image
        self.custom_image_mime = custom_image_mime
        self.voice = voice
        self.system_instruction = system_instruction
        self.on_event = on_event
        self.tools = {t.name: t for t in (tools or [])}
        self.google_search = google_search
        self.language_code = language_code
        self.label = label
        self.ctx = ToolContext(ui=self._ui, state=state if state is not None else {}, session=self)

        self._session = None             # the SDK AsyncSession
        self._connection = None          # the async context manager from connect()
        self._receiver: asyncio.Task | None = None
        self._pending_calls: set[str] = set()   # tool names currently running in background
        self._turn_text: list[str] = []         # model transcript for the current turn
        self._turn_done = asyncio.Event()
        self.last_turn_text = ""

    # -- configuration ------------------------------------------------------------

    def build_config(self) -> types.LiveConnectConfig:
        """Everything the model needs to know, sent once in the setup message."""
        tools: list[Any] = []
        if self.tools:
            # Function declarations are plain dicts; the SDK converts them.
            # background tools are marked NON_BLOCKING so the model keeps talking.
            decls = []
            for t in self.tools.values():
                d = dict(t.declaration)
                if t.background:
                    d["behavior"] = "NON_BLOCKING"
                decls.append(d)
            tools.append({"function_declarations": decls})
        if self.google_search:
            # Note: Google Search can't be combined with function calling.
            tools.append({"google_search": {}})

        return types.LiveConnectConfig(
            # VIDEO is the magic switch: it turns on the avatar.
            response_modalities=["VIDEO"],
            avatar_config=self._avatar_config(),
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=self.voice)
                ),
                language_code=self.language_code,
            ),
            system_instruction=self.system_instruction,
            tools=tools or None,
            # Transcripts of what the user said and what the avatar said.
            input_audio_transcription=types.AudioTranscriptionConfig(),
            output_audio_transcription=types.AudioTranscriptionConfig(),
            # Camera input gets expensive in tokens; a sliding window lets the
            # session run beyond the default audio+video limits.
            context_window_compression=types.ContextWindowCompressionConfig(
                trigger_tokens=100_000,
                sliding_window=types.SlidingWindow(target_tokens=50_000),
            ),
        )

    def _avatar_config(self) -> types.AvatarConfig:
        """A prebuilt avatar by name, or a custom one generated from a reference photo."""
        if self.custom_image:
            # The SDK base64-encodes the bytes for us. The docs specify a 9:16
            # portrait, at least 704x1280, under 5 MB, with PNG recommended.
            return types.AvatarConfig(
                customized_avatar=types.CustomizedAvatar(
                    image_data=self.custom_image,
                    image_mime_type=self.custom_image_mime,
                ),
                video_bitrate_bps=config.VIDEO_BITRATE,
            )
        # Translate our display name to Google's id (e.g. "David" -> "Sam").
        return types.AvatarConfig(avatar_name=api_name(self.avatar), video_bitrate_bps=config.VIDEO_BITRATE)

    # -- lifecycle ------------------------------------------------------------------

    async def __aenter__(self) -> "AvatarSession":
        client = config.make_client()
        self._connection = client.aio.live.connect(model=config.MODEL, config=self.build_config())
        self._session = await self._connection.__aenter__()
        self._receiver = asyncio.create_task(self._receive_loop())
        log.info("[%s] connected (avatar=%s voice=%s)", self.label, self.avatar, self.voice)
        return self

    async def __aexit__(self, *exc) -> None:
        if self._receiver:
            self._receiver.cancel()
        if self._connection:
            await self._connection.__aexit__(None, None, None)
        log.info("[%s] closed", self.label)

    # -- sending ---------------------------------------------------------------------

    async def send_audio(self, pcm16k: bytes) -> None:
        """Raw 16-bit little-endian mono PCM at 16 kHz from the microphone."""
        await self._session.send_realtime_input(
            audio=types.Blob(data=pcm16k, mime_type="audio/pcm;rate=16000")
        )

    async def send_image(self, jpeg: bytes) -> None:
        """One camera frame (JPEG). Send about 1 frame per second.

        Heads up: the docs show `media=...`, but gemini-3.8-live rejects that
        with "Mime type 'image/jpeg' is not supported". `video=` is correct.
        """
        await self._session.send_realtime_input(
            video=types.Blob(data=jpeg, mime_type="image/jpeg")
        )

    async def send_text(self, text: str) -> None:
        """A typed message, treated like the user saying it."""
        self._turn_done.clear()
        await self._session.send_realtime_input(text=text)

    async def direct(self, note: str) -> None:
        """Steer the avatar mid-session with a "stage direction".

        The docs suggest sending a role="system" Content with send_client_content,
        but gemini-3.8-live ignores that. A realtime text message framed as a
        stage direction works reliably.
        """
        await self.send_text(f"(Stage direction, do not read this aloud: {note})")

    async def say_and_wait(self, text: str, timeout: float = 90) -> str:
        """Send text, wait for the avatar to finish its turn, return what it said."""
        await self.send_text(text)
        await asyncio.wait_for(self._turn_done.wait(), timeout)
        return self.last_turn_text

    # -- receiving ------------------------------------------------------------------

    async def _receive_loop(self) -> None:
        """Turn server messages into events.

        Events emitted through on_event(name, payload):
          video          bytes  fMP4 chunk for the <video> element
          transcript     {"role": "user"|"model", "text": str}
          turn_complete  {"text": full model transcript for the turn}
          interrupted    None   (user barged in, so drop buffered speech)
          tool_call      {"name", "args"}
          tool_result    {"name", "result"}
          go_away        {"time_left"}  (connection closing soon)
          error          {"message"}
        """
        try:
            # session.receive() yields messages for ONE turn and then stops,
            # so it needs an outer loop to keep listening across turns.
            while True:
                async for msg in self._session.receive():
                    await self._handle(msg)
        except asyncio.CancelledError:
            raise
        except Exception as e:  # connection dropped, quota, etc.
            log.exception("[%s] receive loop ended", self.label)
            await self.on_event("error", {"message": str(e)})

    async def _handle(self, msg: types.LiveServerMessage) -> None:
        sc = msg.server_content
        if sc:
            # 1) Media. With VIDEO modality each part is a chunk of fMP4.
            if sc.model_turn and sc.model_turn.parts:
                for part in sc.model_turn.parts:
                    if part.inline_data and part.inline_data.data:
                        await self.on_event("video", part.inline_data.data)

            # 2) Transcripts arrive in small pieces as speech is produced.
            if sc.input_transcription and sc.input_transcription.text:
                await self.on_event("transcript", {"role": "user", "text": sc.input_transcription.text})
            if sc.output_transcription and sc.output_transcription.text:
                self._turn_text.append(sc.output_transcription.text)
                await self.on_event("transcript", {"role": "model", "text": sc.output_transcription.text})

            # 3) Turn management.
            if sc.interrupted:
                await self.on_event("interrupted", None)
            if sc.turn_complete:
                self.last_turn_text = "".join(self._turn_text).strip()
                self._turn_text = []
                self._turn_done.set()
                await self.on_event("turn_complete", {"text": self.last_turn_text})

        # 4) Tool calls.
        if msg.tool_call and msg.tool_call.function_calls:
            for fc in msg.tool_call.function_calls:
                await self._dispatch_tool(fc)

        # 5) The server warns ~60s before closing the connection (~10 min limit).
        #    A production app would reconnect with session resumption here.
        if msg.go_away:
            await self.on_event("go_away", {"time_left": str(msg.go_away.time_left)})

    # -- tools -------------------------------------------------------------------------

    async def _dispatch_tool(self, fc: types.FunctionCall) -> None:
        name = fc.name or ""
        tool = self.tools.get(name)
        args = dict(fc.args or {})
        await self.on_event("tool_call", {"name": name, "args": args})

        if tool is None:
            await self._respond(fc, {"status": "error", "message": f"Unknown tool {name}"}, None)
            return

        if not tool.background:
            # Fast tools: run inline. The model waits for the answer.
            await self._respond(fc, await self._run(tool, args), None)
            return

        # Slow tools: the model may issue the same call twice while waiting.
        # Ignore duplicates while the first one is still running (see the docs'
        # "Handle duplicate function calls" section).
        if name in self._pending_calls:
            log.info("[%s] ignoring duplicate background call %s", self.label, name)
            return
        self._pending_calls.add(name)

        async def run_in_background():
            try:
                result = await self._run(tool, args)
                await self._respond(fc, result, tool.scheduling)
            finally:
                self._pending_calls.discard(name)

        # Never await slow work inside the receive loop, or the stream freezes.
        asyncio.create_task(run_in_background())

    async def _run(self, tool: Tool, args: dict) -> dict:
        try:
            result = await tool.handler(args, self.ctx)
        except Exception as e:
            log.exception("tool %s failed", tool.name)
            # Informative errors stop gemini-3.8-live from retrying in a loop.
            result = {"status": "error", "retryable": False, "message": str(e)}
        await self.on_event("tool_result", {"name": tool.name, "result": result})
        return result

    async def _respond(self, fc: types.FunctionCall, result: dict, scheduling: str | None) -> None:
        await self._session.send_tool_response(
            function_responses=[
                types.FunctionResponse(
                    id=fc.id,          # must echo the call id
                    name=fc.name,
                    response=result,
                    scheduling=scheduling,
                )
            ]
        )

    async def _ui(self, event: str, data: Any) -> None:
        await self.on_event("ui", {"event": event, "data": data})
