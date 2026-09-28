"""Tests for System (system.py).

Converted from a script that opened the real system and stored its
configuration container: the dummy test checks the container content; the
hardware test checks that the real system opens and closes.
"""
import pytest

from nanofactorysystem import System

SAMPLE = {
    "name": "#1",
    "orientation": "top",
    "substrate": "boro-silicate glass",
    "substrateThickness": 700.0,
    "material": "SZ2080",
    "materialThickness": 75.0,
}


def test_system_container(test_config, dummy_backend):
    with System("Test", "Zeiss 20x", backend=dummy_backend, controller={"zMax": 25000.0},
                sample=dict(SAMPLE)) as system:
        dc = system.container()

    assert dc["content.json"]["containerType"]["name"] == "NanoFactory"
    assert dc["data/objective.json"]["key"] == "Zeiss 20x"
    assert dc["data/controller.json"]["zMax"] == 25000.0
    assert dc["data/sample.json"]["sample"]["material"] == "SZ2080"
    assert dc["data/dhm.json"]["device"]["dhm"]["configId"] == 178


def test_home_returns_to_start_position(dummy_system):
    x0, y0, z0 = dummy_system.x0, dummy_system.y0, dummy_system.z0
    dummy_system.moveabs(x=x0 + 100.0, y=y0 - 50.0)

    dummy_system.home(wait=True)

    assert dummy_system.position("XYZ") == pytest.approx([x0, y0, z0])


@pytest.mark.hardware
def test_real_system_opens(lab_user):
    with System(lab_user, "Zeiss 20x", controller={"zMax": 25700.0}, sample=dict(SAMPLE)) as system:
        assert system.opened
        dc = system.container()
        assert dc["data/controller.json"]["zMax"] == 25700.0
    assert not system.opened
