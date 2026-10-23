import os

from dotenv import load_dotenv

ENV_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    ".env",
)

# Local development only; harmless if the file does not exist.
load_dotenv(ENV_PATH, override=True, encoding="utf-8-sig")


def _setting(name, default=""):
    """Streamlit Secrets first (cloud), then environment / .env (local)."""
    try:
        import streamlit as st

        if name in st.secrets:
            return str(st.secrets[name])
    except Exception:
        pass  # no secrets configured (e.g. running a script locally)

    return os.getenv(name, default)


RAPIDAPI_KEY = _setting("RAPIDAPI_KEY").strip()
RAPIDAPI_HOST = _setting(
    "RAPIDAPI_HOST", "cricbuzz-cricket.p.rapidapi.com"
).strip()