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
    assert sizes == {"markets": 100, "behavioral": 70}


def test_every_level_represented(decks):
    for d in decks:
        assert {c.difficulty for c in d.cards} == {"easy", "medium", "hard"}, d.id


def test_no_duplicate_questions(decks):
    qs = [c.q.lower() for d in decks for c in d.cards]
    assert len(qs) == len(set(qs))


def test_progress_round_trip(tmp_path):
    from services.flashcards import load_progress, save_progress
    path = tmp_path / "progress.json"
    assert load_progress(path)["known"] == set()          # missing file → empty
    prog = {"known": {"mkt-001"}, "review": {"beh-04"}, "difficulty": {"mkt-002": "hard", "x": "bogus"}}
    assert save_progress(prog, path)
    back = load_progress(path)
    assert back["known"] == {"mkt-001"} and back["review"] == {"beh-04"}
    assert back["difficulty"] == {"mkt-002": "hard"}       # invalid levels dropped


def test_unknown_difficulty_rejected():
    raw = {"decks": [{"id": "x", "title": "X", "cards": [
        {"id": "a", "q": "Question one?", "a": "Answer one.", "difficulty": "brutal"}]}]}
    with pytest.raises(ValueError):
        parse_decks(raw)


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
