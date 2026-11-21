"""iCalendar (.ics) export: import into Google Calendar, Outlook or Apple Calendar.

Written by hand instead of with a library: the format is plain text (RFC 5545) and the
three rules that trip people up are all here - CRLF line ends, escaping, and folding
lines longer than 75 bytes.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from .models import Event, Importance

DURATION = timedelta(minutes=30)
ICON = {"Fed": "🇺🇸", "BEA": "🇺🇸", "ECB": "🇪🇺", "BoE": "🇬🇧"}


def escape(value: str) -> str:
    # Backslash first, or the backslashes added for the others would get doubled.
    return value.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def fold(line: str) -> str:
    """Split lines over 75 bytes; continuation lines start with a space. Never cut a UTF-8 character."""
    out, current = [], ""
    for ch in line:
        limit = 75 if not out else 74  # continuation lines lose one byte to the leading space
        if len((current + ch).encode("utf-8")) > limit:
            out.append(current)
            current = ch
        else:
            current += ch
    out.append(current)
    return "\r\n ".join(out)


def stamp(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")  # UTC: every calendar app agrees on it


def to_ics(events: list[Event], min_importance: Importance = Importance.MEDIUM, now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//macro-calendar//EN",
        "CALSCALE:GREGORIAN",
        "X-WR-CALNAME:Macro calendar",
    ]
    for e in events:
        if e.importance.rank < min_importance.rank:
            continue
        description = "\n".join(filter(None, [e.note, f"Importance: {e.importance.value}", f"Source: {e.url}"]))
        lines += [
            "BEGIN:VEVENT",
            f"UID:{e.uid}",
            f"DTSTAMP:{stamp(now)}",
            f"DTSTART:{stamp(e.when)}",
            f"DTEND:{stamp(e.when + DURATION)}",
            f"SUMMARY:{escape(ICON.get(e.source, '') + ' ' + e.title).strip()}",
            f"DESCRIPTION:{escape(description)}",
            f"URL:{e.url}",
            "END:VEVENT",
        ]
    lines.append("END:VCALENDAR")
    return "\r\n".join(fold(line) for line in lines) + "\r\n"


def write_ics(events: list[Event], path: Path, min_importance: Importance = Importance.MEDIUM) -> Path:
    # newline="": keep our \r\n as is (Windows would otherwise turn \n into \r\n again).
    path.write_text(to_ics(events, min_importance), encoding="utf-8", newline="")
    return path
