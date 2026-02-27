"""
main.py — Structured Products Pricer
Run with: streamlit run main.py
"""

import streamlit as st

# ── Page Config (must be first Streamlit command) ──
st.set_page_config(
    page_title="Structured Products Pricer",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ──
st.markdown("""
<style>
    /* ── Google Font ── */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    /* ── Global ── */
    html, body, [class*="css"] {
        font-family: 'Inter', 'SF Pro Display', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    .stApp {
        background-color: #080C14;
        background-image:
            radial-gradient(ellipse 60% 50% at 15% 10%, rgba(0,229,255,0.055) 0%, transparent 65%),
            radial-gradient(ellipse 50% 40% at 88% 85%, rgba(56,189,248,0.04) 0%, transparent 60%),
            radial-gradient(ellipse 40% 60% at 50% 50%, rgba(10,20,50,0.6) 0%, transparent 100%);
        color: #E8EDF5;
    }
    /* Subtle dot-grid texture on main content */
    .main .block-container {
        background-image: radial-gradient(rgba(30,58,85,0.18) 1px, transparent 1px);
        background-size: 24px 24px;
        background-position: 0 0;
    }

    /* ── Sidebar ── */
    section[data-testid="stSidebar"] {
        background-color: #080E1C;
        background-image:
            radial-gradient(ellipse 80% 40% at 50% 0%, rgba(0,229,255,0.06) 0%, transparent 70%),
            linear-gradient(180deg, #0A1220 0%, #080E1C 100%);
        border-right: 1px solid #1A2E45;
    }
    section[data-testid="stSidebar"]::before {
        content: '';
        display: block;
        height: 2px;
        background: linear-gradient(90deg, #00E5FF 0%, #38BDF8 50%, transparent 100%);
        position: sticky;
        top: 0;
        z-index: 100;
        box-shadow: 0 0 16px rgba(0,229,255,0.5);
    }
    section[data-testid="stSidebar"] .stMarkdown h1 {
        color: #00E5FF;
        font-size: 1.1rem;
        font-weight: 700;
        letter-spacing: 0.04em;
        text-transform: uppercase;
    }
    section[data-testid="stSidebar"] .stMarkdown h5 {
        color: #5A6A82;
        font-size: 0.72rem;
        font-weight: 500;
        letter-spacing: 0.06em;
        text-transform: uppercase;
    }
    section[data-testid="stSidebar"] .stMarkdown p,
    section[data-testid="stSidebar"] .stMarkdown li {
        color: #7B8EA8;
        font-size: 0.82rem;
    }
    /* Sidebar nav radio */
    section[data-testid="stSidebar"] .stRadio label {
        color: #9BAEC8 !important;
        font-size: 0.88rem !important;
        font-weight: 400;
        padding: 4px 0;
        transition: color 0.15s;
    }
    section[data-testid="stSidebar"] .stRadio label:hover {
        color: #00E5FF !important;
    }

    /* ── Page headings ── */
    .stMarkdown h2 {
        color: #E8EDF5;
        font-weight: 700;
        font-size: 1.4rem;
        letter-spacing: -0.01em;
        border-bottom: 1px solid #1A2E45;
        padding-bottom: 0.4rem;
        margin-bottom: 0.5rem;
    }
    .stMarkdown h3 {
        color: #38BDF8;
        font-weight: 600;
        font-size: 1.0rem;
        letter-spacing: 0.02em;
        text-transform: uppercase;
    }
    .stMarkdown h4 {
        color: #9BAEC8;
        font-weight: 600;
        font-size: 0.88rem;
        letter-spacing: 0.05em;
        text-transform: uppercase;
        margin-top: 0.8rem;
        margin-bottom: 0.3rem;
    }

    /* ── Metric cards — glassmorphism ── */
    [data-testid="stMetric"] {
        background: rgba(10, 20, 36, 0.70) !important;
        backdrop-filter: blur(12px) !important;
        -webkit-backdrop-filter: blur(12px) !important;
        border: 1px solid rgba(0, 229, 255, 0.14) !important;
        border-radius: 10px !important;
        padding: 12px 16px !important;
        box-shadow: 0 4px 24px rgba(0,0,0,0.45), inset 0 1px 0 rgba(255,255,255,0.04) !important;
        transition: border-color 0.2s, box-shadow 0.2s;
        position: relative;
        overflow: hidden;
    }
    [data-testid="stMetric"]::before {
        content: '';
        position: absolute;
        top: 0; left: 0; right: 0;
        height: 1px;
        background: linear-gradient(90deg, transparent, rgba(0,229,255,0.35), transparent);
    }
    [data-testid="stMetric"]:hover {
        border-color: rgba(0,229,255,0.30) !important;
        box-shadow: 0 6px 28px rgba(0,229,255,0.10), 0 4px 24px rgba(0,0,0,0.5) !important;
    }
    [data-testid="stMetricValue"] {
        color: #00E5FF !important;
        font-weight: 700 !important;
        font-size: 1.3rem !important;
        font-variant-numeric: tabular-nums;
        letter-spacing: -0.01em;
        text-shadow: 0 0 12px rgba(0,229,255,0.4);
    }
    [data-testid="stMetricLabel"] {
        color: #5A6A82 !important;
        font-size: 0.70rem !important;
        font-weight: 600 !important;
        text-transform: uppercase;
        letter-spacing: 0.07em;
    }
    [data-testid="stMetricDelta"] {
        font-size: 0.76rem !important;
    }

    /* ── DataFrames / Tables ── */
    .stDataFrame {
        background: rgba(8,16,28,0.75) !important;
        backdrop-filter: blur(8px) !important;
        -webkit-backdrop-filter: blur(8px) !important;
        border: 1px solid rgba(0,229,255,0.10) !important;
        border-radius: 10px !important;
        overflow: hidden;
        box-shadow: 0 4px 20px rgba(0,0,0,0.4);
    }
    .stDataFrame thead tr th {
        background-color: rgba(5,12,24,0.9) !important;
        color: #5A6A82 !important;
        font-size: 0.70rem !important;
        font-weight: 700 !important;
        text-transform: uppercase;
        letter-spacing: 0.07em;
        border-bottom: 1px solid #1A2E45 !important;
    }
    .stDataFrame tbody tr td {
        color: #C5D2E0 !important;
        font-size: 0.84rem !important;
        border-bottom: 1px solid rgba(26,46,69,0.5) !important;
        font-variant-numeric: tabular-nums;
    }
    .stDataFrame tbody tr:hover td {
        background-color: rgba(0,229,255,0.04) !important;
    }

    /* ── Primary button ── */
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #005F7A 0%, #007EA6 50%, #0095C2 100%);
        color: #E8EDF5;
        border: 1px solid rgba(0,229,255,0.35);
        border-radius: 8px;
        font-weight: 600;
        font-size: 0.88rem;
        letter-spacing: 0.04em;
        padding: 0.5rem 1.4rem;
        transition: all 0.25s;
        box-shadow: 0 0 16px rgba(0,229,255,0.20), 0 2px 8px rgba(0,0,0,0.4);
        text-shadow: 0 0 8px rgba(0,229,255,0.3);
    }
    .stButton > button[kind="primary"]:hover {
        background: linear-gradient(135deg, #007FA8 0%, #00AACC 100%);
        border-color: rgba(0,229,255,0.65);
        box-shadow: 0 0 28px rgba(0,229,255,0.40), 0 2px 12px rgba(0,0,0,0.5);
        transform: translateY(-1px);
    }
    .stButton > button[kind="primary"]:active {
        transform: translateY(0);
    }
    .stButton > button {
        background-color: #111E2E;
        color: #9BAEC8;
        border: 1px solid #1A2E45;
        border-radius: 6px;
        font-size: 0.84rem;
        transition: all 0.15s;
    }
    .stButton > button:hover {
        background-color: #162840;
        color: #E8EDF5;
        border-color: #38BDF8;
    }

    /* ── Inputs ── */
    .stNumberInput input,
    .stTextInput input,
    .stTextArea textarea {
        background-color: #0F1923 !important;
        color: #C5D2E0 !important;
        border: 1px solid #1A2E45 !important;
        border-radius: 6px !important;
        font-size: 0.88rem !important;
        font-variant-numeric: tabular-nums;
        transition: border-color 0.15s;
    }
    .stNumberInput input:focus,
    .stTextInput input:focus,
    .stTextArea textarea:focus {
        border-color: #00E5FF88 !important;
        box-shadow: 0 0 0 2px rgba(0,229,255,0.1) !important;
    }
    .stNumberInput label,
    .stTextInput label,
    .stTextArea label,
    .stSelectbox label,
    .stRadio label,
    .stSlider label {
        color: #7B8EA8 !important;
        font-size: 0.78rem !important;
        font-weight: 500 !important;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }

    /* ── Selectbox ── */
    .stSelectbox > div > div {
        background-color: #0F1923 !important;
        color: #C5D2E0 !important;
        border: 1px solid #1A2E45 !important;
        border-radius: 6px !important;
    }

    /* ── Slider ── */
    .stSlider .stSlider > div {
        color: #00E5FF;
    }

    /* ── Select Slider ── */
    .stSelectSlider > div {
        color: #9BAEC8;
    }

    /* ── Toggle ── */
    .stToggle label {
        color: #9BAEC8 !important;
    }

    /* ── Expanders ── */
    details[data-testid="stExpander"] summary {
        background: rgba(10,20,36,0.65);
        backdrop-filter: blur(10px);
        -webkit-backdrop-filter: blur(10px);
        border: 1px solid rgba(0,229,255,0.12);
        border-radius: 8px;
        color: #9BAEC8;
        font-size: 0.85rem;
        font-weight: 500;
        padding: 9px 14px;
        transition: all 0.15s;
        box-shadow: 0 2px 12px rgba(0,0,0,0.3);
    }
    details[data-testid="stExpander"] summary:hover {
        border-color: rgba(56,189,248,0.4);
        color: #38BDF8;
        box-shadow: 0 2px 16px rgba(0,229,255,0.08);
    }
    details[data-testid="stExpander"] {
        border: none !important;
    }
    details[data-testid="stExpander"][open] summary {
        border-radius: 8px 8px 0 0;
        border-color: rgba(0,229,255,0.25);
        color: #00E5FF;
    }
    details[data-testid="stExpander"] > div {
        background: rgba(8,16,28,0.55);
        border: 1px solid rgba(0,229,255,0.08);
        border-top: none;
        border-radius: 0 0 8px 8px;
        backdrop-filter: blur(8px);
        -webkit-backdrop-filter: blur(8px);
    }

    /* ── Info / Warning / Success boxes ── */
    .stInfo {
        background-color: #0B1F35 !important;
        border-left: 3px solid #38BDF8 !important;
        border-radius: 0 6px 6px 0 !important;
        color: #9BAEC8 !important;
    }
    .stSuccess {
        background-color: #0A2218 !important;
        border-left: 3px solid #10D48A !important;
        border-radius: 0 6px 6px 0 !important;
        color: #9BAEC8 !important;
    }
    .stWarning {
        background-color: #1E1500 !important;
        border-left: 3px solid #F0B429 !important;
        border-radius: 0 6px 6px 0 !important;
    }

    /* ── Dividers ── */
    hr {
        border-color: #1A2E45 !important;
        margin: 0.75rem 0;
    }

    /* ── Caption text ── */
    .stCaption, .stMarkdown small {
        color: #5A6A82 !important;
        font-size: 0.76rem !important;
    }

    /* ── Form submit button ── */
    .stFormSubmitButton > button {
        background: linear-gradient(135deg, #006B8A 0%, #0090B8 100%) !important;
        color: #E8EDF5 !important;
        border: 1px solid #00E5FF44 !important;
        border-radius: 6px !important;
        font-weight: 600 !important;
        font-size: 0.88rem !important;
    }
    .stFormSubmitButton > button:hover {
        box-shadow: 0 0 16px rgba(0,229,255,0.25) !important;
    }

    /* ── Spinner ── */
    .stSpinner > div {
        border-top-color: #00E5FF !important;
    }

    /* ── Tab styling (if any) ── */
    .stTabs [data-baseweb="tab-list"] {
        background-color: #0B1220;
        border-bottom: 1px solid #1A2E45;
    }
    .stTabs [data-baseweb="tab"] {
        color: #5A6A82;
        font-size: 0.84rem;
        font-weight: 500;
    }
    .stTabs [aria-selected="true"] {
        color: #00E5FF !important;
        border-bottom: 2px solid #00E5FF !important;
    }

    /* ── Non-collapsible sidebar ──
       Force the sidebar to always stay on-screen (prevent the CSS transform
       that slides it off). Also hide the collapse arrow inside the sidebar. */
    section[data-testid="stSidebar"] {
        transform: translateX(0) !important;
        min-width: 260px !important;
    }
    button[data-testid="baseButton-header"]   {display: none !important;}
    [data-testid="stSidebarCollapseButton"]   {display: none !important;}
    /* NOTE: do NOT hide [data-testid="collapsedControl"] — that is the
       reopen button shown when sidebar is collapsed. Hiding it locks users out. */

    /* ── Sidebar custom nav buttons ── */
    section[data-testid="stSidebar"] button[data-testid="stBaseButton-primary"] {
        background: rgba(0,229,255,0.10) !important;
        color: #00E5FF !important;
        border: 1px solid rgba(0,229,255,0.22) !important;
        border-radius: 6px !important;
        font-size: 0.83rem !important;
        font-weight: 600 !important;
        letter-spacing: 0.01em;
        box-shadow: none !important;
        padding: 5px 10px !important;
        text-align: left !important;
    }
    section[data-testid="stSidebar"] button[data-testid="stBaseButton-secondary"] {
        background: transparent !important;
        color: #7B8EA8 !important;
        border: 1px solid transparent !important;
        border-radius: 6px !important;
        font-size: 0.83rem !important;
        font-weight: 400 !important;
        box-shadow: none !important;
        padding: 5px 10px !important;
    }
    section[data-testid="stSidebar"] button[data-testid="stBaseButton-secondary"]:hover {
        background: rgba(0,229,255,0.05) !important;
        color: #C5D2E0 !important;
        border-color: rgba(0,229,255,0.12) !important;
    }

    /* ── Hide Streamlit branding ── */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    [data-testid="stSidebarNavItems"] {display: none;}
    [data-testid="stPageLink"] {display: none;}
</style>
""", unsafe_allow_html=True)

# ── Navigation state ──
if "page" not in st.session_state:
    st.session_state["page"] = "Market Monitor"


def _nav(label):
    active = st.session_state["page"] == label
    if st.button(label, key=f"_nav_{label}", use_container_width=True,
                 type="primary" if active else "secondary"):
        st.session_state["page"] = label
        st.rerun()


_SEP = ("<hr style='border:none;border-top:1px solid #1A2E45;"
        "margin:5px 0;opacity:0.7'>")

# ── Sidebar ──
with st.sidebar:
    st.markdown(
        "<div style='padding:12px 4px 6px 4px'>"
        "<span style='color:#00E5FF;font-size:1.0rem;font-weight:700;"
        "letter-spacing:0.06em;text-transform:uppercase;'>Financial Markets Toolkit</span><br>"
        "<span style='color:#3A4A5C;font-size:0.66rem;letter-spacing:0.07em;"
        "text-transform:uppercase;'>Derivatives · Rates · Simulation</span>"
        "</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div style='height:1px;background:linear-gradient(90deg,#00E5FF55,transparent);"
        "margin:8px 0 10px 0'></div>",
        unsafe_allow_html=True,
    )

    _nav("Market Monitor")
    st.markdown(_SEP, unsafe_allow_html=True)
    _nav("Payoff Analyzer")
    _nav("Exotic Pricer")
    _nav("Vol Smile")
    _nav("Swaps")
    _nav("Forwards")
    _nav("Monte Carlo")
    st.markdown(_SEP, unsafe_allow_html=True)
    _nav("Suggested Improvements")

    st.markdown(
        "<div style='height:1px;background:linear-gradient(90deg,#1A2E45,transparent);"
        "margin:12px 0 8px 0'></div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div style='color:#3A4A5C;font-size:0.66rem;letter-spacing:0.04em'>"
        "Python · Streamlit · NumPy · SciPy · Plotly"
        "</div>",
        unsafe_allow_html=True,
    )

page = st.session_state["page"]

# ── Page Routing ──
if page == "Market Monitor":
    from pages.home_dashboard import render
    render()

elif page == "Payoff Analyzer":
    from pages.structured_products import render
    render()

elif page == "Exotic Pricer":
    from pages.exotic_pricer import render
    render()

elif page == "Vol Smile":
    from pages.vol_smile_page import render
    render()

elif page == "Swaps":
    from pages.swaps_page import render
    render()

elif page == "Forwards":
    from pages.forwards_page import render
    render()

elif page == "Monte Carlo":
    from pages.monte_carlo_page import render
    render()

elif page == "Suggested Improvements":
    from pages.roadmap import render
    render()
