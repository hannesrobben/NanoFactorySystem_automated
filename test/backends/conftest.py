"""Fixtures for the dummy backend tests."""
import pytest

from nanofactorysystem.config import DEFAULT_CONFIG, use_config

TEST_USER = {
    "name": "Test User",
    "email": "test@example.org",
    "organization": "Test Lab",
    "orcid": "0000-0000-0000-0000",
}


@pytest.fixture
def test_config():
    """ Built-in default configuration plus the user ``Test``. """

    with use_config(DEFAULT_CONFIG | {"user:Test": TEST_USER}) as config:
        yield config


@pytest.fixture
def backend(tmp_path):
    """ Dummy backend with seed 0 and its working directory in ``tmp_path``. """

    from nanofactorysystem.backends import DummyBackend
    return DummyBackend(seed=0, workdir=tmp_path / "dummy")
