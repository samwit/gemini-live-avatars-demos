# Copyright 2026 Sam Witteveen
# SPDX-License-Identifier: Apache-2.0

"""
Demo 2: The Appraiser, an "Antiques Roadshow" for everyday junk.

Hold anything up to your webcam: a stapler, a banana, your cat. Professor
Hawthorne (the "David" avatar) examines it through the camera, invents an
absurdly grand history for it, checks the "auction archives", and issues an
official Certificate of Appraisal on screen.

What it shows:
  * live visual understanding: camera frames go to the model at 1 fps
  * tool calls that drive the UI: the certificate is rendered by the page
  * ASYNCHRONOUS function calling: `consult_auction_archives` takes ~6 seconds.
    It's marked NON_BLOCKING, so the professor keeps chatting while it runs,
    and the result arrives with scheduling=WHEN_IDLE. He mentions it at the
    next natural pause instead of going silent.
"""

import asyncio
import hashlib
import random

from ..live_session import Tool
from .base import Demo

SYSTEM = """\
You are Professor Percival Hawthorne, a gloriously pompous antiques appraiser on a
television show called "The Appraiser". You are appearing as a live video avatar and
you can see the guest through their camera.

How the show works:
1. Greet the guest and ask them to hold their item up to the camera.
2. When you can see an item clearly, call `begin_appraisal` with what you see.
   Describe genuine visual details (colour, wear, markings) so they know you really see it.
3. Invent a wildly grand, funny, but internally consistent history for the item.
   Ask the guest one question about where they got it.
4. Call `consult_auction_archives` for comparable sales. This takes a few moments and
   runs in the background, so keep chatting while you wait.
5. When the archive results arrive, react to them dramatically, then call
   `issue_certificate` with your final valuation.
6. Invite them to bring the next item.

Style: theatrical, erudite, warm, with short spoken sentences (this is live TV, not an
essay). Treat mundane objects as priceless artifacts. If you can't see an item clearly,
say so and ask them to hold it closer. If the guest describes an item in text (for example,
they have no camera), take their description at face value and appraise that. Never claim the valuations are real; you may
wink at the audience about it.
"""


# ---------------------------------------------------------------------------------
# Tool handlers. Each gets (args, ctx) and returns a dict for the model.
# `ctx.ui(event, data)` pushes a widget update to the browser.
# ---------------------------------------------------------------------------------

async def begin_appraisal(args, ctx):
    ctx.state["item"] = args.get("item_name", "a mystery object")
    await ctx.ui("appraisal_started", args)
    return {"status": "ok", "message": "The item is now on the appraisal table."}


async def consult_auction_archives(args, ctx):
    """Pretend to search decades of auction records. Deliberately slow."""
    item = args.get("item_name", ctx.state.get("item", "item"))
    await ctx.ui("archives_searching", {"item_name": item})

    await asyncio.sleep(6)  # the slow part; the avatar keeps talking meanwhile

    # Deterministic fake data, so the same item always gets the same "history".
    rng = random.Random(hashlib.md5(item.lower().encode()).hexdigest())
    houses = ["Sotheby's of Lower Wessex", "Christie's Discount Annex", "The Royal Garage Sale",
              "Bonhams-by-the-Sea", "Phillips & Nephew", "The Vatican Car Boot Sale"]
    sales = []
    for _ in range(3):
        sales.append({
            "house": rng.choice(houses),
            "year": rng.randint(1851, 2025),
            "lot": f"A remarkably similar {item}",
            "hammer_price_usd": rng.choice([12, 85, 400, 2_300, 17_500, 98_000, 1_250_000]),
        })
    result = {"status": "ok", "item_name": item, "comparable_sales": sales}
    await ctx.ui("archives_result", result)
    return result


async def issue_certificate(args, ctx):
    await ctx.ui("certificate", args)
    return {"status": "ok", "message": "Certificate displayed on screen for the guest."}


TOOLS = [
    Tool(
        declaration={
            "name": "begin_appraisal",
            "description": "Put the item the guest is showing on the appraisal table. Call once per new item.",
            "parameters": {
                "type": "object",
                "properties": {
                    "item_name": {"type": "string", "description": "Short name, e.g. 'red stapler'"},
                    "first_impression": {"type": "string", "description": "One-line visual first impression"},
                },
                "required": ["item_name"],
            },
        },
        handler=begin_appraisal,
    ),
    Tool(
        declaration={
            "name": "consult_auction_archives",
            "description": "Search historical auction records for comparable sales. Slow: takes several seconds; keep talking meanwhile.",
            "parameters": {
                "type": "object",
                "properties": {"item_name": {"type": "string"}},
                "required": ["item_name"],
            },
        },
        handler=consult_auction_archives,
        background=True,          # NON_BLOCKING: the avatar keeps talking
        scheduling="WHEN_IDLE",   # report back at the next natural pause
    ),
    Tool(
        declaration={
            "name": "issue_certificate",
            "description": "Display the official Certificate of Appraisal on the guest's screen.",
            "parameters": {
                "type": "object",
                "properties": {
                    "item_name": {"type": "string"},
                    "era": {"type": "string", "description": "e.g. 'Late Victorian, circa 1887'"},
                    "provenance": {"type": "string", "description": "Two-sentence invented history"},
                    "low_estimate_usd": {"type": "integer"},
                    "high_estimate_usd": {"type": "integer"},
                    "rarity": {"type": "integer", "description": "1 (common) to 5 (unique)"},
                    "remark": {"type": "string", "description": "A witty closing remark"},
                },
                "required": ["item_name", "era", "provenance", "low_estimate_usd", "high_estimate_usd", "rarity"],
            },
        },
        handler=issue_certificate,
    ),
]


class Appraiser(Demo):
    id = "appraiser"
    title = "The Appraiser"
    emoji = "🔍"
    tagline = "Hold any object up to your webcam. A pompous professor values it and issues a certificate."
    features = ["Camera vision", "Tools → UI", "Async tools (WHEN_IDLE)"]
    avatar = "David"
    voice = "Sadaltager"

    def system_instruction(self, options):
        return SYSTEM

    def tools(self):
        return TOOLS

    def opening(self, options):
        return "(The guest has just sat down. Welcome them to the show in two short sentences.)"
