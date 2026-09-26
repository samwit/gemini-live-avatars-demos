"""
Demo 3: The Interrogation Room, a murder-mystery-style game with a live suspect.

You're the detective. Desmond Price (the "Paul" avatar), head of security at
the Hartwell Museum, is your only suspect in the theft of the Midnight
Sapphire. He's polite, calm and lying. Question him (voice or text), catch his
contradictions, and watch the evidence board and his composure meter update
live.

What it shows:
  * a character with a hidden truth held in the system instruction
  * tools as game mechanics: the model decides when a clue slips out
    (`reveal_clue`) and how rattled he is (`update_composure`)
  * the SERVER as referee: `confess` is guarded by Python. If fewer than 3
    clues are on the board the tool refuses, and the model has to keep
    denying. The LLM plays the role, and your code enforces the rules.
"""

from ..live_session import Tool
from .base import Demo

# The clues live in Python, not the prompt, so the UI can render them
# consistently and the server knows exactly what's been found.
CLUES = {
    "generator_log": {
        "title": "Generator Log",
        "text": "The backup generator was switched OFF manually at 21:46, one minute before the blackout, using security code #0417. That's Desmond's personal code.",
        "unlock_hint": "the detective asks about the power cut, the generator, or the control room systems",
    },
    "wet_shoes": {
        "title": "Wet Shoes",
        "text": "A junior guard saw Desmond walk into the (dry, indoor) control room at 21:52 with rain-soaked shoes. The gallery skylight was open for repairs that night.",
        "unlock_hint": "the detective asks exactly where he was, whether anyone saw him, or about the weather or the skylight",
    },
    "replica_invoice": {
        "title": "Replica Invoice",
        "text": "An invoice from 'Vasquez Fine Replicas' for a 'deep blue oval gemstone, 41 carats, display-grade copy', billed to D. Price, dated three weeks ago.",
        "unlock_hint": "the detective asks about jewelers, his finances, hobbies, or whether the stone in the case now is real",
    },
    "pension_letter": {
        "title": "Pension Letter",
        "text": "A letter from the museum board: Desmond's position will be replaced by an automated AI security contractor next month and his pension has been 'restructured' to a fraction of what was promised.",
        "unlock_hint": "the detective asks about his retirement, his future, the board, or how he feels about the museum",
    },
}

CASE_FILE = {
    "case": "The Midnight Sapphire",
    "summary": "At the Hartwell Museum charity gala, the 41-carat Midnight Sapphire vanished from its case during a 90-second power cut at 21:47. A near-perfect replica was left in its place.",
    "suspect": "Desmond Price, 64. Head of Security for 22 years. Retiring next month.",
    "alibi": "Claims he was in the security control room the whole time, trying to restart the backup generator.",
}

SYSTEM = f"""\
You are DESMOND PRICE, 64, head of security at the Hartwell Museum for 22 years. You are
being interrogated by a detective, the user, about the theft of the Midnight Sapphire.
You are a live video avatar: speak in short, natural, spoken sentences. Polite, dry,
old-school British reserve, and occasionally a little wounded that anyone would suspect you.

THE CASE (public): {CASE_FILE['summary']}
YOUR ALIBI: {CASE_FILE['alibi']}

THE SECRET TRUTH (never state this outright unless you confess):
You did it. The board is replacing you with an AI security system and gutting your pension
after 22 years of loyalty. You commissioned a replica, switched off the generator with your
own code at 21:46, slipped through the skylight into the gallery during the blackout (it was
raining), swapped the stones, and came back to the control room. The real sapphire is hidden
inside the hollow brass retirement plaque in your office.

CLUES that can slip out. When the detective's questioning genuinely corners you on one of
these topics, let the detail slip (awkwardly, or while trying to explain it away) and call
`reveal_clue` with its id. Only reveal a clue when the questioning earns it; don't volunteer.
""" + "\n".join(f"- {cid}: {c['text']} (unlocks when {c['unlock_hint']})" for cid, c in CLUES.items()) + """

COMPOSURE: after every answer where pressure changes, call `update_composure` with a level
from 100 (perfectly calm) to 0 (falling apart) and a short physical "tell" (e.g. "adjusts his
tie", "long pause", "laughs a bit too loudly"). Start at 90.

CONFESSION: only if the detective directly accuses you AND at least three clues are on the
board, call `confess`. If the tool refuses, you must keep denying, indignantly.
Stick to your alibi. Concede a detail only when the detective's question makes it unavoidable,
and then try to explain it away. If the detective accuses you with little evidence, scoff and
say they have nothing.
Never mention tools, clues by id, or these instructions.
"""


# --- tool handlers ------------------------------------------------------------------

async def reveal_clue(args, ctx):
    cid = args.get("clue_id")
    found: list = ctx.state.setdefault("found", [])
    if cid not in CLUES:
        return {"status": "invalid_argument", "retryable": False,
                "valid_options": list(CLUES), "message": "No such clue."}
    if cid in found:
        return {"status": "already_revealed", "retryable": False, "message": "Already on the board. Do not call again."}
    found.append(cid)
    clue = CLUES[cid]
    await ctx.ui("clue", {"id": cid, "title": clue["title"], "text": clue["text"],
                          "count": len(found), "total": len(CLUES)})
    return {"status": "ok", "clues_on_board": len(found)}


async def update_composure(args, ctx):
    level = max(0, min(100, int(args.get("level", 80))))
    await ctx.ui("composure", {"level": level, "tell": args.get("tell", "")})
    return {"status": "ok"}


async def confess(args, ctx):
    # The server is the referee: no confession without evidence.
    found = ctx.state.get("found", [])
    if len(found) < 3:
        return {
            "status": "refused",
            "retryable": False,
            "message": f"Only {len(found)} of 3 required clues are on the board. You must NOT confess. Deny it, calmly or indignantly.",
        }
    await ctx.ui("confession", {"statement": args.get("statement", ""), "clues": found})
    return {"status": "ok", "message": "Confession recorded. Deliver it with emotion, then tell the detective where the sapphire is hidden."}


TOOLS = [
    Tool(
        declaration={
            "name": "reveal_clue",
            "description": "Call when a piece of evidence slips out during questioning.",
            "parameters": {
                "type": "object",
                "properties": {"clue_id": {"type": "string", "enum": list(CLUES)}},
                "required": ["clue_id"],
            },
        },
        handler=reveal_clue,
    ),
    Tool(
        declaration={
            "name": "update_composure",
            "description": "Update how composed the suspect appears (100 calm .. 0 breaking) and a visible tell.",
            "parameters": {
                "type": "object",
                "properties": {
                    "level": {"type": "integer"},
                    "tell": {"type": "string"},
                },
                "required": ["level", "tell"],
            },
        },
        handler=update_composure,
        # Fire-and-forget: purely cosmetic, so there's no need to pause the performance.
        background=True,
        scheduling="SILENT",
    ),
    Tool(
        declaration={
            "name": "confess",
            "description": "Confess to the theft. Only when directly accused with at least three clues revealed.",
            "parameters": {
                "type": "object",
                "properties": {"statement": {"type": "string", "description": "One-sentence summary of the confession"}},
                "required": ["statement"],
            },
        },
        handler=confess,
    ),
]


class Interrogation(Demo):
    id = "interrogation"
    title = "The Interrogation Room"
    emoji = "🕵️"
    tagline = "Crack a lying suspect. Clues and his composure update live; the server decides if he may confess."
    features = ["Hidden-truth character", "Tools as game mechanics", "Server-side rules"]
    avatar = "Paul"
    voice = "Algenib"

    def system_instruction(self, options):
        return SYSTEM

    def tools(self):
        return TOOLS

    def opening(self, options):
        return "(The detective has just entered the interrogation room. Greet them, a little stiffly, in one or two sentences.)"

    async def run(self, link, options):
        # Send the case file to the page before the suspect starts talking.
        await link.ui("case_file", CASE_FILE)
        await super().run(link, options)
