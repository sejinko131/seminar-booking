# Main Streamlit entry point.
# Configure the page before importing modules that register Streamlit caches/widgets.
import streamlit as st

st.set_page_config(page_title="세미나실 대관시스템", page_icon="📅", layout="wide")

import booking_core as _booking_core

# Do not block the first page render on Google Sheets.
# Booking/create/edit/cancel actions still use load_fresh_values() directly.
_original_load_data_cached = _booking_core.load_data_cached
_booking_core.load_data_cached = lambda: ([], [])

# app_v2 currently contains a second set_page_config call. Suppress only that
# duplicate call during import for compatibility with Streamlit Cloud versions
# that require set_page_config to be the very first Streamlit command.
_original_set_page_config = st.set_page_config
st.set_page_config = lambda *args, **kwargs: None
try:
    from app_v2 import *  # noqa: F401,F403
except Exception as exc:
    st.error("앱 초기화 중 오류가 발생했습니다.")
    st.exception(exc)
finally:
    st.set_page_config = _original_set_page_config
    _booking_core.load_data_cached = _original_load_data_cached
