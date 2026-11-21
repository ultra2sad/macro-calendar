"""What a source is, plus parsing helpers several sources share."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from bs4 import BeautifulSoup

from ..models import Event

MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july",
     "august", "september", "october", "november", "december"], start=1)}


@dataclass(frozen=True, slots=True)
class Source:
    name: str
    url: str
    parse: Callable[[str], list[Event]]  # page HTML -> events; pure, so it's tested on saved pages


def soup(html: str) -> BeautifulSoup:
    # lxml: fast and forgiving with the messy HTML real sites serve.
    return BeautifulSoup(html, "lxml")


def month_number(name: str) -> int:
    """'March' / 'mar' / 'Mar.' -> 3."""
    key = name.strip().strip(".").lower()
    for full, number in MONTHS.items():
        if full.startswith(key[:3]):
            return number
    raise ValueError(f"unknown month: {name!r}")


def text(node) -> str:
    # \xa0 (non-breaking space) shows up in dates like "Thursday\xa04 February".
    return " ".join(node.get_text(" ", strip=True).replace("\xa0", " ").split())
