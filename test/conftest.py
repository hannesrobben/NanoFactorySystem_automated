"""Shared pytest configuration and fixtures.

- ``--run-hardware``: run tests marked ``hardware`` (they need the lab PC).
- ``test_config``: built-in default configuration plus the user ``Test``,
  independent of ``~/nanofactory.json``.
- ``dummy_backend``, ``dummy_controller``, ``dummy_system``: simulated
  hardware (see ``nanofactorysystem.backends``).
- ``tmp_program_dir``: directory for generated AeroBasic programs.
- ``lab_user``: first user of the lab configuration, for hardware tests.
"""
import time

import pytest

from nanofactorysystem.config import DEFAULT_CONFIG, use_config

TEST_USER_KEY = "Test"
TEST_USER = {
    "name": "Test User",
    "email": "test@example.org",
    "organization": "Test Lab",
    "orcid": "0000-0000-0000-0000",
}


def pytest_addoption(parser):
    parser.addoption("--run-hardware", action="store_true", default=False,
                     help="run tests marked 'hardware', which need the Laser Nanofactory lab hardware")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--run-hardware"):
        return
    skip_hardware = pytest.mark.skip(reason="needs the lab hardware; run with --run-hardware on the lab PC")
    for item in items:
        if "hardware" in item.keywords:
            item.add_marker(skip_hardware)


def dummy_sys_args():
    """ Return fresh runtime arguments for ``System`` on the dummy backend.

    A new dictionary is needed for every ``System``, because the parameter
    classes pop keys from the dictionaries they receive (see T21).
    """

    return {"controller": {"zMax": 25000.0}}


@pytest.fixture
def test_config():
    """ Activate the built-in default configuration plus the user ``Test``.

    Yields
    ------
    Config
        The global ``sysConfig`` with the test configuration.
    """

    with use_config(DEFAULT_CONFIG | {f"user:{TEST_USER_KEY}": TEST_USER}) as config:
        yield config


@pytest.fixture
def lab_user():
    """ First user of the lab configuration (``~/nanofactory.json``), for hardware tests. """

    from nanofactorysystem.config import sysConfig
    users = sysConfig.users()
    if not users:
        pytest.skip("no user in the lab configuration (~/nanofactory.json)")
    return users[0]


@pytest.fixture
def tmp_program_dir(tmp_path):
    """ Empty directory for generated AeroBasic programs. """

    path = tmp_path / "programs"
    path.mkdir()
    return path


@pytest.fixture
def dummy_backend(tmp_path):
    """ Dummy backend with seed 0; its working directory is inside ``tmp_path``. """

    from nanofactorysystem.backends import DummyBackend
    return DummyBackend(seed=0, workdir=tmp_path / "dummy")


@pytest.fixture
def no_sleep(monkeypatch, dummy_backend):
    """ Let ``time.sleep`` advance the virtual clock of the dummy backend instead of waiting. """

    monkeypatch.setattr(time, "sleep", dummy_backend.world.clock.sleep)


@pytest.fixture
def dummy_controller(dummy_backend, tmp_program_dir, no_sleep):
    """ Connected ``Aerotech3200`` on the simulated controller of ``dummy_backend``.

    Program files go to ``tmp_program_dir``; commands are recorded in
    ``dummy_backend.calllog``.
    """

    from nanofactorysystem.devices.aerotech import Aerotech3200
    controller = Aerotech3200(transport_factory=lambda: dummy_backend.transport, program_dir=tmp_program_dir)
    controller.connect()
    yield controller
    controller.close()


@pytest.fixture
def dummy_system(test_config, dummy_backend, no_sleep):
    """ ``System`` for user ``Test`` and objective ``Zeiss 20x`` on ``dummy_backend``.

    The system is closed after the test.
    """

    from nanofactorysystem import System
    with System(TEST_USER_KEY, "Zeiss 20x", backend=dummy_backend, **dummy_sys_args()) as system:
        yield system
