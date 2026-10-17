"""Streamlit entry point. Run with: uv run streamlit run app.py"""

import streamlit as st

from hogproj import __version__
from hogproj.config import get_settings

st.set_page_config(page_title="Hog Projections", page_icon="🐖", layout="wide")

st.title("Hog Projections")
st.caption(f"v{__version__} · scaffold — features land phase by phase (see docs/PLAN.md)")

settings = get_settings()
st.write("Data mode:", "offline (sample data)" if settings.offline else "online (USDA APIs)")
