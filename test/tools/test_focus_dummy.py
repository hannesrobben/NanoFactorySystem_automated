"""Smoke test of the focus detection tool on the dummy backend.

The detection itself is not simulated (the dummy camera renders no exposure
spots), so the expected result is "no focus". The test checks that the tool
runs end to end on System and that the z-line exposure reaches the controller.
The measurement scripts for the real system are in test/manual/tools/.
"""
import pytest

from nanofactorysystem import Focus
from nanofactorysystem.tools.focus import focusStatus


def test_focus_run_on_dummy_system(dummy_system, dummy_backend):
    focus = Focus(dummy_system, focus={"shape": (256, 256), "centerRadius": 40})
    x, y, z = dummy_system.x0 + 50.0, dummy_system.y0, dummy_system.z0

    focus.run(x, y, z, 20.0, 0.7, 200.0, 0.2)

    assert focus.result["status"] == focusStatus.nofocus
    exposure, = dummy_backend.world.exposures
    assert exposure.start[:2] == pytest.approx((x / 1000, y / 1000))
    assert exposure.end[2] - exposure.start[2] == pytest.approx(0.02)
    assert exposure.power == pytest.approx(0.7, rel=1e-3)
