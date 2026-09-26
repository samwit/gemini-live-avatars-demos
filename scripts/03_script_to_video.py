"""
03 - Script to video: use a *live* API as a talking-head video generator.

Give it a text file of paragraphs and a presenter reads them one by one. Out
comes a single MP4, with natural idle moments (blinks, breaths) between lines,
because the avatar's video stream never stops.

    uv run python scripts/03_script_to_video.py scripts/sample_script.txt --avatar Sam --voice Charon

Handy for product walkthroughs, course intros, or localised versions of the
same script. Add --translate Spanish and the presenter reads it in Spanish.

How it works: one Live session, a strict "teleprompter" system instruction,
and every chunk of the continuous fMP4 stream is recorded from connect until
shortly after the last line finishes.
"""

import argparse
import asyncio
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from google.genai import types  # noqa: E402

from app.config import MODEL, make_client  # noqa: E402

TELEPROMPTER = """\
You are a professional presenter reading from a teleprompter on camera.
When you receive text, read it out loud EXACTLY as written, word for word, with natural,
engaging delivery. Do not add greetings, comments, questions or anything else.
Do not respond to the content; just perform it."""


async def main(path: str, avatar: str, voice: str, out: str, translate: str | None) -> None:
    text = open(path, encoding="utf-8").read()
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    print(f"{len(paragraphs)} paragraphs to read as {avatar} ({voice})")

    instruction = TELEPROMPTER
    if translate:
        instruction += f"\nThe text is in English, but perform it translated into {translate}. Speak only {translate}."

    config = types.LiveConnectConfig(
        response_modalities=["VIDEO"],
        avatar_config=types.AvatarConfig(avatar_name=avatar),  # full default bitrate for recordings
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice))
        ),
        system_instruction=instruction,
        output_audio_transcription=types.AudioTranscriptionConfig(),
    )

    video = bytearray()
    turn_done = asyncio.Event()

    async with make_client().aio.live.connect(model=MODEL, config=config) as session:

        async def record():
            # The stream is continuous, so keep receiving across turns.
            while True:
                async for msg in session.receive():
                    sc = msg.server_content
                    if not sc:
                        continue
                    for part in (sc.model_turn.parts if sc.model_turn else None) or []:
                        if part.inline_data and part.inline_data.data:
                            video.extend(part.inline_data.data)
                    if sc.output_transcription and sc.output_transcription.text:
                        print(sc.output_transcription.text, end="", flush=True)
                    if sc.turn_complete:
                        turn_done.set()

        recorder = asyncio.create_task(record())
        await asyncio.sleep(1.0)  # a beat of idle presenter before the first line

        for i, para in enumerate(paragraphs, 1):
            print(f"\n[{i}/{len(paragraphs)}] ", end="")
            turn_done.clear()
            await session.send_realtime_input(text=para)
            await asyncio.wait_for(turn_done.wait(), timeout=180)
            await asyncio.sleep(0.6)  # small natural pause between paragraphs

        await asyncio.sleep(1.5)  # let the last words finish streaming
        recorder.cancel()

    raw = out.replace(".mp4", ".fragmented.mp4")
    open(raw, "wb").write(video)
    print(f"\n\nRecorded {len(video) / 1e6:.1f} MB")

    # Fragmented MP4 plays fine in browsers and VLC. For editors (Premiere, Final Cut)
    # and social uploads, remux it into a regular MP4 (no re-encode, takes a second).
    if shutil.which("ffmpeg"):
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", raw, "-c", "copy", "-movflags", "+faststart", out], check=True)
        os.remove(raw)
        print(f"Saved {out}")
    else:
        print(f"Saved {raw} (install ffmpeg to also get a regular MP4)")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("script", nargs="?", default=os.path.join(os.path.dirname(__file__), "sample_script.txt"))
    p.add_argument("--avatar", default="Sam")
    p.add_argument("--voice", default="Charon")
    p.add_argument("--out", default="presenter.mp4")
    p.add_argument("--translate", help="Perform the script in another language, e.g. Japanese")
    a = p.parse_args()
    asyncio.run(main(a.script, a.avatar, a.voice, a.out, a.translate))
