# Streamlit entry point.
# app_v2 contains the actual UI. Imported modules are cached by Python, so
# explicitly reload app_v2 on every Streamlit script run to re-render the UI.
import importlib
import sys

import streamlit as st

st.set_page_config(page_title="세미나실 대관시스템", page_icon="📅", layout="wide")

# app_v2 also contains set_page_config for direct/local execution. Suppress only
# that duplicate call while executing it through this entry point.
_original_set_page_config = st.set_page_config
st.set_page_config = lambda *args, **kwargs: None

try:
    if "app_v2" in sys.modules:
        importlib.reload(sys.modules["app_v2"])
    else:
        import app_v2  # noqa: F401
except Exception as exc:
    st.error("앱 초기화 중 오류가 발생했습니다.")
    st.exception(exc)
finally:
    st.set_page_config = _original_set_page_config
