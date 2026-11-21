"""Parsers against real pages saved on 2026-11-21 (tests/fixtures), so no network is needed."""

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from macro_calendar.models import Importance
from macro_calendar.sources import SOURCES, bea, boe, ecb, fed

FIXTURES = Path(__file__).parent / "fixtures"
MSK = ZoneInfo("Europe/Moscow")


def page(name: str) -> str:
    return (FIXTURES / f"{name}.html").read_text(encoding="utf-8")


def msk(event) -> str:
    return event.when.astimezone(MSK).strftime("%Y-%m-%d %H:%M")


@pytest.mark.parametrize(("name", "minimum"), [("fed", 40), ("ecb", 10), ("boe", 10), ("bea", 5)])
def test_every_source_finds_events(name, minimum):
    events = SOURCES[name].parse(page(name))
    assert len(events) >= minimum
    assert all(e.when.tzinfo is not None for e in events)


def test_fed_decision_is_on_the_last_day_at_2pm_new_york():
    events = {e.when.date().isoformat(): e for e in fed.parse(page("fed"))}
    dec = events["2026-12-09"]  # meeting "December 8-9*"
    assert dec.title == "FOMC rate decision + economic projections"
    assert msk(dec) == "2026-12-09 22:00"  # 14:00 EST
    # Daylight saving: in June New York is UTC-4, so the same 14:00 is 21:00 in Moscow.
    assert msk(events["2026-06-17"]) == "2026-06-17 21:00"
    assert events["2026-01-28"].title == "FOMC rate decision"  # no asterisk, no projections


def test_fed_odd_rows():
    html = """<div class="panel"><div class="panel-heading">2025 FOMC Meetings</div>
      <div class="row fomc-meeting"><div class="fomc-meeting__month">Apr/May</div><div class="fomc-meeting__date">30-1</div></div>
      <div class="row fomc-meeting"><div class="fomc-meeting__month">August</div><div class="fomc-meeting__date">22 (notation vote)</div></div>
    </div>"""
    events = fed.parse(html)
    assert [e.when.date().isoformat() for e in events] == ["2025-05-01"]  # spans months; notation vote skipped


def test_ecb_takes_day_two_with_press_conference():
    events = ecb.parse(page("ecb"))
    days = [e.when.date().isoformat() for e in events]
    assert "2026-12-17" in days and "2026-12-16" not in days  # day 1 is not the decision
    assert "2026-11-25" not in days  # a non-monetary policy meeting
    assert msk(events[0]) == "2026-12-17 16:15"


def test_boe_dates_years_and_reports():
    events = {e.when.date().isoformat(): e for e in boe.parse(page("boe"))}
    assert events["2026-12-17"].title == "BoE rate decision"
    assert events["2027-02-04"].title == "BoE rate decision + Monetary Policy Report"  # "Thursday\xa04 February"
    assert msk(events["2026-12-17"]) == "2026-12-17 15:00"


def test_bea_times_and_importance():
    events = bea.parse(page("bea"))
    gdp = next(e for e in events if e.title.startswith("GDP (Second Estimate)"))
    assert msk(gdp) == "2026-11-25 16:30" and gdp.importance is Importance.HIGH
    county = next(e for e in events if e.title.startswith("GDP by County"))
    assert county.importance is Importance.LOW  # "GDP" alone must not make it important
    trade = next(e for e in events if "International Trade" in e.title)
    assert trade.importance is Importance.MEDIUM


def test_bea_reads_pm_times_and_year_rows():
    html = """<table><tr><td>Year 2027</td></tr>
      <tr><td><div class="release-date">January 29</div><small>2:00 PM</small></td>
          <td class="release-title">Personal Income and Outlays, December 2026</td></tr></table>"""
    (e,) = bea.parse(html)
    assert e.when == datetime(2027, 1, 29, 14, 0, tzinfo=ZoneInfo("America/New_York"))


def test_changed_layout_gives_no_events_not_garbage():
    assert all(src.parse("<html><body><p>We moved!</p></body></html>") == [] for src in SOURCES.values())
