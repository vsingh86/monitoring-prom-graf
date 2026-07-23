import os

import pytest

from src.config import ConfigError, load_config

VALID_YAML = """
scrape_timeout_seconds: 10
databases:
  - name: authapi-postgres
    db_type: postgres
    host: pg-host
    port: 5432
    database: authapi
    username: authapi_ro
    password: ${TEST_PG_PASSWORD}
"""


def test_loads_valid_config(tmp_path, monkeypatch):
    monkeypatch.setenv("TEST_PG_PASSWORD", "secret123")
    config_file = tmp_path / "config.yaml"
    config_file.write_text(VALID_YAML)

    config = load_config(str(config_file))

    assert set(config.databases) == {"authapi-postgres"}
    target = config.databases["authapi-postgres"]
    assert target.db_type == "postgres"
    assert target.host == "pg-host"
    assert target.port == 5432
    assert target.password == "secret123"
    assert target.scrape_timeout_seconds == 10


def test_missing_env_var_fails_startup(tmp_path, monkeypatch):
    monkeypatch.delenv("TEST_PG_PASSWORD", raising=False)
    config_file = tmp_path / "config.yaml"
    config_file.write_text(VALID_YAML)

    with pytest.raises(ConfigError, match="TEST_PG_PASSWORD"):
        load_config(str(config_file))


def test_duplicate_name_rejected(tmp_path, monkeypatch):
    monkeypatch.setenv("TEST_PG_PASSWORD", "secret123")
    duplicate_yaml = VALID_YAML + VALID_YAML.replace("scrape_timeout_seconds: 10\ndatabases:\n", "")
    config_file = tmp_path / "config.yaml"
    config_file.write_text(duplicate_yaml)

    with pytest.raises(ConfigError, match="duplicate"):
        load_config(str(config_file))


def test_unknown_db_type_rejected(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        """
databases:
  - name: weird-db
    db_type: mongodb
    host: h
    port: 1
    username: u
    password: p
"""
    )

    with pytest.raises(ConfigError, match="unknown db_type"):
        load_config(str(config_file))


def test_missing_required_field_rejected(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        """
databases:
  - name: incomplete-db
    db_type: postgres
    host: h
"""
    )

    with pytest.raises(ConfigError, match="missing required field"):
        load_config(str(config_file))


def test_per_target_scrape_timeout_override(tmp_path, monkeypatch):
    monkeypatch.setenv("TEST_PG_PASSWORD", "secret123")
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        VALID_YAML.replace("username: authapi_ro", "username: authapi_ro\n    scrape_timeout_seconds: 30")
    )

    config = load_config(str(config_file))

    assert config.databases["authapi-postgres"].scrape_timeout_seconds == 30
