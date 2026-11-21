"""Download -> parse -> export, with a fake network (httpx.MockTransport)."""

from datetime import datetime, timezone
from pathlib import Path

import httpx
from openpyxl import load_workbook

from macro_calendar import collect as collect_module
from macro_calendar.collect import collect, upcoming
from macro_calendar.export_excel import write_excel
from macro_calendar.export_ics import escape, fold, to_ics
from macro_calendar.models import Event, Importance
from macro_calendar.sources import SOURCES

FIXTURES = Path(__file__).parent / "fixtures"
NOW = datetime(2026, 11, 21, 12, 0, tzinfo=timezone.utc)


def fake_site(broken: str | None = None):
    """Serves the saved pages; the `broken` source answers 403."""
    pages = {src.url: (FIXTURES / f"{key}.html").read_text(encoding="utf-8") for key, src in SOURCES.items()}

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if broken and SOURCES[broken].url == url:
            return httpx.Response(403, text="Forbidden")
        return httpx.Response(200, text=pages[url])

    return httpx.MockTransport(handler)


async def test_one_broken_source_does_not_stop_the_others():
    results = await collect(list(SOURCES.values()), transport=fake_site(broken="ecb"))
    by_name = {r.source.name: r for r in results}
    assert not by_name["ECB"].ok and "403" in by_name["ECB"].error
    assert all(by_name[n].ok and by_name[n].events for n in ("Fed", "BoE", "BEA"))


async def test_server_errors_are_retried(monkeypatch):
    calls = 0

    async def no_sleep(_):
        pass

    def flaky(request):
        nonlocal calls
        calls += 1
        return httpx.Response(503) if calls < 3 else httpx.Response(200, text=(FIXTURES / "boe.html").read_text("utf-8"))

    monkeypatch.setattr(collect_module.asyncio, "sleep", no_sleep)
    (result,) = await collect([SOURCES["boe"]], transport=httpx.MockTransport(flaky))
    assert result.ok and calls == 3


async def test_upcoming_is_sorted_future_only_and_within_range():
    results = await collect(list(SOURCES.values()), transport=fake_site())
    events = upcoming(results, days=60, now=NOW)
    assert events and all(NOW <= e.utc <= datetime(2027, 1, 21, tzinfo=timezone.utc) for e in events)
    assert [e.utc for e in events] == sorted(e.utc for e in events)
    assert {e.source for e in events} == {"Fed", "ECB", "BoE", "BEA"}


async def test_excel_has_both_sheets_and_highlights(tmp_path):
    results = await collect(list(SOURCES.values()), transport=fake_site(broken="bea"))
    path = write_excel(upcoming(results, 60, now=NOW), results, tmp_path / "out.xlsx", now=NOW)
    wb = load_workbook(path)
    rows = list(wb["Calendar"].iter_rows(min_row=2, values_only=True))
    fed_row = next(r for r in rows if r[4] == "Fed")
    assert fed_row[1] == "22:00" and fed_row[8] == "14:00 EST"
    assert wb["Calendar"]["A2"].fill.fgColor.rgb.endswith("F8D7DA")  # high importance is highlighted
    status = {r[0]: r[1] for r in wb["Sources"].iter_rows(min_row=2, values_only=True) if r[0] in SOURCES_NAMES}
    assert status["Fed"] == "OK" and "403" in status["BEA"]


SOURCES_NAMES = {s.name for s in SOURCES.values()}


def make_event(title="ECB rate decision", importance=Importance.HIGH) -> Event:
    when = datetime(2026, 12, 17, 13, 15, tzinfo=timezone.utc)
    return Event(when, "ECB", "EU", title, importance, "https://example.org")


def test_ics_format_rules():
    ics = to_ics([make_event(), make_event("Minor, thing", Importance.LOW)], now=NOW)
    assert ics.startswith("BEGIN:VCALENDAR\r\n") and ics.endswith("END:VCALENDAR\r\n")
    assert "DTSTART:20261217T131500Z" in ics and "DTEND:20261217T134500Z" in ics
    assert ics.count("BEGIN:VEVENT") == 1  # LOW is below the default MEDIUM cut-off
    assert all(len(line.encode()) <= 75 for line in ics.split("\r\n"))


def test_ics_escaping_and_folding():
    assert escape("a,b;c\\d\ne") == "a\\,b\\;c\\\\d\\ne"
    long = "SUMMARY:" + "🇺🇸 GDP (Second Estimate) and Corporate Profits, 3rd Quarter 2026 " * 2
    folded = fold(long)
    assert all(len(part.encode()) <= 75 for part in folded.split("\r\n"))
    assert folded.replace("\r\n ", "") == long  # unfolding gives back the original, emoji intact


def test_uid_is_stable():
    assert make_event().uid == "ecb-20261217-ecb-rate-decision@macro-calendar"
