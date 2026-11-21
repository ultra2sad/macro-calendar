"""All sources. Adding a central bank = one module with URL + parse(), then list it here."""

from . import bea, boe, ecb, fed
from .base import Source

SOURCES: dict[str, Source] = {s.name.lower(): s for s in (fed.SOURCE, ecb.SOURCE, boe.SOURCE, bea.SOURCE)}

__all__ = ["SOURCES", "Source"]
