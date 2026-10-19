"""Streamlit entry point. Run with: uv run streamlit run app.py"""

import streamlit as st

from hogproj import __version__
from hogproj.config import get_settings
from hogproj.ui import asset, page_footer, setup_page

st.set_page_config(
    page_title="Hog Projections",
    page_icon=str(asset("mark.svg")),
    layout="wide",
    initial_sidebar_state="expanded",
)
setup_page()

# Streamlit drops a widget's value when its page isn't shown. Re-assigning the keyed inputs
# on every run keeps them, so switching pages doesn't reset the user's assumptions.
for key in [
    k for k in st.session_state if str(k).startswith(("herd_", "cost_", "scn_", "risk_", "mkt_"))
]:
    if key not in ("herd_inputs", "cost_inputs"):
        st.session_state[key] = st.session_state[key]

page = st.navigation(
    {
        "Summary": [
            st.Page(
                "views/0_Overview.py",
                title="Overview",
                icon=":material/space_dashboard:",
                default=True,
            ),
        ],
        "Your operation": [
            st.Page("views/1_Herd_flow.py", title="Herd flow", icon=":material/timeline:"),
            st.Page(
                "views/2_Costs_and_returns.py",
                title="Costs & returns",
                icon=":material/request_quote:",
            ),
        ],
        "Decisions": [
            st.Page("views/4_Scenarios.py", title="Scenarios", icon=":material/compare_arrows:"),
            st.Page("views/5_Risk.py", title="Risk", icon=":material/shield:"),
        ],
        "Markets": [
            st.Page(
                "views/3_Market_prices.py", title="Market prices", icon=":material/show_chart:"
            ),
        ],
    }
)
page.run()
page_footer()
with st.sidebar:  # after the page so it sits below the page's own inputs
    mode = "Offline · saved data" if get_settings().offline else "Online"
    st.markdown(
        f'<div class="hp-foot" style="margin-top:28px">Hog Projections {__version__} · {mode}'
        "</div>",
        unsafe_allow_html=True,
    )
