"""US Federal Reserve: FOMC meeting calendar.

Page layout: one panel per year ("2026 FOMC Meetings"), one row per meeting with a
month ("March", or "Apr/May" when it spans two) and days ("17-18*", "30-1").
The decision is published at 2:00 pm New York time on the meeting's last day.
"""

from __future__ import annotations

import re
from datetime import datetime
from zoneinfo import ZoneInfo

from ..models import Event, Importance
from .base import Source, month_number, soup, text

URL = "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"
NEW_YORK = ZoneInfo("America/New_York")
DAYS_RE = re.compile(r"^(\d{1,2})(?:-(\d{1,2}))?(\*)?$")  # "17-18*", "30-1", "22"
YEAR_RE = re.compile(r"(\d{4}) FOMC Meetings")


def parse(html: str) -> list[Event]:
    events: list[Event] = []
    for panel in soup(html).select("div.panel"):
        heading = panel.select_one(".panel-heading")
        year_match = YEAR_RE.search(text(heading)) if heading else None
        if not year_match:
            continue
        year = int(year_match.group(1))
        for row in panel.select(".fomc-meeting"):
            month_el, days_el = row.select_one(".fomc-meeting__month"), row.select_one(".fomc-meeting__date")
            if month_el is None or days_el is None:
                continue
            days = DAYS_RE.match(text(days_el))
            if days is None:
                continue  # "22 (notation vote)", "(unscheduled)": not a scheduled decision
            first, last, projections = days.group(1), days.group(2), days.group(3)
            # "Apr/May" + "30-1": the decision falls in the second month.
            month = month_number(text(month_el).split("/")[-1])
            day = int(last or first)
            # A December meeting never spills into January, so the panel's year is right.
            when = datetime(year, month, day, 14, 0, tzinfo=NEW_YORK)
            title = "FOMC rate decision" + (" + economic projections" if projections else "")
            events.append(Event(when, "Fed", "US", title, Importance.HIGH, URL,
                                note="Press conference at 2:30 pm ET"))
    return events


SOURCE = Source("Fed", URL, parse)
