"""Loads and validates config.yaml: the list of databases this exporter can scrape."""
import os
import re
from dataclasses import dataclass, field

import yaml

KNOWN_DB_TYPES = {"postgres", "mysql", "sqlserver", "oracle"}
DEFAULT_SCRAPE_TIMEOUT_SECONDS = 10

_ENV_VAR_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


class ConfigError(Exception):
    """Raised for any problem with config.yaml -- callers should fail startup on this."""


@dataclass
class DatabaseTarget:
    name: str
    db_type: str
    host: str
    port: int
    username: str
    password: str
    database: str | None = None
    service_name: str | None = None
    scrape_timeout_seconds: int = DEFAULT_SCRAPE_TIMEOUT_SECONDS


@dataclass
class Config:
    databases: dict[str, DatabaseTarget] = field(default_factory=dict)


def _interpolate_env(value: str) -> str:
    def replace(match: re.Match) -> str:
        var_name = match.group(1)
        if var_name not in os.environ:
            raise ConfigError(
                f"config.yaml references ${{{var_name}}} but that environment "
                f"variable is not set. Set it (e.g. via db-exporter/.env) before starting."
            )
        return os.environ[var_name]

    return _ENV_VAR_PATTERN.sub(replace, value)


def load_config(path: str) -> Config:
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    if not raw or "databases" not in raw:
        raise ConfigError(f"{path} must define a top-level 'databases' list")

    default_timeout = raw.get("scrape_timeout_seconds", DEFAULT_SCRAPE_TIMEOUT_SECONDS)

    databases: dict[str, DatabaseTarget] = {}
    for i, entry in enumerate(raw["databases"]):
        _require_fields(entry, i, ["name", "db_type", "host", "port", "username", "password"])

        name = entry["name"]
        if name in databases:
            raise ConfigError(f"duplicate database name '{name}' in {path} -- names must be unique")

        db_type = entry["db_type"]
        if db_type not in KNOWN_DB_TYPES:
            raise ConfigError(
                f"database '{name}' has unknown db_type '{db_type}' -- "
                f"must be one of {sorted(KNOWN_DB_TYPES)}"
            )

        databases[name] = DatabaseTarget(
            name=name,
            db_type=db_type,
            host=entry["host"],
            port=int(entry["port"]),
            username=entry["username"],
            password=_interpolate_env(str(entry["password"])),
            database=entry.get("database"),
            service_name=entry.get("service_name"),
            scrape_timeout_seconds=int(entry.get("scrape_timeout_seconds", default_timeout)),
        )

    return Config(databases=databases)


def _require_fields(entry: dict, index: int, fields_needed: list[str]) -> None:
    missing = [f for f in fields_needed if f not in entry]
    if missing:
        label = entry.get("name", f"entry #{index}")
        raise ConfigError(f"database '{label}' is missing required field(s): {', '.join(missing)}")
