# Main Streamlit entry point.
# Configure the page before importing modules that register Streamlit caches/widgets.
import streamlit as st

st.set_page_config(page_title="세미나실 대관시스템", page_icon="📅", layout="wide")

# Temporary startup diagnostics: these markers make cloud-only startup stalls visible.
_startup_marker = st.empty()
_startup_marker.caption("앱 초기화 중...")

import booking_core as _booking_core

_original_load_data_cached = _booking_core.load_data_cached

def _diagnostic_load_data_cached():
    _startup_marker.caption("예약 데이터를 불러오는 중...")
    result = _original_load_data_cached()
    _startup_marker.caption("화면을 구성하는 중...")
    return result

_booking_core.load_data_cached = _diagnostic_load_data_cached

# app_v2 currently contains a second set_page_config call. Suppress only that
# duplicate call during import for compatibility with Streamlit Cloud versions
# that require set_page_config to be the very first Streamlit command.
_original_set_page_config = st.set_page_config
st.set_page_config = lambda *args, **kwargs: None
try:
    from app_v2 import *  # noqa: F401,F403
    _startup_marker.empty()
except Exception as exc:
    _startup_marker.empty()
    st.error("앱 초기화 중 오류가 발생했습니다.")
    st.exception(exc)
finally:
    st.set_page_config = _original_set_page_config
    _booking_core.load_data_cached = _original_load_data_cached
