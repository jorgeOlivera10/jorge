"""Dashboard opcional en Streamlit (placeholder para más adelante).

Se implementará cuando la CLI y la BD estén maduras. Ejecutar con:
    pip install -e ".[dashboard]"
    streamlit run dashboard/streamlit_app.py
"""

import streamlit as st  # type: ignore


def main() -> None:
    st.set_page_config(page_title="Biwenger Analyzer", page_icon="⚽")
    st.title("⚽ Biwenger Analyzer")
    st.info("Dashboard pendiente de implementar. Usa la CLI: `biwenger --help`.")


if __name__ == "__main__":
    main()
