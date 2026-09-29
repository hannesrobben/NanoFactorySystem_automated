"""Tests for the runtime helpers (runtime.py) and for logging instead of printing."""
import logging

import pytest

from nanofactorysystem.aerobasic.ascii import AerotechAsciiInterface, AerotechError
from nanofactorysystem.backends.dummy import FakeA3200Transport, SimulatedWorld
from nanofactorysystem.runtime import getLogger


@pytest.fixture
def clean_logger():
    logger = logging.getLogger("dummy")
    saved = list(logger.handlers)
    for handler in saved:
        logger.removeHandler(handler)
    yield logger
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()
    for handler in saved:
        logger.addHandler(handler)


def file_handlers(logger):
    return [h for h in logger.handlers if isinstance(h, logging.FileHandler)]


def test_repeated_calls_do_not_duplicate_handlers(clean_logger, tmp_path):
    logger = getLogger()
    getLogger()
    getLogger(logfile=tmp_path / "a.log")
    getLogger(logfile=tmp_path / "a.log")
    getLogger()

    assert len(logger.handlers) == 2
    assert [h.baseFilename for h in file_handlers(logger)] == [str((tmp_path / "a.log").resolve())]


def test_new_logfile_replaces_previous(clean_logger, tmp_path):
    logger = getLogger(logfile=tmp_path / "first.log")
    logger.info("one")
    getLogger(logfile=tmp_path / "second.log")
    logger.info("two")

    assert [h.baseFilename for h in file_handlers(logger)] == [str((tmp_path / "second.log").resolve())]
    assert "two" not in (tmp_path / "first.log").read_text()
    assert "two" in (tmp_path / "second.log").read_text()


def test_messages_are_written_once(clean_logger, tmp_path):
    logger = getLogger(logfile=tmp_path / "log.txt")
    getLogger(logfile=tmp_path / "log.txt")

    logger.info("hello")

    assert (tmp_path / "log.txt").read_text().count("hello") == 1


def test_failed_commands_are_logged_not_printed(capsys, caplog):
    transport = FakeA3200Transport(SimulatedWorld(), strict=True)
    api = AerotechAsciiInterface(transport_factory=lambda: transport)
    api.connect()
    transport.fail_next(r"^LINEAR", error="Axis fault")

    with caplog.at_level(logging.ERROR):
        with pytest.raises(AerotechError):
            api.send("UNKNOWN COMMAND")
        with pytest.raises(AerotechError):
            api.send("LINEAR X1 F1")

    assert capsys.readouterr().out == ""
    assert "INVALID" in caplog.text and "Axis fault" in caplog.text
