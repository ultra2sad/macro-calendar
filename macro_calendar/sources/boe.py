"""Bank of England: Monetary Policy Committee announcement dates.

Page layout: a heading per year ("2026 confirmed dates") followed by a table of
rows like ["Thursday 5 February", "February MPC Summary and minutes and February
Monetary Policy Report"]. Announcements are at 12:00 London time.
"""

from __future__ import annotations

import re
from datetime import datetime
from zoneinfo import ZoneInfo

from ..models import Event, Importance
from .base import Source, month_number, soup, text

URL = "https://www.bankofengland.co.uk/monetary-policy/upcoming-mpc-dates"
LONDON = ZoneInfo("Europe/London")
YEAR_RE = re.compile(r"(\d{4}) confirmed dates")
DATE_RE = re.compile(r"(\d{1,2}) ([A-Za-z]+)")  # "Thursday 5 February" -> 5, February


def parse(html: str) -> list[Event]:
    events: list[Event] = []
    page = soup(html)
    for heading in page.find_all(["h2", "h3"]):
        year_match = YEAR_RE.search(text(heading))
        if not year_match:
            continue
        year = int(year_match.group(1))
        table = heading.find_next("table")
        if table is None:
            continue
        for row in table.find_all("tr"):
            cells = [text(td) for td in row.find_all("td")]
            if len(cells) < 2 or not (date := DATE_RE.search(cells[0])):
                continue
            when = datetime(year, month_number(date.group(2)), int(date.group(1)), 12, 0, tzinfo=LONDON)
            with_report = "Monetary Policy Report" in cells[1]
            title = "BoE rate decision" + (" + Monetary Policy Report" if with_report else "")
            events.append(Event(when, "BoE", "UK", title, Importance.HIGH, URL))
    return events


SOURCE = Source("BoE", URL, parse)
