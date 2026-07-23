import time

import pytest
from prometheus_client import generate_latest

from src.config import Config, DatabaseTarget
from src.registry import TargetNotFound, TargetRegistry


def _config_with(target: DatabaseTarget) -> Config:
    return Config(databases={target.name: target})


def test_unknown_target_raises_target_not_found():
    config = _config_with(
        DatabaseTarget(name="a", db_type="postgres", host="h", port=1, username="u", password="p")
    )
    registry = TargetRegistry(config)

    with pytest.raises(TargetNotFound):
        registry.scrape("does-not-exist")


def test_connection_failure_reports_up_zero_without_raising(monkeypatch):
    target = DatabaseTarget(name="a", db_type="postgres", host="h", port=1, username="u", password="p")
    config = _config_with(target)
    registry = TargetRegistry(config)

    class ExplodingAdapter:
        def __init__(self, target):
            pass

        def get_connection(self):
            raise ConnectionError("boom")

        def collect(self, conn):
            return []

    monkeypatch.setattr("src.registry.get_adapter_class", lambda db_type: ExplodingAdapter)

    prom_registry = registry.scrape("a")
    text = generate_latest(prom_registry).decode("utf-8")

    assert 'db_exporter_up{target="a"} 0.0' in text
    assert 'db_exporter_scrape_error{target="a"} 1.0' in text


def test_slow_collector_times_out_and_reports_up_zero(monkeypatch):
    target = DatabaseTarget(
        name="a", db_type="postgres", host="h", port=1, username="u", password="p", scrape_timeout_seconds=1
    )
    config = _config_with(target)
    registry = TargetRegistry(config)

    class SlowAdapter:
        def __init__(self, target):
            pass

        def get_connection(self):
            return object()

        def collect(self, conn):
            time.sleep(5)
            return []

    monkeypatch.setattr("src.registry.get_adapter_class", lambda db_type: SlowAdapter)

    prom_registry = registry.scrape("a")
    text = generate_latest(prom_registry).decode("utf-8")

    assert 'db_exporter_up{target="a"} 0.0' in text


def test_successful_scrape_reports_up_one_and_includes_families(monkeypatch):
    from prometheus_client.core import GaugeMetricFamily

    target = DatabaseTarget(name="a", db_type="postgres", host="h", port=1, username="u", password="p")
    config = _config_with(target)
    registry = TargetRegistry(config)

    class HappyAdapter:
        def __init__(self, target):
            pass

        def get_connection(self):
            return object()

        def collect(self, conn):
            family = GaugeMetricFamily("pg_settings_max_connections", "test")
            family.add_metric([], 100)
            return [family], False

    monkeypatch.setattr("src.registry.get_adapter_class", lambda db_type: HappyAdapter)

    prom_registry = registry.scrape("a")
    text = generate_latest(prom_registry).decode("utf-8")

    assert 'db_exporter_up{target="a"} 1.0' in text
    assert 'db_exporter_scrape_error{target="a"} 0.0' in text
    assert "pg_settings_max_connections 100.0" in text


def test_partial_failure_keeps_up_but_sets_error(monkeypatch):
    """A target that connects fine but has one failing query (per
    VendorAdapter.collect()'s (families, had_error) contract) should report
    up=1 (the connection IS fine) with error=1 -- not up=0."""
    from prometheus_client.core import GaugeMetricFamily

    target = DatabaseTarget(name="a", db_type="postgres", host="h", port=1, username="u", password="p")
    config = _config_with(target)
    registry = TargetRegistry(config)

    class PartiallyFailingAdapter:
        def __init__(self, target):
            pass

        def get_connection(self):
            return object()

        def collect(self, conn):
            family = GaugeMetricFamily("pg_settings_max_connections", "test")
            family.add_metric([], 100)
            return [family], True  # one query failed, but this one succeeded

    monkeypatch.setattr("src.registry.get_adapter_class", lambda db_type: PartiallyFailingAdapter)

    prom_registry = registry.scrape("a")
    text = generate_latest(prom_registry).decode("utf-8")

    assert 'db_exporter_up{target="a"} 1.0' in text
    assert 'db_exporter_scrape_error{target="a"} 1.0' in text
    assert "pg_settings_max_connections 100.0" in text


def test_scrape_all_self_health_reflects_last_status(monkeypatch):
    target = DatabaseTarget(name="a", db_type="postgres", host="h", port=1, username="u", password="p")
    config = _config_with(target)
    registry = TargetRegistry(config)

    class ExplodingAdapter:
        def __init__(self, target):
            pass

        def get_connection(self):
            raise ConnectionError("boom")

        def collect(self, conn):
            return []

    monkeypatch.setattr("src.registry.get_adapter_class", lambda db_type: ExplodingAdapter)
    registry.scrape("a")  # populates _last_status

    text = generate_latest(registry.scrape_all_self_health()).decode("utf-8")
    assert 'db_exporter_up{target="a"} 0.0' in text
