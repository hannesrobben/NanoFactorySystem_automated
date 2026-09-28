"""Tests for the laser attenuator calibration (devices/attenuator.py).

Converted from a script that printed and plotted the lab calibration file:
the dummy test checks the conversion on a synthetic calibration; the
hardware test checks the real calibration file on the lab PC.
"""
import numpy as np
import pytest

from nanofactorysystem import Attenuator


@pytest.mark.parametrize("fit_kind", ["quadratic", "cubic"])
def test_conversion_is_consistent(test_config, dummy_backend, fit_kind):
    args = dummy_backend.attenuator_args() | {"fitKind": fit_kind}
    att = Attenuator("Test", attenuator=args)

    values = np.linspace(0.5, 9.5, 10)
    powers = np.array([float(att.atop(v)) for v in values])

    assert att.data.shape == (101, 2)
    assert np.all(np.diff(powers) > 0)
    assert [float(att.ptoa(p)) for p in powers] == pytest.approx(values, abs=0.05)
    assert att["powerMin"] == 0.0
    assert att["powerMax"] == pytest.approx(dummy_backend.world.max_power)


def test_polynomial_fit(test_config, dummy_backend):
    """ The polynomial fit does not pass through the data points (see Attenuator); only check its setup. """

    att = Attenuator("Test", attenuator=dummy_backend.attenuator_args() | {"fitKind": "poly"})

    assert att["polynomialOrder"] == 2
    assert float(att.atop(10.0)) == pytest.approx(dummy_backend.world.max_power, rel=0.05)


def test_container(test_config, dummy_backend):
    att = Attenuator("Test", attenuator=dummy_backend.attenuator_args())

    dc = att.container()

    assert len(dc["meas/calibration.json"]["calibration"]) == 101


@pytest.mark.hardware
def test_real_calibration_file(lab_user):
    att = Attenuator(lab_user, attenuator={"fitKind": "quadratic"})

    a, p = att.data[:, 0], att.data[:, 1]
    assert a[0] == 0.0 and a[-1] == 10.0
    assert np.all(np.diff(a) > 0)
    assert np.all(np.diff(p) >= 0), "laser power must not decrease with the attenuator value"
    assert att["powerMax"] > att["powerMin"] >= 0.0
