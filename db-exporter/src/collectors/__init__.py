"""Maps a config.yaml db_type value to its VendorAdapter class."""
from src.collectors.mysql import MysqlAdapter
from src.collectors.oracle import OracleAdapter
from src.collectors.postgres import PostgresAdapter
from src.collectors.sqlserver import SqlServerAdapter

_ADAPTERS = {
    "postgres": PostgresAdapter,
    "mysql": MysqlAdapter,
    "sqlserver": SqlServerAdapter,
    "oracle": OracleAdapter,
}


def get_adapter_class(db_type: str):
    return _ADAPTERS[db_type]
