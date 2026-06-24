"""
Local SQLite cache for literature search results.

Stores search queries, literature results, retrieval logs, and fulltext links.
Uses the project's existing SQLAlchemy database.

Tables:
- literature_queries: cached search queries
- literature_results: cached normalized results
- literature_retrieval_logs: per-source retrieval logs
- literature_fulltext_links: OA fulltext link records

Cache key = MD5(query + sorted(sources) + sorted(filters))
"""

import hashlib
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class LiteratureCache:
    """SQLite-based cache for literature search results.

    Uses a separate SQLite DB from the main app to avoid table conflicts
    and keep cache management independent.
    """

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            db_path = os.getenv(
                "LITERATURE_DB_PATH",
                str(Path(__file__).resolve().parent.parent.parent / "literature_cache.db"),
            )
        self._db_path = db_path
        self._conn = None
        self._ensure_tables()

    # ── Connection ─────────────────────────────────────────────────

    @property
    def conn(self):
        import sqlite3
        if self._conn is None:
            self._conn = sqlite3.connect(self._db_path)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
        return self._conn

    def _ensure_tables(self):
        c = self.conn
        c.executescript("""
            CREATE TABLE IF NOT EXISTS literature_queries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query_text TEXT NOT NULL,
                sources TEXT NOT NULL,
                filters_json TEXT DEFAULT '{}',
                cache_key TEXT UNIQUE NOT NULL,
                result_count INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS literature_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query_id INTEGER,
                title TEXT,
                authors_json TEXT DEFAULT '[]',
                year INTEGER,
                doi TEXT,
                pmid TEXT,
                pmcid TEXT,
                abstract TEXT,
                journal TEXT,
                source_databases_json TEXT DEFAULT '[]',
                citation_count INTEGER,
                url TEXT,
                pdf_url TEXT,
                fulltext_url TEXT,
                open_access INTEGER,
                publication_type TEXT,
                keywords_json TEXT DEFAULT '[]',
                raw_json TEXT DEFAULT '{}',
                fulltext_available INTEGER DEFAULT 0,
                fulltext_source TEXT,
                oa_license TEXT,
                final_score REAL,
                ranking_explanation TEXT,
                extraction_json TEXT DEFAULT '{}',
                retrieved_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS literature_retrieval_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query_id INTEGER,
                source_database TEXT NOT NULL,
                status TEXT DEFAULT 'ok',
                message TEXT,
                duration_ms REAL,
                result_count INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS literature_fulltext_links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                literature_id INTEGER NOT NULL,
                doi TEXT,
                source TEXT NOT NULL,
                pdf_url TEXT,
                landing_page_url TEXT,
                license TEXT,
                is_oa INTEGER DEFAULT 0,
                checked_at TEXT DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_lr_query_id ON literature_results(query_id);
            CREATE INDEX IF NOT EXISTS idx_lr_doi ON literature_results(doi);
            CREATE INDEX IF NOT EXISTS idx_lr_pmid ON literature_results(pmid);
            CREATE INDEX IF NOT EXISTS idx_lq_cache_key ON literature_queries(cache_key);
        """)
        self.conn.commit()

    # ── Cache key ──────────────────────────────────────────────────

    @staticmethod
    def make_cache_key(query: str, sources: list[str], filters: Optional[dict] = None) -> str:
        """Generate a deterministic cache key."""
        components = [query.strip().lower()]
        components.extend(sorted(sources))
        if filters:
            components.append(json.dumps(filters, sort_keys=True))
        return hashlib.md5("|".join(components).encode()).hexdigest()

    # ── Query cache ────────────────────────────────────────────────

    def get_cached_query(self, cache_key: str) -> Optional[dict]:
        """Get a cached query by cache_key. Returns None if not found."""
        row = self.conn.execute(
            "SELECT * FROM literature_queries WHERE cache_key = ?",
            (cache_key,),
        ).fetchone()
        return dict(row) if row else None

    def save_query(self, query_text: str, sources: list[str], filters: Optional[dict],
                   cache_key: str, result_count: int = 0) -> int:
        """Save a search query and return its id."""
        c = self.conn
        c.execute(
            """INSERT OR REPLACE INTO literature_queries
               (query_text, sources, filters_json, cache_key, result_count, created_at)
               VALUES (?, ?, ?, ?, ?, datetime('now'))""",
            (query_text, json.dumps(sources), json.dumps(filters or {}), cache_key, result_count),
        )
        self.conn.commit()
        return c.execute("SELECT last_insert_rowid()").fetchone()[0]

    # ── Results cache ──────────────────────────────────────────────

    def get_cached_results(self, query_id: int) -> list[dict]:
        """Get cached results for a query."""
        rows = self.conn.execute(
            "SELECT * FROM literature_results WHERE query_id = ? ORDER BY final_score DESC",
            (query_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def save_results(self, query_id: int, results: list) -> int:
        """Save LiteratureResult objects to cache. Returns count saved."""
        from app.literature.schema import LiteratureResult

        c = self.conn
        count = 0
        for r in results:
            if isinstance(r, LiteratureResult):
                d = r.to_dict()
            else:
                d = r

            c.execute(
                """INSERT INTO literature_results
                   (query_id, title, authors_json, year, doi, pmid, pmcid, abstract,
                    journal, source_databases_json, citation_count, url, pdf_url,
                    fulltext_url, open_access, publication_type, keywords_json,
                    raw_json, fulltext_available, fulltext_source, oa_license,
                    final_score, ranking_explanation, retrieved_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    query_id,
                    d.get("title", ""),
                    d.get("authors_json", "[]"),
                    d.get("year"),
                    d.get("doi"),
                    d.get("pmid"),
                    d.get("pmcid"),
                    d.get("abstract"),
                    d.get("journal"),
                    d.get("source_records_json", "[]"),
                    d.get("citation_count"),
                    d.get("url"),
                    d.get("pdf_url"),
                    d.get("fulltext_url"),
                    1 if d.get("open_access") else 0,
                    d.get("publication_type"),
                    d.get("keywords_json", "[]"),
                    d.get("raw_json", "{}"),
                    1 if d.get("fulltext_available") else 0,
                    d.get("fulltext_source"),
                    d.get("oa_license"),
                    d.get("final_score"),
                    d.get("ranking_explanation", ""),
                    d.get("retrieved_at", datetime.utcnow().isoformat()),
                ),
            )
            count += 1
        self.conn.commit()
        return count

    def clear_results(self, query_id: int):
        """Remove cached results for a query."""
        self.conn.execute("DELETE FROM literature_results WHERE query_id = ?", (query_id,))
        self.conn.commit()

    # ── Retrieval logs ─────────────────────────────────────────────

    def log_retrieval(self, query_id: int, source: str, status: str = "ok",
                      message: str = "", duration_ms: float = 0, result_count: int = 0):
        self.conn.execute(
            """INSERT INTO literature_retrieval_logs
               (query_id, source_database, status, message, duration_ms, result_count)
               VALUES (?,?,?,?,?,?)""",
            (query_id, source, status, message, duration_ms, result_count),
        )
        self.conn.commit()

    # ── Fulltext links ─────────────────────────────────────────────

    def save_fulltext_link(self, literature_id: int, doi: str, source: str,
                           pdf_url: str = "", landing_page_url: str = "",
                           license_val: str = "", is_oa: bool = False):
        self.conn.execute(
            """INSERT OR IGNORE INTO literature_fulltext_links
               (literature_id, doi, source, pdf_url, landing_page_url, license, is_oa)
               VALUES (?,?,?,?,?,?,?)""",
            (literature_id, doi, source, pdf_url or "", landing_page_url or "", license_val or "", 1 if is_oa else 0),
        )
        self.conn.commit()

    def get_fulltext_links(self, literature_id: int) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM literature_fulltext_links WHERE literature_id = ?",
            (literature_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None
