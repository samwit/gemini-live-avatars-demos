"""
Demo 6: Be the Avatar. Upload a photo and talk to yourself (or anyone who's agreed).

The page crops the photo to the spec Google asks for (9:16 portrait PNG,
720x1280), and the server sends it as `avatar_config.customized_avatar`.
Gemini then animates that face live, with lip sync, in place of a prebuilt
avatar.

IMPORTANT: custom avatars are allowlisted. Unless your Google Cloud project has
been granted access (ask your account team), setup fails with "Current project
is not allowlisted for customized avatar feature", and the page shows that
message. You're also responsible for having consent from the person in the
photo. Google's rules forbid photos of minors and celebrities.

What it shows:
  * customized_avatar: a single reference image, no training or upload step
  * validating user input on the server before it reaches the model
  * the photo is only held in memory for the session and never written to disk
"""

import base64
import struct

from ..avatars import VOICES
from .base import Demo

MAX_BYTES = 5 * 1024 * 1024       # Google's limit: under 5 MB
MIN_W, MIN_H = 704, 1280          # Google's minimum portrait resolution


def png_size(data: bytes) -> tuple[int, int]:
    """Read width/height from a PNG header (no imaging library needed)."""
    if data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        raise ValueError("The photo must be a PNG. The page converts it for you, so try re-uploading.")
    return struct.unpack(">II", data[16:24])


class CustomAvatar(Demo):
    id = "custom"
    title = "Be the Avatar"
    emoji = "📸"
    tagline = "Upload a portrait and Gemini animates it live as your own talking avatar (allowlisted projects)."
    features = ["customized_avatar", "Reference photo", "Consent checks"]
    avatar = "custom"
    voice = "Aoede"

    def system_instruction(self, options):
        name = (options.get("name") or "").strip()[:40]
        persona = (options.get("persona") or "").strip()[:2000] or (
            "You are a friendly, witty assistant. Keep answers to two or three sentences."
        )
        who = f"Your name is {name}. " if name else ""
        return who + persona + "\n\nYou are appearing as a live video avatar. Speak naturally and keep turns short."

    def session_kwargs(self, options):
        # Rule 1: the person uploading must confirm consent and the photo rules.
        if not options.get("consent"):
            raise ValueError("Please confirm you have permission to use this photo before starting.")

        # Rule 2: the image must be a PNG that meets Google's size limits.
        try:
            image = base64.b64decode(options.get("image") or "", validate=True)
        except Exception:
            raise ValueError("Couldn't read the uploaded photo. Please try another image.")
        if not image:
            raise ValueError("Please upload a photo first.")
        if len(image) > MAX_BYTES:
            raise ValueError(f"The photo is {len(image) / 1e6:.1f} MB. The limit is 5 MB.")
        w, h = png_size(image)
        if w < MIN_W or h < MIN_H:
            raise ValueError(f"The photo is {w}x{h}. It needs to be at least {MIN_W}x{MIN_H} (portrait).")

        voice = options.get("voice") if options.get("voice") in VOICES else "Aoede"
        return {"custom_image": image, "custom_image_mime": "image/png", "voice": voice, "avatar": "custom"}

    def opening(self, options):
        return "(The user just brought you to life from their photo. Greet them in one short, delighted sentence.)"
