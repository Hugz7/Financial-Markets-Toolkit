"""views/interview_prep.py — Interview flashcards: flip, self-score, rate difficulty,
review what you missed. Scores and difficulty ratings are saved locally."""

from __future__ import annotations

import random

import streamlit as st

from services.flashcards import LEVELS, Card, load_decks, load_progress, save_progress
from ui.components import (Stat, empty_state, flashcard, page_header, panel, section,
                           stat_grid)

ALL = "all"
_S = "ip_progress"   # {"known": set, "review": set, "difficulty": {card_id: level}}
LEVEL_LABEL = {"easy": "Easy", "medium": "Medium", "hard": "Hard"}
LEVEL_BADGE = {"easy": ":green-badge[Easy]", "medium": ":orange-badge[Medium]", "hard": ":red-badge[Hard]"}


def _progress() -> dict:
    if _S not in st.session_state:
        st.session_state[_S] = load_progress()
    return st.session_state[_S]


def _persist() -> None:
    st.session_state["ip_saved"] = save_progress(_progress())


def _level(card: Card) -> str:
    return _progress()["difficulty"].get(card.id, card.difficulty)


def _status(card_id: str) -> str | None:
    p = _progress()
    return "known" if card_id in p["known"] else "review" if card_id in p["review"] else None


def _mark(card_id: str, verdict: str, n: int) -> None:
    p = _progress()
    other = "review" if verdict == "known" else "known"
    p[verdict].add(card_id)
    p[other].discard(card_id)
    _persist()
    _step(+1, n)


def _rate(card: Card) -> None:
    """Store the user's difficulty rating (only overrides that differ from the default)."""
    level = st.session_state.get(f"ip_lvl_{card.id}")
    if level not in LEVELS:
        return
    diffs = _progress()["difficulty"]
    if level == card.difficulty:
        diffs.pop(card.id, None)
    else:
        diffs[card.id] = level
    _persist()


def _step(delta: int, n: int) -> None:
    pos = st.session_state.get("ip_pos", 0) + delta
    if pos >= n:
        st.session_state["ip_done"] = True
        pos = n - 1
    st.session_state["ip_pos"] = max(0, pos)


def _restart(review_only: bool = False) -> None:
    st.session_state["ip_pos"] = 0
    st.session_state["ip_done"] = False
    st.session_state["ip_review_only"] = review_only
    st.session_state["ip_seed"] = st.session_state.get("ip_seed", 0) + 1


def _reset_scores() -> None:
    p = _progress()
    p["known"].clear()
    p["review"].clear()
    _persist()
    _restart()


def render():
    decks = load_decks()
    by_id = {d.id: d for d in decks}
    total_cards = sum(len(d.cards) for d in decks)

    page_header(
        "Interview Prep",
        f"{total_cards} flashcards for markets interviews: {len(decks[0].cards)} technical questions with "
        f"model answers and {total_cards - len(decks[0].cards)} behavioural ones. Flip, score yourself, "
        "rate each card's difficulty, then revisit what you missed.",
        eyebrow="Practice",
    )

    # ── Controls ──
    with panel():
        c1, c2, c3 = st.columns([2.2, 2, 1.6], vertical_alignment="bottom")
        options = [d.id for d in decks] + [ALL]
        labels = {**{d.id: f"{d.short} · {len(d.cards)}" for d in decks}, ALL: f"All · {total_cards}"}
        deck_id = c1.segmented_control("Deck", options, format_func=labels.get,
                                       default=decks[0].id, key="ip_deck") or decks[0].id
        levels = c2.pills("Difficulty", LEVELS, selection_mode="multi", default=list(LEVELS),
                          format_func=LEVEL_LABEL.get, key="ip_levels") or list(LEVELS)
        cards_in_deck: list[Card] = ([c for d in decks for c in d.cards] if deck_id == ALL
                                     else list(by_id[deck_id].cards))
        topics = sorted({c.topic for c in cards_in_deck if c.topic and c.topic != "Behavioral"})
        topic = c3.selectbox("Topic", ["All topics"] + topics, key="ip_topic",
                             disabled=not topics)
        d1, d2, d3, _ = st.columns([1, 1.3, 1.2, 1.5], vertical_alignment="center")
        shuffle = d1.toggle("Shuffle", key="ip_shuffle")
        review_only = d2.toggle("Only cards to review", key="ip_review_only")
        d3.button("Reset scores", icon=":material/restart_alt:", width="stretch",
                  on_click=_reset_scores)

    prog = _progress()
    cards = [c for c in cards_in_deck
             if _level(c) in levels and (topic == "All topics" or c.topic == topic)]
    pool = [c for c in cards if c.id in prog["review"]] if review_only else cards

    # Rebuild the study order only when the selection changes, not on every score or rating.
    seed = st.session_state.get("ip_seed", 0)
    sig = (deck_id, tuple(sorted(levels)), topic, shuffle, review_only, seed)
    if st.session_state.get("ip_sig") != sig:
        order = [c.id for c in pool]
        if shuffle:
            random.Random(seed).shuffle(order)
        st.session_state.update(ip_sig=sig, ip_order=order, ip_pos=0, ip_done=False)
    lookup = {c.id: c for c in cards_in_deck}
    order = [i for i in st.session_state["ip_order"] if i in lookup]

    known = sum(c.id in prog["known"] for c in cards)
    review = sum(c.id in prog["review"] for c in cards)
    split = {lv: sum(_level(c) == lv for c in cards) for lv in LEVELS}
    stat_grid([
        Stat("Cards selected", str(len(cards)), hint=f"of {len(cards_in_deck)} in deck"),
        Stat("Known", str(known), tone="pos" if known else "default"),
        Stat("To review", str(review), tone="warn" if review else "default"),
        Stat("Easy · Medium · Hard", f"{split['easy']} · {split['medium']} · {split['hard']}"),
    ], columns=4)

    tab_study, tab_browse = st.tabs(["Study", "Browse all"])

    # ── Study ──
    with tab_study:
        if not order:
            empty_state("No cards match",
                        "Nothing in this selection — widen the difficulty or topic filter, "
                        "or turn off “Only cards to review”.")
        elif st.session_state.get("ip_done"):
            empty_state("Selection complete",
                        f"{known} known · {review} to review. Go again, or focus on the ones you missed.")
            a, b, _ = st.columns([1, 1, 2])
            a.button("Study again", icon=":material/replay:", width="stretch",
                     on_click=_restart, kwargs={"review_only": False})
            b.button(f"Review missed ({review})", icon=":material/flag:", type="primary",
                     width="stretch", disabled=review == 0,
                     on_click=_restart, kwargs={"review_only": True})
        else:
            n = len(order)
            pos = min(st.session_state.get("ip_pos", 0), n - 1)
            card = lookup[order[pos]]
            level = _level(card)
            st.progress((pos + 1) / n, text=f"Card {pos + 1} of {n}")
            eyebrow = by_id[card.deck].short + (f" · {card.topic}" if card.topic and card.topic != "Behavioral" else "")
            flashcard(card.id, card.q, card.a, eyebrow=eyebrow, counter=f"{pos + 1} / {n}",
                      points=card.points, status=_status(card.id), level=level)

            b1, b2, b3, b4 = st.columns(4)
            b1.button("Previous", icon=":material/arrow_back:", width="stretch",
                      disabled=pos == 0, on_click=_step, args=(-1, n))
            b2.button("Didn't know", icon=":material/flag:", width="stretch",
                      on_click=_mark, args=(card.id, "review", n))
            b3.button("Knew it", icon=":material/check:", type="primary", width="stretch",
                      on_click=_mark, args=(card.id, "known", n))
            b4.button("Skip", icon=":material/arrow_forward:", width="stretch",
                      on_click=_step, args=(+1, n))

            r1, r2 = st.columns([1.4, 3], vertical_alignment="center")
            r1.markdown("**How hard was this one?**")
            st.session_state[f"ip_lvl_{card.id}"] = level
            r2.segmented_control("Rate difficulty", LEVELS, format_func=LEVEL_LABEL.get,
                                 key=f"ip_lvl_{card.id}", on_change=_rate, args=(card,),
                                 label_visibility="collapsed")

            if card.link:
                import navigation  # deferred: navigation imports this module
                target = navigation.page(card.link)
                if target is not None:
                    st.page_link(target, label=f"See it in the toolkit — {navigation.title(card.link)}",
                                 icon=":material/north_east:")
            saved = st.session_state.get("ip_saved")
            note = "" if saved is None else (" · Progress saved on this computer" if saved
                                             else " · Progress kept for this session only")
            st.caption(f"Source: {by_id[card.deck].source}{note}")

    # ── Browse ──
    with tab_browse:
        query = st.text_input("Search questions and answers", key="ip_query",
                              placeholder="e.g. Black-Scholes, convexity, weakness…",
                              label_visibility="collapsed").strip().lower()
        hits = [c for c in cards if not query or query in c.q.lower() or query in c.a.lower()]
        section(f"{len(hits)} questions", "Filtered by deck, difficulty and topic above")
        icons = {"known": ":material/check_circle:", "review": ":material/flag:"}
        for c in hits:
            with st.expander(f"{LEVEL_BADGE[_level(c)]} {_md(c.q)}",
                             icon=icons.get(_status(c.id), ":material/help:")):
                st.markdown(_md(c.a))
                if c.points:
                    st.markdown("\n".join(f"- {_md(p)}" for p in c.points))


def _md(text: str) -> str:
    """Escape Markdown control characters (answers contain r_d, S·N(d₁), $…)."""
    for ch in "\\`*_[]#$~":
        text = text.replace(ch, "\\" + ch)
    return text
