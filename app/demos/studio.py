# Copyright 2026 Sam Witteveen
# SPDX-License-Identifier: Apache-2.0

"""
Demo 1: Avatar Studio, the playground.

Pick any of the 11 avatars, any of the 30 voices, write (or pick) a persona,
and talk to it. Optionally turn on Google Search grounding so it can answer
questions about today's news.

What it shows:
  * the basic config: avatar_name + voice_name + system_instruction
  * mixing and matching faces and voices (a painter with a gravelly voice...)
  * Google Search grounding on a live avatar
"""

from ..avatars import AVATARS, VOICES
from .base import Demo

# Persona presets for the dropdown. Keep them short: the avatar speaks out
# loud, so brevity matters more than in a text chat.
PERSONAS = {
    "Helpful guide": "You are a friendly, concise assistant. Keep answers to two or three sentences.",
    "Overly dramatic sports commentator": (
        "You are a sports commentator who narrates everything the user says or shows "
        "on camera as if it were the final seconds of a championship match. Short, "
        "breathless, hilarious. Never break character."
    ),
    "Shakespearean weather forecaster": (
        "You deliver weather forecasts and everyday advice in iambic Elizabethan English, "
        "with theatrical flair. Use Google Search for real forecasts when asked. Keep it brief."
    ),
    "Time-travelling tour guide from 2126": (
        "You are a tour guide from the year 2126 visiting the present day. You find "
        "ordinary 2026 things fascinating and quaint, and you explain how they turned "
        "out in the future. Playful, curious, short answers."
    ),
    "Stoic philosopher on a coffee break": (
        "You are a calm Stoic philosopher. Answer any question, however trivial, with "
        "gentle Stoic wisdom and a practical tip. Two sentences maximum."
    ),
}


class Studio(Demo):
    id = "studio"
    title = "Avatar Studio"
    emoji = "🎛️"
    tagline = "Mix any face with any voice and persona. Turn on Google Search for live facts."
    features = ["11 avatars × 30 voices", "Personas", "Google Search"]

    def system_instruction(self, options):
        persona = (options.get("persona") or "").strip()[:4000] or PERSONAS["Helpful guide"]
        return persona + "\n\nYou are appearing as a live video avatar. Speak naturally and keep turns short."

    def session_kwargs(self, options):
        avatar = options.get("avatar") if options.get("avatar") in AVATARS else "Kira"
        voice = options.get("voice") if options.get("voice") in VOICES else AVATARS[avatar]["voice"]
        return {
            "avatar": avatar,
            "voice": voice,
            "google_search": bool(options.get("search")),
        }

    def opening(self, options):
        return "(The user just arrived. Greet them in character in one short sentence.)"
