"""views/roadmap.py — Collaborative feature tracker (persisted to suggestions.json)."""

import streamlit as st

from services.suggestions import PRIORITIES, STATUSES, load_suggestions, save_suggestions
from ui.components import panel, Stat, badges, empty_state, page_header, section, stat_grid

_PRIORITY_TONE = {"High": "neg", "Medium": "warn", "Low": "accent"}
_STATUS_TONE = {"Done": "pos", "In Progress": "accent", "Planned": "default", "Rejected": "default"}


def _persist_and_rerun() -> None:
    save_suggestions(st.session_state.suggestions)
    st.rerun()


def _edit_form(i: int, s: dict) -> None:
    with st.form(key=f"form_edit_{i}", border=False):
        new_title = st.text_input("Title", value=s["title"])
        new_desc = st.text_area("Description", value=s["description"])
        a, b = st.columns(2)
        new_prio = a.selectbox("Priority", PRIORITIES, index=PRIORITIES.index(s["priority"]))
        new_status = b.selectbox("Status", STATUSES, index=STATUSES.index(s["status"]))
        save_col, cancel_col, _ = st.columns([1, 1, 4])
        submitted = save_col.form_submit_button("Save", type="primary", width="stretch")
        cancelled = cancel_col.form_submit_button("Cancel", width="stretch")
    if submitted:
        st.session_state.suggestions[i].update(
            title=new_title, description=new_desc, priority=new_prio, status=new_status)
        st.session_state[f"editing_{i}"] = False
        _persist_and_rerun()
    if cancelled:
        st.session_state[f"editing_{i}"] = False
        st.rerun()


def _item(i: int, s: dict) -> None:
    with panel():
        main, actions = st.columns([9, 1], vertical_alignment="center")
        with main:
            st.markdown(f"**{s['title']}**")
            badges([(s["priority"], _PRIORITY_TONE.get(s["priority"], "default")),
                    (s["status"], _STATUS_TONE.get(s["status"], "default"))])
            if s.get("description"):
                st.caption(f"{s['description']} · by {s['author']}")
            else:
                st.caption(f"by {s['author']}")
        with actions:
            e, d = st.columns(2)
            if e.button("", key=f"edit_{i}", icon=":material/edit:", help="Edit"):
                st.session_state[f"editing_{i}"] = True
            if d.button("", key=f"del_{i}", icon=":material/delete:", help="Delete"):
                st.session_state.suggestions.pop(i)
                _persist_and_rerun()
        if st.session_state.get(f"editing_{i}"):
            _edit_form(i, s)


def render():
    page_header("Roadmap",
                "Collaborative feature tracker — add, edit and prioritise improvements.",
                eyebrow="Project")

    if "suggestions" not in st.session_state:
        st.session_state.suggestions = load_suggestions()
    suggestions = st.session_state.suggestions

    count = lambda key, val: sum(1 for x in suggestions if x[key] == val)  # noqa: E731
    stat_grid([
        Stat("Total", str(len(suggestions))),
        Stat("High priority", str(count("priority", "High")), tone="neg"),
        Stat("Medium priority", str(count("priority", "Medium")), tone="warn"),
        Stat("Low priority", str(count("priority", "Low")), tone="accent"),
        Stat("Done", str(count("status", "Done")), tone="pos"),
    ], columns=5)

    section("Backlog")
    f1, f2, _ = st.columns([1, 1, 2])
    filter_priority = f1.selectbox("Priority", ["All"] + PRIORITIES, key="sg_fp")
    filter_status = f2.selectbox("Status", ["All"] + STATUSES, key="sg_fs")
    filtered = [
        (i, s) for i, s in enumerate(suggestions)
        if (filter_priority == "All" or s["priority"] == filter_priority)
        and (filter_status == "All" or s["status"] == filter_status)
    ]
    st.caption(f"{len(filtered)} of {len(suggestions)} shown")

    if not filtered:
        empty_state("Nothing matches these filters", "Change the priority or status filter.")
    for i, s in filtered:
        _item(i, s)

    section("Add a suggestion")
    with panel():
        with st.form("add_suggestion_form", clear_on_submit=True, border=False):
            a, b, c = st.columns([3, 1, 1.4])
            new_title = a.text_input("Title *", placeholder="Short, descriptive title")
            new_priority = b.selectbox("Priority", PRIORITIES)
            new_author = c.text_input("Your name / initials", placeholder="e.g. Hugo")
            new_desc = st.text_area("Description", placeholder="What should be built and why?",
                                    height=80)
            submitted = st.form_submit_button("Add suggestion", type="primary",
                                              icon=":material/add:")
        if submitted and new_title.strip():
            st.session_state.suggestions.append({
                "title": new_title.strip(), "description": new_desc.strip(),
                "priority": new_priority, "author": new_author.strip() or "Anonymous",
                "status": "Planned",
            })
            save_suggestions(st.session_state.suggestions)
            st.toast(f"“{new_title.strip()}” added", icon=":material/check:")
            st.rerun()
        elif submitted:
            st.warning("Title is required.")
