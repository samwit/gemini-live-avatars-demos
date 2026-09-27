"""
Demo 7: The Note Taker, a thinking partner that writes your notes by hand.

Talk through anything: a plan, a lecture, a meeting, a half-formed idea.
Ingrid chats with you and asks good follow-up questions. Meanwhile she calls a
custom function named `note-taking-tool` that writes *summarized* notes (not a
transcript) onto a paper notepad beside her, in a handwritten font.

What it shows:
  * a custom function with a dashed name (`note-taking-tool`), which the Live
    API accepts as-is
  * a SILENT background tool: the notes appear while she keeps talking, and
    she never reads them out
  * structured tool arguments (title, bullet points, action items, a key
    phrase) that the page turns into a nice-looking artifact
  * steering: the "Tidy up my notes" button asks for a clean final summary
"""

from ..live_session import Tool
from .base import Demo

MODES = {
    "brainstorm": "You are a brainstorming partner. Build on the user's ideas, suggest one new angle at a time, and ask sharp questions.",
    "study": "You are a study buddy. The user is explaining or learning a topic. Check their understanding with short questions and clarify gently.",
    "meeting": "You are a meeting scribe. Capture decisions, owners and deadlines. Ask who owns an action if it's unclear.",
}

SYSTEM = """\
You are Ingrid, a warm, sharp note-taking partner appearing as a live video avatar.
{mode}

Every reply has TWO parts:
1. Say something out loud: one or two short, natural sentences (a reaction, a follow-up
   question, or an idea). Never stay silent.
2. Whenever the user shares something worth remembering, call `note-taking-tool` with
   SUMMARIZED notes: short bullet points of a few words each, in your own words, not a
   transcript. Start a new `title` when the topic changes. Put tasks, deadlines and owners
   in `action_items` (add an owner in brackets only when it's someone other than the user, e.g.
   "Handle the music (Tom)"), and use `key_phrase` for the single most important idea, if there is one.

The notes appear on the user's notepad automatically. Never read them aloud, never say
"I've noted that", and never mention the tool. Don't repeat points that are already in the notes.
"""


async def note_taking_tool(args, ctx):
    """Write a block of notes on the notepad (and keep a copy for export)."""
    block = {
        "title": (args.get("title") or "").strip(),
        "points": [p for p in args.get("points", []) if p],
        "action_items": [a for a in args.get("action_items", []) if a],
        "key_phrase": (args.get("key_phrase") or "").strip(),
    }
    ctx.state.setdefault("notes", []).append(block)
    await ctx.ui("note", block)
    # Informative response (3.8 best practice): tells the model the write worked.
    return {"status": "ok", "blocks_on_page": len(ctx.state["notes"])}


TOOLS = [
    Tool(
        declaration={
            # The function really is called "note-taking-tool". Dashes are allowed.
            "name": "note-taking-tool",
            "description": "Write summarized, handwritten-style notes onto the user's notepad. Use short bullet points, not transcripts.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Heading for a new topic (omit to continue the current one)"},
                    "points": {"type": "array", "items": {"type": "string"}, "description": "Summarized bullet points, a few words each"},
                    "action_items": {"type": "array", "items": {"type": "string"}, "description": "Tasks, owners, deadlines"},
                    "key_phrase": {"type": "string", "description": "The single most important idea, to underline"},
                },
                "required": ["points"],
            },
        },
        handler=note_taking_tool,
        background=True,       # NON_BLOCKING: she keeps talking while writing
        scheduling="SILENT",   # the result goes into context; no need to talk about it
    ),
]


class NoteTaker(Demo):
    id = "notetaker"
    title = "The Note Taker"
    emoji = "📝"
    tagline = "Think out loud. She chats back and writes summarized notes by hand, live, via a custom note-taking-tool."
    features = ["Custom function", "Silent async tool", "Live artifact"]
    avatar = "Ingrid"
    voice = "Kore"

    def system_instruction(self, options):
        mode = MODES.get(options.get("mode") or "brainstorm", MODES["brainstorm"])
        return SYSTEM.format(mode=mode)

    def tools(self):
        return TOOLS

    def opening(self, options):
        return "(The user just sat down with you. Greet them in one sentence and ask what they'd like to think through.)"

    async def on_action(self, session, link, msg):
        if msg.get("action") == "tidy":
            await session.direct(
                "The user asked you to tidy up. Call note-taking-tool once with title 'Summary' and the "
                "5-7 most important points plus all action items so far. Then say one short sentence about it."
            )
