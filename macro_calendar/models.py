"""The one shape every source is normalised into."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum


class Importance(str, Enum):
    HIGH = "high"  # rate decisions, GDP, PCE inflation: markets move
    MEDIUM = "medium"
    LOW = "low"

    @property
    def rank(self) -> int:
        return {"high": 3, "medium": 2, "low": 1}[self.value]


@dataclass(frozen=True, slots=True)
class Event:
    """One scheduled market-moving event.

    `when` is timezone-aware in the publisher's own zone (14:00 New York for the Fed,
    14:15 Frankfurt for the ECB). Converting to the reader's zone happens only at export,
    so the data stays correct whoever reads it and wherever daylight saving shifts.
    """

    when: datetime
    source: str  # "Fed", "ECB", "BoE", "BEA"
    country: str  # "US", "EU", "UK"
    title: str
    importance: Importance
    url: str
    note: str = ""

    def __post_init__(self) -> None:
        if self.when.tzinfo is None:
            raise ValueError(f"{self.source}: event time must carry a timezone: {self.when!r}")

    @property
    def utc(self) -> datetime:
        return self.when.astimezone(timezone.utc)

    @property
    def uid(self) -> str:
        """Stable id: re-importing the .ics updates events instead of duplicating them."""
        slug = re.sub(r"[^a-z0-9]+", "-", self.title.lower()).strip("-")[:40]
        return f"{self.source.lower()}-{self.when:%Y%m%d}-{slug}@macro-calendar"
