"""Database engine and session configuration.

For local development: uses SQLite (kpi_agent.db).
For Streamlit Cloud / production: set DATABASE_URL to a PostgreSQL connection string.

The DATABASE_URL is read from:
1. Environment variable DATABASE_URL
2. Streamlit secrets (st.secrets["DATABASE_URL"])
3. Default: SQLite at <project_root>/kpi_agent.db

If PostgreSQL is configured but unreachable, falls back to SQLite automatically.
"""

import os
import logging
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase

logger = logging.getLogger(__name__)

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "")

# Try Streamlit secrets if available (Streamlit Cloud)
if not DATABASE_URL:
    try:
        import streamlit as st
        DATABASE_URL = st.secrets.get("DATABASE_URL", "")
    except Exception:
        pass

# Fallback: local SQLite
if not DATABASE_URL:
    DATABASE_URL = f"sqlite:///{Path(__file__).resolve().parent.parent / 'kpi_agent.db'}"

IS_SQLITE = "sqlite" in DATABASE_URL

# SQLite needs check_same_thread=False; PostgreSQL doesn't
_connect_args = {"check_same_thread": False} if IS_SQLITE else {}

_original_url = DATABASE_URL
engine = create_engine(
    DATABASE_URL,
    echo=False,
    connect_args=_connect_args,
    pool_pre_ping=not IS_SQLITE,
)

# If PostgreSQL, verify the connection works — otherwise fall back to SQLite
if not IS_SQLITE:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as e:
        logger.warning("PostgreSQL unreachable (%s), falling back to SQLite", e)
        DATABASE_URL = f"sqlite:///{Path(__file__).resolve().parent.parent / 'kpi_agent.db'}"
        IS_SQLITE = True
        engine = create_engine(
            DATABASE_URL,
            echo=False,
            connect_args={"check_same_thread": False},
            pool_pre_ping=False,
        )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency: yields a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
