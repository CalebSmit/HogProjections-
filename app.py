"""Streamlit entry point. Run with: uv run streamlit run app.py"""

import streamlit as st

from hogproj import __version__
from hogproj.config import get_settings

st.set_page_config(page_title="Hog Projections", page_icon="🐖", layout="wide")

# Streamlit drops a widget's value when its page isn't shown. Re-assigning the keyed inputs
# on every run keeps them, so switching pages doesn't reset the user's assumptions.
for key in [k for k in st.session_state if str(k).startswith(("herd_", "cost_", "scn_", "risk_"))]:
    if key not in ("herd_inputs", "cost_inputs"):
        st.session_state[key] = st.session_state[key]

page = st.navigation(
    {
        "Summary": [
            st.Page("views/0_Overview.py", title="Overview", icon="🏠", default=True),
        ],
        "Your farm": [
            st.Page("views/1_Herd_flow.py", title="Herd flow", icon="🐷"),
            st.Page("views/2_Costs_and_returns.py", title="Costs & returns", icon="💵"),
        ],
        "Decide": [
            st.Page("views/4_Scenarios.py", title="Scenarios", icon="🔀"),
        ],
        "Markets": [
            st.Page("views/3_Market_prices.py", title="Market prices", icon="📈"),
        ],
    }
)
with st.sidebar:
    mode = "offline (saved data)" if get_settings().offline else "online"
    st.caption(f"Hog Projections v{__version__} · {mode}")
page.run()
