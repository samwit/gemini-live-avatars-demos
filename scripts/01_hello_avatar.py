# Copyright 2026 Sam Witteveen
# SPDX-License-Identifier: Apache-2.0

"""
01 - Hello, Avatar: the smallest useful Live Avatar program.

Sends one text prompt to gemini-3.8-live with an avatar enabled and saves the
avatar's spoken reply as an MP4 you can open in any video player.

    uv run python scripts/01_hello_avatar.py "Tell me a joke about a rabbit"
    uv run python scripts/01_hello_avatar.py "Explain black holes to a 5 year old" --avatar Leo --voice Algieba

The four ideas to take away:
  1. response_modalities=["VIDEO"] is what turns the avatar on.
  2. avatar_config picks the face, speech_config picks the voice.
  3. The reply arrives as a stream of fragmented-MP4 chunks, with audio included.
  4. Concatenating the chunks in order gives you a valid MP4 file.
"""

import argparse
import asyncio
import os
import sys
import time

# Let the script import the shared auth helper from app/config.py.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from google.genai import types  # noqa: E402

from app.avatars import api_name  # noqa: E402
from app.config import MODEL, make_client  # noqa: E402


async def main(prompt: str, avatar: str, voice: str, out: str) -> None:
    client = make_client()  # Agent Platform client (API key or ADC, see app/config.py)

    config = types.LiveConnectConfig(
        # (1) VIDEO output = avatar mode.
        response_modalities=["VIDEO"],
        # (2) Which face...
        avatar_config=types.AvatarConfig(avatar_name=api_name(avatar)),
        # ...and which voice.
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice)
            )
        ),
        system_instruction="You are a warm, witty presenter. Keep answers under 30 seconds.",
        # Also send back a text transcript of what the avatar says.
        output_audio_transcription=types.AudioTranscriptionConfig(),
    )

    t0 = time.time()
    async with client.aio.live.connect(model=MODEL, config=config) as session:
        print(f"Connected to {MODEL} as {avatar} ({voice}) in {time.time() - t0:.1f}s")

        await session.send_realtime_input(text=prompt)

        chunks: list[bytes] = []
        # receive() yields every server message for one model turn.
        async for message in session.receive():
            content = message.server_content
            if not content:
                continue

            # (3) Each part's inline_data is a chunk of fMP4 (mime type video/mp4).
            if content.model_turn:
                for part in content.model_turn.parts or []:
                    if part.inline_data and part.inline_data.data:
                        if not chunks:
                            print(f"First video chunk after {time.time() - t0:.1f}s")
                        chunks.append(part.inline_data.data)

            if content.output_transcription and content.output_transcription.text:
                print(content.output_transcription.text, end="", flush=True)

            if content.turn_complete:
                break

    # (4) The chunks are one continuous fragmented MP4, so write them out in order.
    with open(out, "wb") as f:
        f.write(b"".join(chunks))
    size_mb = sum(map(len, chunks)) / 1e6
    print(f"\n\nSaved {len(chunks)} chunks ({size_mb:.1f} MB) to {out}")
    print("Tip: the avatar idles before it speaks, so the video starts with a second or two of listening.")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("prompt", nargs="?", default="Introduce yourself in two sentences.")
    p.add_argument("--avatar", default="Kai", help="Jay, Paul, David, Ingrid, Kira, Vera, Ben, Kai, Leo, Carmen, Piper")
    p.add_argument("--voice", default="Puck", help="Any of the 30 prebuilt voices, e.g. Puck, Kore, Charon")
    p.add_argument("--out", default="hello_avatar.mp4")
    args = p.parse_args()
    asyncio.run(main(args.prompt, args.avatar, args.voice, args.out))
