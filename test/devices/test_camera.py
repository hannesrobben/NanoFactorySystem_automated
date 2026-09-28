"""Tests for the camera facade (devices/camera.py).

Converted from a script that optimised the exposure of the real camera and
stored an image container: the dummy test checks the same flow on the
simulated camera; the hardware test checks the real camera.
"""
import numpy as np
import pytest

from nanofactorysystem import Camera
from nanofactorysystem.config import sysConfig


def test_optexpose_and_container(test_config, dummy_backend):
    driver = dummy_backend.camera_driver(None, None)
    with Camera("Test", sysConfig.objective("Zeiss 20x"), driver=driver, camera={"ExposureTime": 10000}) as camera:
        assert camera["ExposureTime"] == 10000

        img, t = camera.optexpose()
        dc = camera.container(loc={"X": 0.0, "Y": 0.0, "Z": 0.0})

    assert abs(img.mean() - 127) < 2
    assert camera["ExposureTime"] == pytest.approx(t)
    assert dc.img.shape == img.shape


@pytest.mark.hardware
def test_real_camera(lab_user):
    objective = sysConfig.objective(sysConfig.objectives()[0])
    with Camera(lab_user, objective, camera={"ExposureTime": 10000}) as camera:
        assert camera.opened
        img, t = camera.optexpose()

    assert img.ndim == 2 and img.dtype == np.uint8
    assert abs(img.mean() - 127) < 10
    assert t > 0
