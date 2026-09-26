"""
02 - The raw wire protocol: Live Avatar over a plain WebSocket, no SDK.

Everything the SDK does, spelled out as JSON messages. Read this one to see
what's actually on the wire, or if you're porting to a language without an SDK.

    uv run python scripts/02_raw_websocket.py "What's the best thing about Tuesdays?"

The conversation is:

    client → {"setup": {...}}                        once, first message
    server → {"setupComplete": {"sessionId": ...}}
    client → {"realtime_input": {"text": "..."}}     (or audio / video blobs)
    server → {"serverContent": {"modelTurn": {"parts": [{"inlineData": {"mimeType": "video/mp4", "data": <base64>}}]}}}
    server → {"serverContent": {"outputTranscription": {"text": "..."}}}
    server → {"serverContent": {"turnComplete": true}}
    server → {"usageMetadata": {...}}
"""

import argparse
import asyncio
import base64
import json
import os
import sys

import websockets

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app import config  # noqa: E402


def endpoint_and_auth() -> tuple[str, dict, str]:
    """Build the regional WebSocket URL, auth headers and model resource name."""
    loc = config.LOCATION
    host = "aiplatform.googleapis.com" if loc == "global" else f"{loc}-aiplatform.googleapis.com"
    url = f"wss://{host}/ws/google.cloud.aiplatform.v1.LlmBidiService/BidiGenerateContent"

    use_key = config.AUTH_MODE == "api_key" or (config.AUTH_MODE == "auto" and config.API_KEY)
    if use_key:
        # Express mode / API key: the key identifies the project.
        headers = {"x-goog-api-key": config.API_KEY}
        model = f"publishers/google/models/{config.MODEL}"
    else:
        # OAuth bearer token from ADC (or the gcloud CLI).
        creds = config._credentials()
        headers = {"Authorization": f"Bearer {creds.token}"}
        model = f"projects/{config.PROJECT}/locations/{loc}/publishers/google/models/{config.MODEL}"
    return url, headers, model


async def main(prompt: str, avatar: str, voice: str, out: str) -> None:
    url, headers, model = endpoint_and_auth()

    async with websockets.connect(url, additional_headers=headers, max_size=None) as ws:
        # 1) Setup: everything about the session, sent once.
        await ws.send(json.dumps({
            "setup": {
                "model": model,
                "generation_config": {
                    "response_modalities": ["VIDEO"],
                    "speech_config": {"voice_config": {"prebuilt_voice_config": {"voice_name": voice}}},
                },
                "avatar_config": {"avatar_name": avatar},
                "system_instruction": {"parts": [{"text": "You are a cheerful presenter. Be brief."}]},
                "output_audio_transcription": {},
            }
        }))
        print("←", (await ws.recv())[:120])  # {"setupComplete": ...}

        # 2) User input. Audio would be {"audio": {"mime_type": "audio/pcm;rate=16000", "data": b64}},
        #    and a camera frame {"video": {"mime_type": "image/jpeg", "data": b64}}.
        await ws.send(json.dumps({"realtime_input": {"text": prompt}}))

        # 3) Read server messages until the turn is complete.
        video = bytearray()
        async for raw in ws:
            msg = json.loads(raw)
            content = msg.get("serverContent", {})

            for part in content.get("modelTurn", {}).get("parts", []):
                if "inlineData" in part:
                    blob = part["inlineData"]
                    chunk = base64.b64decode(blob["data"])  # JSON carries base64
                    if not video:
                        print(f"← first chunk: {blob.get('mimeType')}, starts with {chunk[4:8]!r} (ftyp = MP4 header)")
                    video += chunk

            if "outputTranscription" in content:
                print("← transcript:", content["outputTranscription"].get("text", ""))
            if "usageMetadata" in msg:
                print("← usage:", {k: v for k, v in msg["usageMetadata"].items() if k.endswith("Count")})
            if content.get("turnComplete"):
                print("← turnComplete")
                break

    open(out, "wb").write(video)
    print(f"Saved {len(video) / 1e6:.1f} MB to {out}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("prompt", nargs="?", default="Say hello and tell me one fun fact.")
    p.add_argument("--avatar", default="Vera")
    p.add_argument("--voice", default="Gacrux")
    p.add_argument("--out", default="raw_websocket.mp4")
    a = p.parse_args()
    asyncio.run(main(a.prompt, a.avatar, a.voice, a.out))
