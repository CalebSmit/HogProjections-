"""Streamlit entry point. Run with: uv run streamlit run app.py"""

import json
from datetime import date

import streamlit as st

from hogproj import __version__
from hogproj.config import get_settings
from hogproj.ui import (
    DERIVED_KEYS,
    SAVED_PREFIXES,
    asset,
    data_status,
    page_footer,
    saved_inputs,
    setup_page,
    warm_data,
)

st.set_page_config(
    page_title="Hog Projections",
    page_icon=str(asset("mark.svg")),
    layout="wide",
    initial_sidebar_state="auto",
)
setup_page()
ss = st.session_state

# Load a saved setup before any widget is created (values set after creation are rejected).
upload = ss.get("io_upload")
if upload is not None and ss.get("_io_loaded") != upload.file_id:
    try:
        values = json.loads(upload.getvalue().decode("utf-8")).get("inputs", {})
        for k, v in values.items():
            if str(k).startswith(SAVED_PREFIXES) and isinstance(v, (int, float, str, bool)):
                ss[k] = v
        for k in DERIVED_KEYS:
            ss.pop(k, None)
        ss["_io_message"] = f"Loaded {len(values)} inputs from {upload.name}."
    except (ValueError, AttributeError):
        ss["_io_message"] = "That file isn't a Hog Projections setup."
    ss["_io_loaded"] = upload.file_id

# Streamlit drops a widget's value when its page isn't shown. Re-assigning the keyed inputs
# on every run keeps them, so switching pages doesn't reset the user's assumptions.
for key in [k for k in ss if str(k).startswith(SAVED_PREFIXES)]:
    if key not in DERIVED_KEYS:
        ss[key] = ss[key]

page = st.navigation(
    {
        "Summary": [
            st.Page(
                "views/12_This_week.py",
                title="This week",
                icon=":material/today:",
                default=True,
            ),
            st.Page(
                "views/0_Overview.py",
                title="Farm outlook",
                icon=":material/space_dashboard:",
            ),
            st.Page("views/7_Guide.py", title="Guide", icon=":material/menu_book:"),
        ],
        "Your operation": [
            st.Page("views/1_Herd_flow.py", title="Herd flow", icon=":material/timeline:"),
            st.Page("views/11_Sow_farm.py", title="Sow farm", icon=":material/egg:"),
            st.Page(
                "views/2_Costs_and_returns.py",
                title="Costs & returns",
                icon=":material/request_quote:",
            ),
            st.Page(
                "views/8_Wean_to_finish.py",
                title="Wean to finish",
                icon=":material/swap_horiz:",
            ),
            st.Page(
                "views/9_Crush_history.py",
                title="Crush history",
                icon=":material/history:",
            ),
        ],
        "Decisions": [
            st.Page("views/4_Scenarios.py", title="Scenarios", icon=":material/compare_arrows:"),
            st.Page("views/10_Hedging.py", title="Hedging", icon=":material/lock:"),
            st.Page("views/5_Risk.py", title="Risk", icon=":material/shield:"),
        ],
        "Markets": [
            st.Page("views/3_Market_prices.py", title="Hog market", icon=":material/show_chart:"),
            st.Page("views/6_Hog_supply.py", title="Hog supply", icon=":material/inventory_2:"),
            st.Page("views/13_Archive.py", title="Market archive", icon=":material/table_view:"),
        ],
    },
    expanded=True,  # every page visible; the menu is the table of contents
)
warm_data()  # all USDA sources in parallel on the first run
page.run()
page_footer()

with st.sidebar:  # after the page so it sits below the page's own inputs
    st.header("Your setup")
    st.download_button(
        "Save inputs",
        json.dumps(
            {"app": "hog-projections", "saved": f"{date.today():%Y-%m-%d}",
             "inputs": saved_inputs()},
            indent=1,
        ),
        f"hog_projections_setup_{date.today():%Y-%m-%d}.json",
        "application/json",
        help="Download every number you've entered, to reload later or send to someone.",
        width="stretch",
    )  # fmt: skip
    st.file_uploader(
        "Load inputs",
        type=["json"],
        key="io_upload",
        help="Open a setup file saved from this app.",
        label_visibility="collapsed",
    )
    if msg := ss.get("_io_message"):
        st.caption(msg)
    with st.expander("Data status"):
        rows = "".join(
            f"<div style='display:flex;justify-content:space-between;gap:8px;font-size:12.5px;"
            f"padding:3px 0'><span>{name}</span><span style='color:var(--muted)'>{when}"
            f"{'' if how == 'live' else ' · saved'}</span></div>"
            for name, when, how in data_status()
        )
        st.markdown(rows, unsafe_allow_html=True)
    mode = "Offline · saved data" if get_settings().offline else "Online"
    st.markdown(
        f'<div class="hp-foot" style="margin-top:20px">Hog Projections {__version__} · {mode}'
        "</div>",
        unsafe_allow_html=True,
    )
