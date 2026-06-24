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

# Ensure app/ is importable
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Run the full Streamlit app
app_path = Path(__file__).resolve().parent / "app" / "streamlit_app.py"
code = compile(app_path.read_text(encoding="utf-8"), str(app_path), "exec")
exec(code, {"__name__": "__main__", "__file__": str(app_path)})
