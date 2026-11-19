"""services/flashcards.py — Interview flashcard decks (data/flashcards.json)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import streamlit as st

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "flashcards.json"
PROGRESS_PATH = DATA_PATH.with_name("user_progress.json")   # local, git-ignored
LEVELS = ("easy", "medium", "hard")


@dataclass(frozen=True)
class Card:
    id: str
    deck: str
    q: str
    a: str
    topic: str = ""
    points: tuple[str, ...] = ()
    link: str | None = None   # url_path of a toolkit page that demonstrates the concept
    difficulty: str = "medium"  # default level from the deck file; users can override it


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
            level = c.get("difficulty", "medium")
            if level not in LEVELS:
                raise ValueError(f"card {c['id']!r} has unknown difficulty {level!r}")
            seen.add(c["id"])
            cards.append(Card(id=c["id"], deck=d["id"], q=c["q"].strip(), a=c["a"].strip(),
                              topic=c.get("topic", ""), points=tuple(c.get("points", ())),
                              link=c.get("link"), difficulty=level))
        decks.append(Deck(id=d["id"], title=d["title"], short=d.get("short", d["title"]),
                          source=d.get("source", ""), cards=tuple(cards)))
    if not decks:
        raise ValueError("no decks found")
    return decks


@st.cache_data(show_spinner=False)
def load_decks() -> list[Deck]:
    return parse_decks(json.loads(DATA_PATH.read_text(encoding="utf-8")))


# ── Personal progress: scores and difficulty overrides, saved locally ─────────

def empty_progress() -> dict:
    return {"known": set(), "review": set(), "difficulty": {}}


def load_progress(path: Path = PROGRESS_PATH) -> dict:
    """Read saved progress; a missing or corrupt file gives an empty one."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return empty_progress()
    return {"known": set(raw.get("known", [])), "review": set(raw.get("review", [])),
            "difficulty": {k: v for k, v in raw.get("difficulty", {}).items() if v in LEVELS}}


def save_progress(progress: dict, path: Path = PROGRESS_PATH) -> bool:
    """Write progress atomically; returns False if the disk is read-only (e.g. hosted)."""
    data = {"known": sorted(progress["known"]), "review": sorted(progress["review"]),
            "difficulty": dict(sorted(progress["difficulty"].items()))}
    try:
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=1), encoding="utf-8")
        tmp.replace(path)
        return True
    except OSError:
        return False
