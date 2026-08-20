import pytest

from src.collectors.base import VendorAdapter
from src.config import DatabaseTarget

TARGET = DatabaseTarget(name="a", db_type="postgres", host="h", port=1, username="u", password="wrong")


class _CountingAdapter(VendorAdapter):
    """connect() always fails; is_alive() is never exercised by these tests."""

    def __init__(self, target, error_factory, auth_error=True):
        super().__init__(target)
        self.connect_calls = 0
        self._error_factory = error_factory
        self._auth_error = auth_error

    def connect(self):
        self.connect_calls += 1
        raise self._error_factory()

    def is_alive(self, conn) -> bool:
        return True

    def is_auth_error(self, exc: Exception) -> bool:
        return self._auth_error

    def collect(self, conn):
        return [], False


def test_auth_failure_is_not_retried_on_subsequent_scrapes():
    adapter = _CountingAdapter(TARGET, lambda: ConnectionError("bad password"))

    with pytest.raises(ConnectionError):
        adapter.get_connection()
    assert adapter.connect_calls == 1

    # A second (and third) scrape must not hit connect() again -- that's the
    # whole point: retrying every scrape interval against a wrong password
    # risks locking the account out.
    with pytest.raises(RuntimeError):
        adapter.get_connection()
    with pytest.raises(RuntimeError):
        adapter.get_connection()
    assert adapter.connect_calls == 1


def test_non_auth_failure_is_retried_every_scrape():
    """A transient failure (network blip, DB restarting) is NOT an auth
    failure and must keep retrying -- only bad credentials should latch."""
    adapter = _CountingAdapter(TARGET, lambda: ConnectionError("connection refused"), auth_error=False)

    with pytest.raises(ConnectionError):
        adapter.get_connection()
    with pytest.raises(ConnectionError):
        adapter.get_connection()

    assert adapter.connect_calls == 2
    assert adapter._auth_failed is False
