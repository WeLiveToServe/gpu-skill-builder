"""Streamlit entrypoint for Community Cloud deployment."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

st.set_page_config(
    page_title="GPU Skill Builder",
    page_icon=":rocket:",
    layout="wide",
)

REPO_URL = "https://github.com/WeLiveToServe/gpu-skill-builder"

st.title("GPU Skill Builder")
st.caption(
    "Provision open-source GPU inference endpoints across providers with built-in safety guardrails."
)

col1, col2 = st.columns(2)
with col1:
    st.subheader("What This Project Does")
    st.markdown(
        "- Provisions GPU endpoints from multiple providers\n"
        "- Loads open-source models that fit selected hardware\n"
        "- Returns OpenAI-compatible endpoint configuration for coding harnesses"
    )

with col2:
    st.subheader("Quick Links")
    st.markdown(f"- [GitHub Repository]({REPO_URL})")
    st.markdown("- [Project README](README.md)")
    st.markdown("- [Handoff Plan](handoff-plan.md)")

st.subheader("Run Locally")
st.code(
    "pip install -r requirements.txt\n"
    "streamlit run streamlit_app.py",
    language="bash",
)

readme_path = Path(__file__).with_name("README.md")
if readme_path.exists():
    st.subheader("README Preview")
    st.markdown(readme_path.read_text(encoding="utf-8"))
else:
    st.info("README.md not found.")
