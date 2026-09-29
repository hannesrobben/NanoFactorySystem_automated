"""Shared pytest configuration and fixtures.

- ``--run-hardware``: run tests marked ``hardware`` (they need the lab PC).
- ``test_config``: built-in default configuration plus the user ``Test``,
  independent of ``~/nanofactory.json``.
- ``dummy_backend``, ``dummy_controller``, ``dummy_system``: simulated
  hardware (see ``nanofactorysystem.backends``).
- ``tmp_program_dir``: directory for generated AeroBasic programs.
- ``lab_user``: first user of the lab configuration, for hardware tests.
- ``--update-golden`` / ``golden``: golden-file comparison of generated programs.
"""
import time
from pathlib import Path

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
    parser.addoption("--update-golden", action="store_true", default=False,
                     help="rewrite the golden reference files in test/golden/ instead of comparing against them")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--run-hardware"):
        return
    skip_hardware = pytest.mark.skip(reason="needs the lab hardware; run with --run-hardware on the lab PC")
    for item in items:
        if "hardware" in item.keywords:
            item.add_marker(skip_hardware)


def dummy_sys_args():
    """ Return runtime arguments for ``System`` on the dummy backend. """

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


GOLDEN_DIR = Path(__file__).parent / "golden"


@pytest.fixture
def golden(request):
    """ Compare generated text with a reference file in ``test/golden/``.

    Returns a function ``check(name, text)``. With ``--update-golden`` the
    reference ``test/golden/<name>.txt`` is (re)written instead, so that
    intended changes can be recorded deliberately. Line endings are
    normalised to ``\\n``.
    """

    update = request.config.getoption("--update-golden")

    def check(name: str, text: str) -> None:
        path = GOLDEN_DIR / f"{name}.txt"
        text = text.replace("\r\n", "\n")
        if update:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8", newline="\n")
            return
        if not path.is_file():
            pytest.fail(f"Golden file {path} is missing; create it with: python -m pytest {request.node.nodeid} "
                        f"--update-golden")
        expected = path.read_text(encoding="utf-8").replace("\r\n", "\n")
        if text != expected:
            import difflib
            diff = "".join(difflib.unified_diff(expected.splitlines(True), text.splitlines(True),
                                                fromfile=f"golden/{name}.txt", tofile="generated", n=2))
            lines = diff.splitlines()
            shown = "\n".join(lines[:60]) + (f"\n... ({len(lines) - 60} more diff lines)" if len(lines) > 60 else "")
            pytest.fail(f"Generated program differs from golden/{name}.txt. If the change is intended, "
                        f"run with --update-golden and review the diff.\n{shown}", pytrace=False)

    return check


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
