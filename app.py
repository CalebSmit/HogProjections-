"""Streamlit entry point. Run with: uv run streamlit run app.py"""

import streamlit as st

from hogproj import __version__
from hogproj.config import get_settings

st.set_page_config(page_title="Hog Projections", page_icon="🐖", layout="wide")


def home() -> None:
    st.title("Hog Projections")
    st.caption(f"v{__version__} · early build — features land phase by phase (see docs/PLAN.md)")

    st.markdown(
        """
    Plan a hog operation week by week: how many pigs you'll sell, what they cost to raise,
    and what they're likely to earn. Pick a page in the sidebar.

    | Page | What it answers |
    |---|---|
    | **Herd flow** | Pigs reaching market each week, and when a sow-herd change shows up |
    | **Costs & returns** | Breakeven price, cost per head, and margin across hog and corn prices |

    Every number starts at a published US industry benchmark. Change any input to match your farm.
    """
    )
    st.page_link("views/1_Herd_flow.py", label="Open Herd flow", icon="🐷")
    st.page_link("views/2_Costs_and_returns.py", label="Open Costs & returns", icon="💵")

    settings = get_settings()
    mode = "offline (sample data)" if settings.offline else "online (USDA APIs)"
    st.caption(f"Data mode: {mode}")


# Streamlit drops a widget's value when its page isn't shown. Re-assigning the keyed inputs
# on every run keeps them, so switching pages doesn't reset the user's assumptions.
for key in [k for k in st.session_state if str(k).startswith(("herd_", "cost_"))]:
    if key != "herd_inputs":
        st.session_state[key] = st.session_state[key]

st.navigation(
    [
        st.Page(home, title="Home", icon="🏠", default=True),
        st.Page("views/1_Herd_flow.py", title="Herd flow", icon="🐷"),
        st.Page("views/2_Costs_and_returns.py", title="Costs & returns", icon="💵"),
    ]
).run()
