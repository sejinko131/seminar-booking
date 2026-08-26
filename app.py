# Main Streamlit entry point.
# Configure the page before importing modules that register Streamlit caches/widgets.
import streamlit as st

st.set_page_config(page_title="세미나실 대관시스템", page_icon="📅", layout="wide")

# app_v2 currently contains a second set_page_config call. Suppress only that
# duplicate call during import for compatibility with Streamlit Cloud versions
# that require set_page_config to be the very first Streamlit command.
_original_set_page_config = st.set_page_config
st.set_page_config = lambda *args, **kwargs: None
try:
    from app_v2 import *  # noqa: F401,F403
finally:
    st.set_page_config = _original_set_page_config
