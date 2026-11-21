"""US Bureau of Economic Analysis: release schedule (GDP, PCE inflation, trade).

Page layout: one table; a "Year 2026" row starts each year, then rows with a date cell
("November 25" + "8:30 AM") and a release title. Times are New York time.
"""

from __future__ import annotations

import re
from datetime import datetime
from zoneinfo import ZoneInfo

from ..models import Event, Importance
from .base import Source, month_number, soup, text

URL = "https://www.bea.gov/news/schedule"
NEW_YORK = ZoneInfo("America/New_York")
YEAR_RE = re.compile(r"Year (\d{4})")
DATE_RE = re.compile(r"([A-Za-z]+) (\d{1,2})")
TIME_RE = re.compile(r"(\d{1,2}):(\d{2}) ?([AP]M)", re.I)

# What moves markets. "Personal Income and Outlays" carries PCE, the Fed's preferred inflation gauge.
HIGH = ("GDP (Advance", "GDP (Second", "GDP (Third", "Personal Income and Outlays")
MEDIUM = ("International Trade in Goods and Services",)


def importance(title: str) -> Importance:
    if any(key in title for key in HIGH):
        return Importance.HIGH
    if any(key in title for key in MEDIUM):
        return Importance.MEDIUM
    return Importance.LOW


def parse(html: str) -> list[Event]:
    events: list[Event] = []
    year: int | None = None
    for row in soup(html).select("table tr"):
        if year_match := YEAR_RE.search(text(row)):
            year = int(year_match.group(1))
            continue
        date_el, title_el = row.select_one(".release-date"), row.select_one("td.release-title")
        if year is None or date_el is None or title_el is None:
            continue
        date = DATE_RE.search(text(date_el))
        if not date:
            continue
        hour, minute = 8, 30  # BEA's standard release time, if the cell has none
        time_el = row.select_one("small")
        if time_el and (t := TIME_RE.search(text(time_el))):
            hour, minute = int(t.group(1)) % 12 + (12 if t.group(3).upper() == "PM" else 0), int(t.group(2))
        when = datetime(year, month_number(date.group(1)), int(date.group(2)), hour, minute, tzinfo=NEW_YORK)
        title = text(title_el)
        events.append(Event(when, "BEA", "US", title, importance(title), URL))
    return events


SOURCE = Source("BEA", URL, parse)
