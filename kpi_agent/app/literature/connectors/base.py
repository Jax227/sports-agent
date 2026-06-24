"""
Base connector class for literature search sources.

All connectors inherit from BaseConnector and implement:
- search(query, limit, filters) -> list[LiteratureResult]
- get_by_doi(doi) -> LiteratureResult | None
- normalize(raw_record) -> LiteratureResult

Connectors that can't be initialized (missing config, import error) are
marked unavailable rather than crashing.
"""

import time
import logging
from abc import ABC, abstractmethod
from typing import Optional

from app.literature.schema import LiteratureResult

logger = logging.getLogger(__name__)


class ConnectorUnavailable(Exception):
    """Raised when a connector cannot be initialized."""


class BaseConnector(ABC):
    """Abstract base for all literature search connectors."""

    name: str = "base"
    label: str = "Base"
    homepage: str = ""

    def __init__(self):
        self._available: Optional[bool] = None
        self._status_message: str = ""
        self._last_error: Optional[str] = None
        self._last_duration_ms: float = 0

    # ── Subclass interface ────────────────────────────────────────

    @abstractmethod
    def search(
        self, query: str, limit: int = 20, filters: Optional[dict] = None
    ) -> list[LiteratureResult]:
        """Search this source. Must return a list of LiteratureResult (empty on failure)."""
        ...

    def get_by_doi(self, doi: str) -> Optional[LiteratureResult]:
        """Lookup a single DOI. Override if the API supports it efficiently."""
        return None

    @abstractmethod
    def normalize(self, raw_record: dict) -> LiteratureResult:
        """Convert a raw API record into a LiteratureResult."""
        ...

    # ── Lifecycle ──────────────────────────────────────────────────

    @property
    def available(self) -> bool:
        """Check if this connector is available without re-initializing."""
        if self._available is None:
            try:
                self._check_availability()
                self._available = True
            except ConnectorUnavailable as e:
                self._available = False
                self._status_message = str(e)
        return self._available

    @property
    def status(self) -> dict:
        """Return status info for the connector."""
        return {
            "name": self.name,
            "label": self.label,
            "available": self.available,
            "message": self._status_message or ("OK" if self.available else "unavailable"),
            "last_error": self._last_error,
            "last_duration_ms": self._last_duration_ms,
        }

    def _check_availability(self):
        """Override to verify API key / email / network before searching.
        Raise ConnectorUnavailable with a clear message if not usable.
        """
        pass

    # ── Helpers ────────────────────────────────────────────────────

    def _safe_search(
        self, query: str, limit: int, filters: Optional[dict]
    ) -> list[LiteratureResult]:
        """Wrapper that catches errors, records timing, and never crashes."""
        if not self.available:
            return []
        t0 = time.perf_counter()
        try:
            results = self.search(query, limit, filters)
            self._last_duration_ms = (time.perf_counter() - t0) * 1000
            return results
        except Exception as e:
            self._last_duration_ms = (time.perf_counter() - t0) * 1000
            self._last_error = str(e)
            logger.warning(f"[{self.name}] search failed: {e}")
            return []

    @staticmethod
    def _safe_int(val) -> Optional[int]:
        try:
            if val is None:
                return None
            return int(val)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _safe_str(val, default: str = "") -> str:
        if val is None:
            return default
        return str(val)
