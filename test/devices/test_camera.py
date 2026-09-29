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


def test_product_and_device_id_select_the_camera(test_config, dummy_backend, monkeypatch):
    import nanofactorysystem.devices.camera as camera_module
    opened = []

    def fake_camera_device(product, device_id):
        opened.append((product, device_id))
        return dummy_backend.camera_driver(product, device_id)

    monkeypatch.setattr(camera_module, "CameraDevice", fake_camera_device)
    camera_args = {"product": "mvBlueFOX3-2032aG", "deviceID": "0", "ExposureTime": 10000}

    camera = Camera("Test", sysConfig.objective("Zeiss 20x"), camera=camera_args)

    assert opened == [("mvBlueFOX3-2032aG", "0")]
    assert camera["ExposureTime"] == 10000
    assert camera_args == {"product": "mvBlueFOX3-2032aG", "deviceID": "0", "ExposureTime": 10000}
