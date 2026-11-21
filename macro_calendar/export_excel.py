"""Excel export: a formatted table someone can open and use straight away."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from .collect import SourceResult
from .models import Event, Importance

FILLS = {
    Importance.HIGH: PatternFill("solid", fgColor="F8D7DA"),  # soft red
    Importance.MEDIUM: PatternFill("solid", fgColor="FFF3CD"),  # soft yellow
}
HEADER_FILL = PatternFill("solid", fgColor="1F3864")
HEADER_FONT = Font(bold=True, color="FFFFFF")


def _header(ws, titles: list[str], widths: list[int]) -> None:
    ws.append(titles)
    for col, width in enumerate(widths, start=1):
        cell = ws.cell(row=1, column=col)
        cell.fill, cell.font = HEADER_FILL, HEADER_FONT
        cell.alignment = Alignment(vertical="center")
        ws.column_dimensions[get_column_letter(col)].width = width
    ws.freeze_panes = "A2"  # header stays visible while scrolling


def write_excel(
    events: list[Event],
    results: list[SourceResult],
    path: Path,
    tz: str = "Europe/Moscow",
    now: datetime | None = None,
) -> Path:
    now = now or datetime.now(timezone.utc)
    zone = ZoneInfo(tz)
    wb = Workbook()

    ws = wb.active
    ws.title = "Calendar"
    _header(ws, [f"Date ({tz})", "Time", "Weekday", "In days", "Source", "Country", "Event", "Importance",
                 "Local time at source", "Link"],
            # Width = longest value + room for the filter arrow, which covers the header's end.
            [24, 9, 13, 10, 10, 11, 72, 14, 22, 9])
    for e in events:
        local = e.when.astimezone(zone)
        ws.append([
            local.date(),  # a real date cell, so Excel sorts and filters it as a date
            local.strftime("%H:%M"),
            local.strftime("%A"),
            (local.date() - now.astimezone(zone).date()).days,
            e.source,
            e.country,
            e.title,
            e.importance.value,
            e.when.strftime("%H:%M %Z"),  # "14:00 EST" - what the publisher announces
            "open",
        ])
        row = ws.max_row
        ws.cell(row=row, column=1).number_format = "DD.MM.YYYY"
        link = ws.cell(row=row, column=10)
        link.hyperlink, link.font = e.url, Font(color="0563C1", underline="single")
        if fill := FILLS.get(e.importance):
            for col in range(1, 10):
                ws.cell(row=row, column=col).fill = fill
    ws.auto_filter.ref = ws.dimensions  # filter arrows on every column

    # Second sheet: what was checked and whether it worked - a broken source is visible, not silent.
    status = wb.create_sheet("Sources")
    _header(status, ["Source", "Status", "Events found", "Page"], [10, 52, 13, 70])
    for r in results:
        status.append([r.source.name, "OK" if r.ok else r.error, len(r.events), r.source.url])
        if not r.ok:
            status.cell(row=status.max_row, column=2).font = Font(color="C00000", bold=True)
    status.append([])
    status.append([f"Updated {now.astimezone(zone):%d.%m.%Y %H:%M} ({tz})"])

    wb.save(path)
    return path
