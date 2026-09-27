# Copyright 2026 Sam Witteveen
# SPDX-License-Identifier: Apache-2.0

"""
Demo 4: The Polyglot Café, language immersion with a teleporting barista.

Piper runs a café that teleports around the world. Order a coffee in French in
Paris, then hit "Tokyo" and the same barista greets you in Japanese, without
reconnecting. Vocabulary cards and gentle corrections pile up beside the
video while you talk, and your order gets rung up in the local currency.

What it shows:
  * multilingual speech: 97 languages, automatic language detection
  * steering a live session: the city buttons send a stage direction into
    the running session (no reconnect, and the conversation history is kept)
  * SILENT async tools: vocab cards and corrections are fire-and-forget, so
    the barista never stops the conversation to talk about them
"""

from ..live_session import Tool
from .base import Demo

CITIES = {
    "paris":    {"city": "Paris",       "cafe": "Le Petit Zinc",        "language": "French",     "currency": "EUR"},
    "tokyo":    {"city": "Tokyo",       "cafe": "Kissa Hoshizora",      "language": "Japanese",   "currency": "JPY"},
    "mexico":   {"city": "Mexico City", "cafe": "Café La Jacaranda",    "language": "Spanish",    "currency": "MXN"},
    "rome":     {"city": "Rome",        "cafe": "Bar Trastevere",       "language": "Italian",    "currency": "EUR"},
    "seoul":    {"city": "Seoul",       "cafe": "Dal-bit Coffee",       "language": "Korean",     "currency": "KRW"},
    "berlin":   {"city": "Berlin",      "cafe": "Kaffeehaus Kreuzberg", "language": "German",     "currency": "EUR"},
    "saopaulo": {"city": "São Paulo",   "cafe": "Padaria Vila Madalena", "language": "Portuguese", "currency": "BRL"},
    "mumbai":   {"city": "Mumbai",      "cafe": "Irani Chai House",     "language": "Hindi",      "currency": "INR"},
}

LEVELS = {
    "beginner": "The customer is a BEGINNER. Speak slowly, use very simple words and short sentences. After each thing you say, add a quick English hint in brackets only if they seem lost.",
    "intermediate": "The customer is INTERMEDIATE. Speak at a natural but clear pace. Use English only if they ask.",
    "advanced": "The customer is ADVANCED. Speak at full native speed with local slang and idioms. Never use English.",
}


def place_prompt(key: str) -> str:
    c = CITIES[key]
    return (f"You are now working at {c['cafe']} in {c['city']}. Speak ONLY {c['language']} "
            f"(RESPOND IN {c['language'].upper()}. YOU MUST RESPOND UNMISTAKABLY IN {c['language'].upper()}.) "
            f"Prices are in {c['currency']}.")


SYSTEM = """\
You are Piper, a warm, witty barista in a magical café that teleports between cities.
You are a live video avatar; speak in short, natural, spoken turns like a real barista.
You are helping the customer practise a language by chatting and taking their order.

{place}
{level}

Teaching tools. These run silently and put cards on the customer's screen. Use them on EVERY
turn, but NEVER mention them out loud:
- Each time you reply, call `add_vocab` for one useful word or phrase you just used.
- Whenever the customer's message has any mistake (grammar, spelling, missing accents, wrong
  word, or English mixed in), call `correct_me` with what they said and the natural version.
  Out loud, just reply naturally and model the correct form. Don't lecture.
- When they finish ordering, call `ring_up_order` with the items and local prices, then tell
  them the total in the local language.
You can also see them through their camera if it's on; if they hold something up, teach its name.
"""


# --- tool handlers ---------------------------------------------------------------------

async def add_vocab(args, ctx):
    await ctx.ui("vocab", args)
    return {"status": "ok"}


async def correct_me(args, ctx):
    await ctx.ui("correction", args)
    return {"status": "ok"}


async def ring_up_order(args, ctx):
    items = args.get("items", [])
    total = round(sum(float(i.get("price", 0)) for i in items), 2)
    currency = CITIES[ctx.state.get("city", "paris")]["currency"]
    await ctx.ui("receipt", {"items": items, "total": total, "currency": currency,
                             "cafe": CITIES[ctx.state.get("city", "paris")]["cafe"]})
    return {"status": "ok", "total": total, "currency": currency}


TOOLS = [
    Tool(
        declaration={
            "name": "add_vocab",
            "description": "Add a vocabulary card to the customer's screen.",
            "parameters": {
                "type": "object",
                "properties": {
                    "word": {"type": "string", "description": "Word/phrase in the local language (native script)"},
                    "romanization": {"type": "string", "description": "Pronunciation in Latin letters, if non-Latin script"},
                    "meaning": {"type": "string", "description": "English meaning"},
                    "example": {"type": "string", "description": "Short example sentence"},
                },
                "required": ["word", "meaning"],
            },
        },
        handler=add_vocab, background=True, scheduling="SILENT",
    ),
    Tool(
        declaration={
            "name": "correct_me",
            "description": "Show a gentle correction card for something the customer said.",
            "parameters": {
                "type": "object",
                "properties": {
                    "you_said": {"type": "string"},
                    "better": {"type": "string"},
                    "why": {"type": "string", "description": "Very short English explanation"},
                },
                "required": ["you_said", "better"],
            },
        },
        handler=correct_me, background=True, scheduling="SILENT",
    ),
    Tool(
        declaration={
            "name": "ring_up_order",
            "description": "Ring up the customer's order and show a receipt. Prices in local currency.",
            "parameters": {
                "type": "object",
                "properties": {
                    "items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {"name": {"type": "string"}, "price": {"type": "number"}},
                            "required": ["name", "price"],
                        },
                    }
                },
                "required": ["items"],
            },
        },
        handler=ring_up_order,
    ),
]


class Polyglot(Demo):
    id = "polyglot"
    title = "The Polyglot Café"
    emoji = "☕"
    tagline = "Order coffee in 8 cities. Teleport mid-conversation, and collect vocab cards and corrections as you go."
    features = ["Multilingual", "Mid-session steering", "Silent async tools"]
    avatar = "Piper"
    voice = "Leda"

    def _city(self, options):
        return options.get("city") if options.get("city") in CITIES else "paris"

    def system_instruction(self, options):
        level = LEVELS.get(options.get("level", "beginner"), LEVELS["beginner"])
        return SYSTEM.format(place=place_prompt(self._city(options)), level=level)

    def tools(self):
        return TOOLS

    def session_kwargs(self, options):
        # Seed the per-session state so ring_up_order knows the currency.
        return {"state": {"city": self._city(options)}}

    def opening(self, options):
        return "(A customer just walked in. Greet them warmly in one short sentence and ask what they'd like.)"

    async def on_action(self, session, link, msg):
        """The city buttons: teleport the café without reconnecting."""
        if msg.get("action") == "teleport" and msg.get("city") in CITIES:
            key = msg["city"]
            session.ctx.state["city"] = key
            await link.ui("teleported", {"key": key, **CITIES[key]})
            await session.direct(
                "The café has just magically teleported! " + place_prompt(key) +
                " React with delight to the new city in one sentence, in the new language, "
                "then ask the customer what they'd like."
            )
