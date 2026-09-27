"""Registry of demos. Add a new demo by writing a Demo subclass and listing it here."""

from .appraiser import Appraiser
from .custom_avatar import CustomAvatar
from .debate import Debate
from .interrogation import Interrogation
from .notetaker import NoteTaker
from .polyglot import Polyglot
from .studio import Studio

DEMOS = {d.id: d for d in (Studio(), Appraiser(), Interrogation(), Polyglot(), NoteTaker(), Debate(), CustomAvatar())}
