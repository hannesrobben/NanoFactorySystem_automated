"""Errors of the protocol v6 client for attributes without a command (T109, finding B19)."""
import pytest

from nanofactorysystem.dhm.dhmclient import DhmClient


def _client():
    return DhmClient.__new__(DhmClient)  # no connection: the errors are raised before any command is sent


def test_writing_a_read_only_attribute_raises_attribute_error():
    with pytest.raises(AttributeError, match="'ServerVersion' is not writeable"):
        _client().ServerVersion = 3


def test_reading_a_write_only_attribute_raises_attribute_error():
    name = next((key for key, (_, read, _) in DhmClient._commands.items() if read is None), None)
    if name is None:
        pytest.skip("no write-only attribute in this protocol version")
    with pytest.raises(AttributeError, match=f"'{name}' is not readable"):
        getattr(_client(), name)
