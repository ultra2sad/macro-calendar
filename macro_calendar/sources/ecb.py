"""European Central Bank: Governing Council meeting calendar.

Page layout: one <dl> of <dt>date</dt><dd>description</dd> pairs, dates as dd/mm/yyyy.
Monetary policy meetings run two days; the decision comes on day 2, the entry that
mentions the press conference. Decision at 14:15 Frankfurt time.
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from ..models import Event, Importance
from .base import Source, soup, text

URL = "https://www.ecb.europa.eu/press/calendars/mgcgc/html/index.en.html"
FRANKFURT = ZoneInfo("Europe/Berlin")


def is_decision(description: str) -> bool:
    d = description.lower()
    return "monetary policy meeting" in d and "non-monetary" not in d and "press conference" in d


def parse(html: str) -> list[Event]:
    events: list[Event] = []
    for dt in soup(html).select("dl > dt"):
        dd = dt.find_next_sibling("dd")
        if dd is None or not is_decision(text(dd)):
            continue
        try:
            day = datetime.strptime(text(dt), "%d/%m/%Y")
        except ValueError:
            continue
        when = day.replace(hour=14, minute=15, tzinfo=FRANKFURT)
        events.append(Event(when, "ECB", "EU", "ECB rate decision", Importance.HIGH, URL,
                            note="Press conference at 14:45 CET"))
    return events


SOURCE = Source("ECB", URL, parse)
