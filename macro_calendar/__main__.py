"""Command line: python -m macro_calendar [--days 365] [--out output] [--tz Europe/Moscow]."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .collect import collect, upcoming
from .export_excel import write_excel
from .export_ics import write_ics
from .models import Importance
from .sources import SOURCES


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="macro_calendar", description="Scrape central bank and macro release dates.")
    p.add_argument("--days", type=int, default=365, help="how far ahead to look (default 365)")
    p.add_argument("--out", type=Path, default=Path("output"), help="folder for the .xlsx and .ics files")
    p.add_argument("--tz", default="Europe/Moscow", help="time zone for the Excel table (default Europe/Moscow)")
    p.add_argument("--sources", default=",".join(SOURCES), help=f"comma list, default: {','.join(SOURCES)}")
    p.add_argument("--ics-min", choices=[i.value for i in Importance], default="medium",
                   help="lowest importance that goes into the .ics (default medium)")
    args = p.parse_args(argv)
    try:
        ZoneInfo(args.tz)
    except (ZoneInfoNotFoundError, ValueError):
        p.error(f"unknown time zone: {args.tz} (examples: Europe/Moscow, UTC, America/New_York)")
    unknown = [s for s in args.sources.split(",") if s.strip().lower() not in SOURCES]
    if unknown:
        p.error(f"unknown source(s): {', '.join(unknown)}; available: {', '.join(SOURCES)}")
    return args


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)  # one line per request is noise here
    args = parse_args(argv)
    sources = [SOURCES[s.strip().lower()] for s in args.sources.split(",")]

    results = asyncio.run(collect(sources))
    events = upcoming(results, args.days)
    for r in results:
        logging.info("%-4s %s", r.source.name, f"{len(r.events)} events" if r.ok else f"FAILED: {r.error}")

    args.out.mkdir(parents=True, exist_ok=True)
    xlsx = write_excel(events, results, args.out / "macro_calendar.xlsx", tz=args.tz)
    ics = write_ics(events, args.out / "macro_calendar.ics", Importance(args.ics_min))
    logging.info("%d upcoming events in the next %d days -> %s, %s", len(events), args.days, xlsx, ics)
    # Exit code 1 if any source failed: a scheduler (cron, Task Scheduler) can alert on it.
    return 0 if all(r.ok for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
