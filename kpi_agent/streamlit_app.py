"""
KPI Agent — Streamlit Cloud entry point.

For Streamlit Community Cloud deployment:
  1. Push this repo to GitHub
  2. Visit share.streamlit.io → New app
  3. Select your repo, branch, and this file as the main entry point
  4. Set secrets in Dashboard → Settings → Secrets (see .streamlit/secrets.toml)

Local usage:
  streamlit run streamlit_app.py
"""

import sys
from pathlib import Path

_pkg_dir = Path(__file__).resolve().parent
if str(_pkg_dir) not in sys.path:
    sys.path.insert(0, str(_pkg_dir))

import runpy
runpy.run_path(str(_pkg_dir / "app" / "streamlit_app.py"), run_name="__main__")
