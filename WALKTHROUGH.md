# Code walkthrough

A suggested order for reading (or presenting) the code, from "hello world" to two avatars arguing. Each step says what to look at and what to point out.

---

## Part 1: The API in 60 lines

### 1. `scripts/01_hello_avatar.py`

The whole idea in one file. Run it first so everyone sees an MP4 appear.

- `response_modalities=["VIDEO"]` turns the avatar on. Without it you get a voice-only Live session.
- `avatar_config=AvatarConfig(avatar_name="Kai")` picks the face, and `speech_config` picks the voice. They're independent, so any face works with any voice.
- The receive loop: each `part.inline_data.data` is a chunk of **fragmented MP4**, and joining the chunks gives a playable file. Audio is inside the MP4, so there's no separate audio handling.
- `output_audio_transcription` gives you the words as text, and you'll use that everywhere.

### 2. `scripts/02_raw_websocket.py`

The same program with no SDK. Point out the three message types: `setup` (once), `realtime_input` (text/audio/video), and the server's `serverContent` (`modelTurn` → `inlineData`, `outputTranscription`, `turnComplete`). The first chunk starts with `ftyp`, the MP4 header. The `usageMetadata` print shows video counted as output tokens (~5–6k tokens per second).

### 3. `app/config.py`

`make_client()` (line 49) is the only auth code in the repo. Point out:
- Avatars live on Gemini Enterprise Agent Platform, so it's always `enterprise=True`.
- API key (express mode) vs. ADC, plus the gcloud-token fallback for demos.
- The warning about AI Studio keys: VIDEO modality is accepted but there's no avatar.

---

## Part 2: The reusable core

### 4. `app/live_session.py`: `AvatarSession` (the heart of the repo)

Read the module docstring first: it describes the stream format.

| Look at | Why |
|---|---|
| `build_config()` (line ~136) | Everything sent in the setup message: VIDEO modality, avatar + bitrate, voice, tools, transcription, context-window compression. Background tools get `behavior: NON_BLOCKING` (line ~146). |
| `send_image()` (line ~204) | **Gotcha:** camera frames go in `video=`; the documented `media=` is rejected by 3.8. |
| `direct()` (line ~219) | Mid-session steering. `role="system"` content is ignored on 3.8, but a realtime "stage direction" works. |
| `say_and_wait()` | Send text and await the avatar's full spoken reply. This is what makes the debate easy. |
| `_receive_loop()` (line ~236) | **Gotcha:** `session.receive()` ends at every turn, hence `while True:` (line ~252). |
| `_handle()` | Turns raw messages into 7 simple events: video, transcript, turn_complete, interrupted, tool_call, go_away, error. |
| `_dispatch_tool()` | Fast tools are awaited inline. Slow tools run in `asyncio.create_task` (line ~329) so the stream never freezes, and duplicate calls are ignored while one is pending. |
| `_respond()` | Echoes `id=fc.id` and passes `scheduling` (WHEN_IDLE / SILENT / INTERRUPT). |

The `Tool` dataclass is the extension point: a declaration dict, an async handler, and `background` + `scheduling`.

### 5. `app/browser_link.py`

The browser ⇄ server protocol in one docstring. One rule: **binary = media, text = JSON.** Server → browser binary frames are `[1 byte stream index][fMP4 chunk]` (line ~59). The index is what lets the debate page run two videos over one socket. `forward_events()` adapts `AvatarSession` events into messages for the page.

### 6. `app/demos/base.py` and `app/server.py`

- `Demo.run()` (base.py line 59) is the standard loop: open a session, optionally greet, then `pump_browser()` forwards mic PCM, camera JPEGs and text into the session.
- `server.py` has one WebSocket route, `/ws/{demo_id}` (line 61). The first message carries the demo's options. `_friendly()` turns common setup errors (blocked key, quota, allowlist) into advice.

---

## Part 3: The browser

### 7. `app/static/js/avatar-player.js`: playing the stream

- `MIME` (line 20): `video/mp4; codecs="avc1.42c020, mp4a.40.2"` (H.264 Constrained Baseline 3.2 + AAC-LC).
- `start()` creates a `MediaSource` (or `ManagedMediaSource` on iOS) and calls `video.play()` while we still have the click gesture, so audio autoplays.
- `_pump()` batches chunks into one `appendBuffer`.
- `_chase()` (line 111) is the live-player part: speed up to 1.08× if we're >0.6 s behind, jump if >2 s, and trim old buffer so it never fills.
- `jumpToLive()` is called on `interrupted`, so barge-in feels instant.

### 8. `pcm-worklet.js` + `media.js`

Mic → AudioWorklet → resample to **16 kHz 16-bit mono PCM** in 100 ms chunks. Camera → canvas → JPEG at **1 fps**, max side 768 px (what the docs recommend).

### 9. `live-client.js`

Routes binary chunks by stream byte (line 39) and re-emits JSON as DOM events. The **echo gate** (`gated`, line 60) mutes the mic while the avatar is speaking, unless headphones mode is on. Without it, laptop speakers make the avatar interrupt itself.

### 10. `shell.js`

Shared page wiring (Start/Stop, mic, camera, transcript bubbles). Each demo page's own JS only handles `onUi(event, data)` for its widgets.

---

## Part 4: The demos (each is persona + tools + a little UI)

### 11. Avatar Studio: `demos/studio.py` + `js/demos/studio.js`
The simplest demo. `session_kwargs()` passes the chosen avatar/voice/search through. Fun combos to show: Leo (painter) + Algenib (gravelly) as the sports commentator, or Vera + Search as a news anchor.

### 12. The Appraiser: `demos/appraiser.py`
- Camera vision: the professor describes real details of what you hold up.
- `consult_auction_archives` is `background=True, scheduling="WHEN_IDLE"` (line ~117). It sleeps 6 s, the professor keeps talking, and he brings up the results at the next pause. **This is the best on-stage demo of async function calling.**
- `issue_certificate` → `ctx.ui("certificate", ...)` → rendered by `js/demos/appraiser.js`.

### 13. The Interrogation Room: `demos/interrogation.py`
- The secret truth lives in the system instruction; the clue texts live in Python (`CLUES`) so the UI and server agree on them.
- `update_composure` is a `SILENT` background tool: purely cosmetic, and it never interrupts the performance.
- **`confess()` (line 111) is the key idea:** the model plays the character, but Python enforces the rules. With fewer than 3 clues (line 114) the tool refuses and tells the model to keep denying. Try accusing her in your first question.

### 14. The Polyglot Café: `demos/polyglot.py`
- `add_vocab` / `correct_me` are `SILENT` background tools, so cards appear without the barista talking about them.
- `on_action()` (line ~170): the city buttons call `session.direct(...)` to teleport the café **in the same session**. The conversation history survives, and the language switches instantly.
- Uses the docs' tip for non-English output: `RESPOND IN X. YOU MUST RESPOND UNMISTAKABLY IN X.`

### 15. Avatar Debate Club: `demos/debate.py`
- Two `AvatarSession`s, each forwarding to a different stream index (lines 71/76).
- `_debate()` is plain asyncio: `said = await me.say_and_wait(prompt)` (line ~105), then the next speaker gets `Your opponent just said: "{said}"`. The output transcription is the glue between the two agents.
- Moderator interjections queue up and are prepended to the next speaker's prompt; the verdict triggers a loser-then-winner reaction.

---

## Adding your own demo

1. Create `app/demos/mydemo.py`:

```python
from ..live_session import Tool
from .base import Demo

async def ring_bell(args, ctx):
    await ctx.ui("bell", {"times": args.get("times", 1)})   # tell the page
    return {"status": "ok"}                                   # tell the model

class MyDemo(Demo):
    id, title, emoji = "mydemo", "My Demo", "🔔"
    tagline = "An avatar that rings a bell."
    features = ["Tools"]
    avatar, voice = "Ben", "Achird"

    def system_instruction(self, options):
        return "You are a town crier. Call ring_bell before every announcement."

    def tools(self):
        return [Tool({"name": "ring_bell", "description": "Ring the bell",
                      "parameters": {"type": "object", "properties": {"times": {"type": "integer"}}}},
                     ring_bell)]
```

2. Register it in `app/demos/__init__.py`.
3. Copy `app/static/studio.html` to `mydemo.html`, point its script at `js/demos/mydemo.js`, and call `mountDemo({ demoId: "mydemo", onUi(event, data) { ... } })`.

It shows up on the home page automatically (the gallery is built from `/api/catalog`).
