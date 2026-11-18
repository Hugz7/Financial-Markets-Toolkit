"""Tests for the flashcard deck file and loader."""

import json

import pytest

from services.flashcards import DATA_PATH, parse_decks

PAGE_SLUGS = {"markets", "payoff", "exotics", "vol-smile", "yield-curve", "swaps",
              "forwards", "monte-carlo", "roadmap", "interview"}


@pytest.fixture(scope="module")
def decks():
    return parse_decks(json.loads(DATA_PATH.read_text(encoding="utf-8")))


def test_deck_sizes(decks):
    sizes = {d.id: len(d.cards) for d in decks}
    assert sizes == {"markets": 20, "behavioral": 70}


def test_every_card_complete(decks):
    for d in decks:
        for c in d.cards:
            assert len(c.q) > 10 and len(c.a) > 40, c.id
            assert "DM or email" not in c.a  # promotional footer stripped from the source PDF


def test_links_point_to_real_pages(decks):
    for d in decks:
        for c in d.cards:
            assert c.link is None or c.link in PAGE_SLUGS, (c.id, c.link)


def test_duplicate_ids_rejected():
    raw = {"decks": [{"id": "x", "title": "X", "cards": [
        {"id": "a", "q": "Question one?", "a": "Answer one."},
        {"id": "a", "q": "Question two?", "a": "Answer two."},
    ]}]}
    with pytest.raises(ValueError):
        parse_decks(raw)
