"""Widening of the OPL motor scan bracket within the motor range (T37, N076)."""
import pytest

from nanofactorysystem.dhm import motorscan
from nanofactorysystem.dhm.motorscan import MotorScanError, bisectAroundMax


class FakeDhm:
    class device:
        MotorMinPos = 0.0
        MotorMaxPos = 10000.0


def bisect_needing_width(width):
    """ Stand-in for bisectMax: finds the maximum only in brackets at least ``width`` wide. """

    brackets = []

    def bisect(dhm, bracket, minc, minm, opt, logger=None):
        brackets.append(bracket)
        if bracket[2] - bracket[0] < width:
            raise MotorScanError("No contrast maximum!")
        return bracket[1]

    return bisect, brackets


def test_bracket_is_widened_until_a_maximum_is_found(monkeypatch):
    bisect, brackets = bisect_needing_width(1500.0)
    monkeypatch.setattr(motorscan, "bisectMax", bisect)

    m = bisectAroundMax(FakeDhm(), (4750.0, 5000.0, 5250.0))

    assert m == 5000.0
    assert brackets == [(4750.0, 5000.0, 5250.0), (4500.0, 5000.0, 5500.0), (4000.0, 5000.0, 6000.0)]


def test_bracket_stays_inside_the_motor_range(monkeypatch):
    bisect, brackets = bisect_needing_width(1e9)
    monkeypatch.setattr(motorscan, "bisectMax", bisect)

    with pytest.raises(MotorScanError, match="exceeds the motor range"):
        bisectAroundMax(FakeDhm(), (400.0, 1000.0, 1600.0))
    # The doubled bracket would start at -200 um, below the motor range, so it is not scanned
    assert brackets == [(400.0, 1000.0, 1600.0)]


def test_no_maximum_with_the_widest_bracket(monkeypatch):
    bisect, brackets = bisect_needing_width(1e9)
    monkeypatch.setattr(motorscan, "bisectMax", bisect)

    with pytest.raises(MotorScanError, match="8 times"):
        bisectAroundMax(FakeDhm(), (4950.0, 5000.0, 5050.0))
    assert len(brackets) == 4
