"""Shared interface every vendor collector module implements.

One VendorAdapter instance per configured database target, holding a warm
connection reused across scrapes (see get_connection()'s liveness check).
"""
import logging
from abc import ABC, abstractmethod
from typing import Any, Callable

from src.config import DatabaseTarget

logger = logging.getLogger(__name__)


class VendorAdapter(ABC):
    def __init__(self, target: DatabaseTarget):
        self.target = target
        self._conn: Any = None

    @abstractmethod
    def connect(self) -> Any:
        """Open a new connection using self.target's fields. Raise on failure."""

    @abstractmethod
    def is_alive(self, conn: Any) -> bool:
        """Cheap liveness check (e.g. SELECT 1). Return False if conn is unusable."""

    @abstractmethod
    def collect(self, conn: Any) -> tuple[list, bool]:
        """Run every query for this vendor. Returns (families, had_error).

        `families` is whatever prometheus_client.core MetricFamily objects
        were successfully built -- callers should implement this using
        safe_collect_family() per query so ONE failing query (e.g. a missing
        grant on a single view) doesn't discard every other metric that DID
        succeed. `had_error` is True if any individual query failed, even if
        others succeeded -- the caller (registry.py) uses it to set
        db_exporter_scrape_error without forcing db_exporter_up to 0 (the
        connection itself is fine; only some queries failed)."""

    def safe_collect_family(self, label: str, builder: Callable[[], Any]) -> tuple[list, bool]:
        """Runs builder() (expected to return one MetricFamily, a list of
        MetricFamily objects, or None), catching any exception so a single
        failing query -- e.g. ORA-00942 from a missing grant on just one
        V$/DBA_ view -- doesn't abort the rest of the scrape.

        Returns (families, had_error): families is [] on failure, so the
        caller can unconditionally `families.extend(...)` the first element
        of the returned tuple regardless of success/failure.
        """
        try:
            result = builder()
        except Exception:
            logger.exception("query '%s' failed for target '%s'", label, self.target.name)
            return [], True
        if result is None:
            return [], False
        if isinstance(result, list):
            return result, False
        return [result], False

    def get_connection(self) -> Any:
        if self._conn is None or not self._safe_is_alive(self._conn):
            self.close()
            self._conn = self.connect()
        return self._conn

    def _safe_is_alive(self, conn: Any) -> bool:
        try:
            return self.is_alive(conn)
        except Exception:
            return False

    def close(self) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None
