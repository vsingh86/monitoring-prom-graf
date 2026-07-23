"""Minimal DB-API test doubles. Queue one result set per expected execute()
call, in the exact order the collector under test issues them."""


class FakeCursor:
    def __init__(self, results_queue: list):
        self._results_queue = results_queue
        self._current = None

    def execute(self, sql, params=None):
        if not self._results_queue:
            raise AssertionError(f"no queued result left for query:\n{sql}")
        item = self._results_queue.pop(0)
        # Queue an exception instance/class in place of a normal result set
        # to simulate that one query failing (e.g. ORA-00942 from a missing
        # grant) without disturbing the order of the remaining queued results.
        if isinstance(item, BaseException) or (isinstance(item, type) and issubclass(item, BaseException)):
            raise item
        self._current = item

    def fetchall(self):
        return self._current or []

    def fetchone(self):
        rows = self._current or []
        return rows[0] if rows else None

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False


class FakeConnection:
    def __init__(self, results_queue: list):
        self._results_queue = results_queue

    def cursor(self, *args, **kwargs):
        return FakeCursor(self._results_queue)

    def close(self):
        pass


def metric_lines(registry) -> str:
    from prometheus_client import generate_latest

    return generate_latest(registry).decode("utf-8")


def build_registry(families):
    from prometheus_client import CollectorRegistry

    from src.registry import _StaticCollector

    registry = CollectorRegistry()
    for family in families:
        registry.register(_StaticCollector(family))
    return registry
