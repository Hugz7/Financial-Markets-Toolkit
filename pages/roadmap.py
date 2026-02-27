"""
roadmap.py — Suggested Improvements (user-editable).
"""

import json
import os
import streamlit as st

SUGGESTIONS_FILE = os.path.join(os.path.dirname(__file__), "..", "suggestions.json")

DEFAULT_SUGGESTIONS = [
    {"title": "Volatility Smile / Skew", "description": "SABR, SVI, or spline interpolation", "priority": "High", "author": "System", "status": "Planned"},
    {"title": "Yield Curve Bootstrapping", "description": "Zero-coupon from swaps/bonds", "priority": "High", "author": "System", "status": "Planned"},
    {"title": "Variance Reduction MC", "description": "Antithetic variates, control variates, importance sampling — 50-70% error reduction", "priority": "High", "author": "System", "status": "Planned"},
    {"title": "VaR / CVaR", "description": "Parametric + historical 99%/95% + Expected Shortfall", "priority": "High", "author": "System", "status": "Planned"},
    {"title": "Multi-Asset Correlation", "description": "Cholesky decomposition for worst-of, best-of, rainbow options", "priority": "Medium", "author": "System", "status": "Planned"},
    {"title": "Heston Stochastic Vol", "description": "FFT Carr-Madan calibration", "priority": "Medium", "author": "System", "status": "Planned"},
    {"title": "Swaption Pricer", "description": "Black76, Bachelier, vol cube", "priority": "Medium", "author": "System", "status": "Planned"},
    {"title": "Binomial/Trinomial Trees", "description": "CRR for American options, early exercise boundary", "priority": "Medium", "author": "System", "status": "Planned"},
    {"title": "Jump-Diffusion (Merton)", "description": "Poisson jumps + lognormal for fat tails", "priority": "Low", "author": "System", "status": "Planned"},
    {"title": "PDF Report Generator", "description": "Automated export with charts and commentary", "priority": "Low", "author": "System", "status": "Planned"},
]

PRIORITY_COLORS = {
    "High":   ("", "rgba(255,77,109,0.10)",  "#FF4D6D"),
    "Medium": ("", "rgba(240,180,41,0.10)",  "#F0B429"),
    "Low":    ("", "rgba(56,189,248,0.10)",  "#38BDF8"),
}
STATUS_OPTIONS = ["Planned", "In Progress", "Done", "Rejected"]


def load_suggestions():
    if os.path.exists(SUGGESTIONS_FILE):
        with open(SUGGESTIONS_FILE, "r") as f:
            return json.load(f)
    return DEFAULT_SUGGESTIONS.copy()


def save_suggestions(suggestions):
    with open(SUGGESTIONS_FILE, "w") as f:
        json.dump(suggestions, f, indent=2)


def render():
    st.markdown("## Suggested Improvements")
    st.caption("Collaborative feature tracker — add, edit, and vote on improvements")

    if "suggestions" not in st.session_state:
        st.session_state.suggestions = load_suggestions()

    suggestions = st.session_state.suggestions

    # ── Stats bar ──
    total = len(suggestions)
    by_status = {s: sum(1 for x in suggestions if x["status"] == s) for s in STATUS_OPTIONS}
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total", total)
    c2.metric("High", sum(1 for x in suggestions if x["priority"] == "High"))
    c3.metric("Medium", sum(1 for x in suggestions if x["priority"] == "Medium"))
    c4.metric("Low", sum(1 for x in suggestions if x["priority"] == "Low"))
    c5.metric("Done", by_status.get("Done", 0))

    st.markdown("---")

    # ── Filter ──
    col_f1, col_f2 = st.columns([1, 1])
    with col_f1:
        filter_priority = st.selectbox("Filter by Priority", ["All", "High", "Medium", "Low"], key="sg_fp")
    with col_f2:
        filter_status = st.selectbox("Filter by Status", ["All"] + STATUS_OPTIONS, key="sg_fs")

    filtered = [
        (i, s) for i, s in enumerate(suggestions)
        if (filter_priority == "All" or s["priority"] == filter_priority)
        and (filter_status == "All" or s["status"] == filter_status)
    ]

    st.markdown(f"**{len(filtered)}** suggestion(s) shown")
    st.markdown("---")

    # ── List ──
    for orig_i, s in filtered:
        emoji, bg, color = PRIORITY_COLORS.get(s["priority"], ("", "rgba(255,255,255,0.05)", "#fff"))
        status_badge = ""

        with st.container():
            col_main, col_actions = st.columns([5, 1])
            with col_main:
                st.markdown(
                    f"<div style='background:{bg};border-left:3px solid {color};"
                    f"padding:10px 14px;border-radius:6px;margin-bottom:4px'>"
                    f"<b style='color:{color}'>{emoji} {s['title']}</b> "
                    f"<span style='color:#5A6A82;font-size:0.82em'>[{s['priority']}] {status_badge} {s['status']}"
                    f" · by {s['author']}</span><br>"
                    f"<span style='color:#9BAEC8;font-size:0.88em'>{s['description']}</span>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
            with col_actions:
                st.markdown("<div style='margin-top:6px'></div>", unsafe_allow_html=True)
                col_edit, col_del = st.columns(2)
                with col_edit:
                    if st.button("Edit", key=f"edit_{orig_i}", help="Edit"):
                        st.session_state[f"editing_{orig_i}"] = True
                with col_del:
                    if st.button("Del", key=f"del_{orig_i}", help="Delete"):
                        st.session_state.suggestions.pop(orig_i)
                        save_suggestions(st.session_state.suggestions)
                        st.rerun()

            # Inline edit form
            if st.session_state.get(f"editing_{orig_i}"):
                with st.form(key=f"form_edit_{orig_i}"):
                    new_title = st.text_input("Title", value=s["title"])
                    new_desc = st.text_area("Description", value=s["description"])
                    new_prio = st.selectbox("Priority", ["High", "Medium", "Low"],
                                            index=["High", "Medium", "Low"].index(s["priority"]))
                    new_status = st.selectbox("Status", STATUS_OPTIONS,
                                              index=STATUS_OPTIONS.index(s["status"]))
                    col_save, col_cancel = st.columns(2)
                    with col_save:
                        submitted = st.form_submit_button("Save", type="primary")
                    with col_cancel:
                        cancelled = st.form_submit_button("Cancel")

                    if submitted:
                        st.session_state.suggestions[orig_i].update(
                            title=new_title, description=new_desc,
                            priority=new_prio, status=new_status)
                        save_suggestions(st.session_state.suggestions)
                        st.session_state[f"editing_{orig_i}"] = False
                        st.rerun()
                    if cancelled:
                        st.session_state[f"editing_{orig_i}"] = False
                        st.rerun()

    # ── Add new suggestion ──
    st.markdown("---")
    st.markdown("#### Add a Suggestion")
    with st.form("add_suggestion_form", clear_on_submit=True):
        col1, col2 = st.columns([3, 1])
        with col1:
            new_title = st.text_input("Title *", placeholder="Short, descriptive title")
        with col2:
            new_priority = st.selectbox("Priority", ["High", "Medium", "Low"])
        new_desc = st.text_area("Description", placeholder="What should be built and why?", height=80)
        new_author = st.text_input("Your name / initials", placeholder="e.g. Hugo")

        submitted = st.form_submit_button("Submit Suggestion", type="primary")
        if submitted and new_title.strip():
            st.session_state.suggestions.append({
                "title": new_title.strip(),
                "description": new_desc.strip(),
                "priority": new_priority,
                "author": new_author.strip() or "Anonymous",
                "status": "Planned",
            })
            save_suggestions(st.session_state.suggestions)
            st.success(f"'{new_title}' added!")
            st.rerun()
        elif submitted:
            st.warning("Title is required.")
