"""services/flashcards.py — Interview flashcard decks (data/flashcards.json)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import streamlit as st

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "flashcards.json"


@dataclass(frozen=True)
class Card:
    id: str
    deck: str
    q: str
    a: str
    topic: str = ""
    points: tuple[str, ...] = ()
    link: str | None = None   # url_path of a toolkit page that demonstrates the concept


@dataclass(frozen=True)
class Deck:
    id: str
    title: str
    short: str
    source: str
    cards: tuple[Card, ...] = field(default_factory=tuple)


def parse_decks(raw: dict) -> list[Deck]:
    """Validate and convert the JSON structure. Raises ValueError on bad data."""
    decks, seen = [], set()
    for d in raw.get("decks", []):
        cards = []
        for c in d["cards"]:
            if c["id"] in seen:
                raise ValueError(f"duplicate card id {c['id']!r}")
            if not c.get("q", "").strip() or not c.get("a", "").strip():
                raise ValueError(f"card {c['id']!r} needs a question and an answer")
            seen.add(c["id"])
            cards.append(Card(id=c["id"], deck=d["id"], q=c["q"].strip(), a=c["a"].strip(),
                              topic=c.get("topic", ""), points=tuple(c.get("points", ())),
                              link=c.get("link")))
        decks.append(Deck(id=d["id"], title=d["title"], short=d.get("short", d["title"]),
                          source=d.get("source", ""), cards=tuple(cards)))
    if not decks:
        raise ValueError("no decks found")
    return decks


@st.cache_data(show_spinner=False)
def load_decks() -> list[Deck]:
    return parse_decks(json.loads(DATA_PATH.read_text(encoding="utf-8")))
