"""Target dispatch: given a target name, run its collector with a timeout,
never let a failure raise past this module, and always produce a
CollectorRegistry containing whatever metrics succeeded plus self-health.
"""
import concurrent.futures
import logging
import time

from prometheus_client import CollectorRegistry
from prometheus_client.core import GaugeMetricFamily

from src.collectors import get_adapter_class
from src.config import Config, DatabaseTarget

logger = logging.getLogger(__name__)


class TargetNotFound(Exception):
    pass


class _StaticCollector:
    """Wraps a pre-built MetricFamily so a CollectorRegistry can serve it."""

    def __init__(self, family):
        self._family = family

    def collect(self):
        yield self._family


class TargetRegistry:
    """Holds one VendorAdapter (and its warm connection) per configured target."""

    def __init__(self, config: Config, max_workers: int = 8):
        self._config = config
        self._adapters: dict[str, object] = {}
        self._last_status: dict[str, tuple[int, int, float]] = {}
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)

    def _get_adapter(self, target: DatabaseTarget):
        if target.name not in self._adapters:
            adapter_cls = get_adapter_class(target.db_type)
            self._adapters[target.name] = adapter_cls(target)
        return self._adapters[target.name]

    def list_targets(self) -> list[DatabaseTarget]:
        """All configured databases, sorted by name, for the / index page."""
        return sorted(self._config.databases.values(), key=lambda t: t.name)

    def scrape(self, target_name: str) -> CollectorRegistry:
        """Returns a CollectorRegistry for this target. Never raises for a
        down/timed-out database -- only for a genuinely unknown target name."""
        if target_name not in self._config.databases:
            raise TargetNotFound(target_name)

        target = self._config.databases[target_name]
        adapter = self._get_adapter(target)

        start = time.monotonic()
        up = 1
        error = 0
        families: list = []

        def _do_scrape():
            # Connect (if needed) and collect must both run inside the worker
            # thread so a hanging connect() is also bounded by the timeout
            # below -- not just the query phase.
            conn = adapter.get_connection()
            return adapter.collect(conn)

        try:
            future = self._executor.submit(_do_scrape)
            families, had_partial_error = future.result(timeout=target.scrape_timeout_seconds)
            if had_partial_error:
                # Connection + collect() itself succeeded, but one or more
                # individual queries failed (see VendorAdapter.collect()'s
                # contract) -- the database IS up, just partially degraded.
                error = 1
        except concurrent.futures.TimeoutError:
            logger.error("scrape of target '%s' timed out after %ss", target_name, target.scrape_timeout_seconds)
            up = 0
            error = 1
        except Exception:
            # Connection itself failed (refused, auth, DNS, etc.) -- nothing
            # could be collected at all.
            logger.exception("scrape of target '%s' failed", target_name)
            up = 0
            error = 1

        duration = time.monotonic() - start
        self._last_status[target_name] = (up, error, duration)

        registry = CollectorRegistry()
        for family in families:
            registry.register(_StaticCollector(family))
        for family in self._self_health_families({target_name: (up, error, duration)}):
            registry.register(_StaticCollector(family))
        return registry

    def scrape_all_self_health(self) -> CollectorRegistry:
        """Bare /metrics (no target): reports each target's LAST known status
        without forcing a fresh scrape of every configured database."""
        registry = CollectorRegistry()
        for family in self._self_health_families(self._last_status):
            registry.register(_StaticCollector(family))
        return registry

    @staticmethod
    def _self_health_families(status_by_target: dict[str, tuple[int, int, float]]):
        up = GaugeMetricFamily("db_exporter_up", "1 if the last scrape of this target succeeded.", labels=["target"])
        error = GaugeMetricFamily("db_exporter_scrape_error", "1 if any query failed during the last scrape.", labels=["target"])
        duration = GaugeMetricFamily("db_exporter_scrape_duration_seconds", "Wall-clock time of the last scrape.", labels=["target"])
        for name, (up_value, error_value, duration_value) in status_by_target.items():
            up.add_metric([name], up_value)
            error.add_metric([name], error_value)
            duration.add_metric([name], duration_value)
        return [up, error, duration]
