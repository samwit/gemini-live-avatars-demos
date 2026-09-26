"""
Catalog of the prebuilt avatars and voices.

Avatar names come from Google's intro_live_avatar notebook and were checked
against the live API. An unknown name fails at setup with
"Unsupported avatar name". The look descriptions are our own, and help you cast
the right face for a demo.

Any avatar can be paired with any of the 30 prebuilt HD voices. The suggested
voice is just a sensible default.
"""

AVATARS = {
    # Photoreal
    "Jay":    {"style": "photoreal", "look": "Young man in a sharp grey suit",           "voice": "Puck"},
    "Paul":   {"style": "photoreal", "look": "Distinguished older man, suit and tie",    "voice": "Algenib"},
    "Sam":    {"style": "photoreal", "look": "Bearded academic, glasses, tweed jacket",  "voice": "Sadaltager"},
    "Ingrid": {"style": "photoreal", "look": "Blonde woman in a navy blazer and tie",    "voice": "Kore"},
    "Kira":   {"style": "photoreal", "look": "Curly-haired woman in a denim jacket",     "voice": "Aoede"},
    "Vera":   {"style": "photoreal", "look": "Silver-haired woman, music-note jacket",   "voice": "Gacrux"},
    # Animated (3D-film style)
    "Ben":    {"style": "animated",  "look": "Friendly young guy in a green jacket",     "voice": "Achird"},
    "Kai":    {"style": "animated",  "look": "Laid-back guy, yellow sweater, sunglasses", "voice": "Fenrir"},
    "Leo":    {"style": "animated",  "look": "Old painter with a beret and apron",       "voice": "Algieba"},
    "Carmen": {"style": "animated",  "look": "Warm older woman in a blue blazer",        "voice": "Sulafat"},
    "Piper":  {"style": "animated",  "look": "Barista/artisan in an apron",              "voice": "Leda"},
}

# All 30 prebuilt voices with Google's one-word character description.
VOICES = {
    "Zephyr": "Bright", "Kore": "Firm", "Orus": "Firm", "Autonoe": "Bright",
    "Umbriel": "Easy-going", "Erinome": "Clear", "Laomedeia": "Upbeat",
    "Schedar": "Even", "Achird": "Friendly", "Sadachbia": "Lively",
    "Puck": "Upbeat", "Fenrir": "Excitable", "Aoede": "Breezy",
    "Enceladus": "Breathy", "Algieba": "Smooth", "Algenib": "Gravelly",
    "Achernar": "Soft", "Gacrux": "Mature", "Zubenelgenubi": "Casual",
    "Sadaltager": "Knowledgeable", "Charon": "Informative", "Leda": "Youthful",
    "Callirrhoe": "Easy-going", "Iapetus": "Clear", "Despina": "Smooth",
    "Rasalgethi": "Informative", "Alnilam": "Firm", "Pulcherrima": "Forward",
    "Vindemiatrix": "Gentle", "Sulafat": "Warm",
}
