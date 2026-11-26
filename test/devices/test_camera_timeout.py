"""Bounded wait for a camera image (T102): ``image_timeout_ms`` and ``CameraDevice.getimage``."""
import numpy as np
import pytest

from nanofactorysystem.camera.camera import (CameraDevice, MIN_TIMEOUT_MS, TRANSFER_MARGIN_MS,
                                             image_timeout_ms)


def test_timeout_is_twice_the_exposure_in_ms_plus_the_transfer_margin():
    # 20 ms exposure (ExposureTime 20000 µs): 40 ms + margin, not 2000 * 20000 ms (about 11 h) as before T102
    assert image_timeout_ms(20000) == 40 + TRANSFER_MARGIN_MS
    assert image_timeout_ms(500000) == 1000 + TRANSFER_MARGIN_MS
    assert image_timeout_ms(0) >= MIN_TIMEOUT_MS


class _FakeRequest:
    isOK = False

    def unlock(self):
        pass


class _FakeFunctionInterface:
    def __init__(self, valid):
        self.valid = valid
        self.waited_ms = None

    def imageRequestSingle(self):
        pass

    def imageRequestWaitFor(self, timeout_ms):
        self.waited_ms = timeout_ms
        return 7 if self.valid else -2119

    def isRequestNrValid(self, number):
        return number >= 0

    def getRequest(self, number):
        return _FakeRequest()


def _device(valid):
    device = CameraDevice.__new__(CameraDevice)  # no mvIMPACT: only the fields getimage uses
    device._property = {}
    device.fi = _FakeFunctionInterface(valid)
    device.__class__ = type("_Device", (CameraDevice,), {"__getitem__": lambda self, key: 20000.0})
    return device


def test_getimage_waits_a_bounded_time_and_reports_a_missed_frame():
    device = _device(valid=False)

    with pytest.raises(TimeoutError, match="540 ms"):
        device.getimage()

    assert device.fi.waited_ms == image_timeout_ms(20000)


def test_getimage_reports_a_failed_request():
    device = _device(valid=True)

    with pytest.raises(RuntimeError, match="Image grabbing failed"):
        device.getimage()
