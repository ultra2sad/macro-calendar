"""Download every source in parallel and turn the pages into one sorted event list."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import httpx

from .models import Event
from .sources import Source

log = logging.getLogger(__name__)

# An honest User-Agent: says what the client is and where to read about it.
USER_AGENT = "macro-calendar/0.1 (+https://github.com/ultra2sad/macro-calendar)"
RETRIES = 3


@dataclass(slots=True)
class SourceResult:
    source: Source
    events: list[Event] = field(default_factory=list)
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None


async def fetch(client: httpx.AsyncClient, url: str) -> str:
    """GET with retries. 5xx and network errors are retried with a growing pause; 4xx are not."""
    for attempt in range(1, RETRIES + 1):
        try:
            response = await client.get(url)
            if response.status_code < 500:
                response.raise_for_status()  # 403/404: retrying won't help
                return response.text
            error: Exception = httpx.HTTPStatusError(
                f"server error {response.status_code}", request=response.request, response=response)
        except httpx.TransportError as err:  # timeouts, refused connections, DNS
            error = err
        if attempt < RETRIES:
            await asyncio.sleep(2 ** attempt)
    raise error


async def collect_one(client: httpx.AsyncClient, source: Source) -> SourceResult:
    # One broken site must not cost the other five: every failure stays inside its result.
    try:
        html = await fetch(client, source.url)
    except httpx.HTTPError as err:
        log.warning("%s: download failed: %s", source.name, err)
        return SourceResult(source, error=f"download failed: {err}")
    try:
        events = source.parse(html)
    except Exception as err:  # a redesign broke the parser
        log.exception("%s: parsing failed", source.name)
        return SourceResult(source, error=f"parsing failed: {err}")
    if not events:
        # A parser that finds nothing usually means the page layout changed: say so loudly.
        log.warning("%s: page downloaded but no events found (layout changed?)", source.name)
        return SourceResult(source, error="no events found on the page (layout changed?)")
    return SourceResult(source, events)


async def collect(sources: list[Source], transport: httpx.AsyncBaseTransport | None = None) -> list[SourceResult]:
    async with httpx.AsyncClient(
        headers={"User-Agent": USER_AGENT}, timeout=30, follow_redirects=True, transport=transport
    ) as client:
        return list(await asyncio.gather(*(collect_one(client, s) for s in sources)))


def upcoming(results: list[SourceResult], days: int, now: datetime | None = None) -> list[Event]:
    """Events from now on, within `days`, without duplicates, soonest first."""
    now = now or datetime.now(timezone.utc)
    until = now + timedelta(days=days)
    unique = {e.uid: e for r in results for e in r.events if now - timedelta(hours=3) <= e.utc <= until}
    return sorted(unique.values(), key=lambda e: (e.utc, e.source))
