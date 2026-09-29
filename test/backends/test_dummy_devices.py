"""Tests for the simulated camera, DHM and attenuator, run through the real facades."""
import numpy as np
import pytest

from nanofactorysystem.backends import protocols
from nanofactorysystem.backends.dummy import (
    DummyCameraDriver, DummyDhmClient, FakeA3200Transport, SimulatedWorld, write_calibration_file)
from nanofactorysystem.config import sysConfig
from nanofactorysystem.devices import Attenuator, Camera, Dhm


@pytest.fixture
def world():
    return SimulatedWorld(seed=0)


def test_camera_images_are_deterministic(test_config):
    img_a = DummyCameraDriver(SimulatedWorld(seed=3)).getimage()
    img_b = DummyCameraDriver(SimulatedWorld(seed=3)).getimage()
    img_c = DummyCameraDriver(SimulatedWorld(seed=4)).getimage()

    assert img_a.dtype == np.uint8 and img_a.shape == (1024, 1280)
    assert np.array_equal(img_a, img_b)
    assert not np.array_equal(img_a, img_c)


def test_camera_facade_and_exposure_optimisation(test_config, world):
    camera = Camera("Test", sysConfig.objective("Zeiss 20x"), driver=DummyCameraDriver(world, width=64, height=48))

    img, t = camera.optexpose(100)

    assert camera.opened
    assert img.shape == (48, 64)
    assert abs(img.mean() - 100) < 2
    assert t == pytest.approx(20000 * 100 / 127, rel=0.05)
    assert world.calllog.filter(device="camera", call="getimage")


def test_camera_area_of_interest(test_config, world):
    camera = Camera("Test", sysConfig.objective("Zeiss 20x"), driver=DummyCameraDriver(world, width=640, height=480))

    camera.setaoi(100)

    assert camera.getimage().shape == (100, 100)


def test_dhm_facade_selects_objective_and_scans_opl(test_config, world):
    objective = sysConfig.objective("Zeiss 63x")
    driver = DummyDhmClient(world, config_id=objective["dhmId"], width=64, height=64)
    dhm = Dhm("Test", objective, driver=driver, dhm={"oplStep": 100.0})

    m = dhm.motorscan(800.0)

    assert driver.Config == 180
    # The configuration already matched the objective, so it was not switched (no sleep)
    assert all(r.args[0] != "Config" for r in world.calllog.filter(device="dhm", call="set"))
    assert m == pytest.approx(world.opl_optimum, abs=100.0)


def test_dhm_exposure_optimisation(test_config, world):
    driver = DummyDhmClient(world, width=64, height=64)
    dhm = Dhm("Test", sysConfig.objective("Zeiss 20x"), driver=driver)

    img, count = dhm.getimage(opt=True)

    assert img.dtype == np.uint8
    assert np.count_nonzero(img >= 255) <= dhm["maxOverflow"]
    assert count >= 1


def test_attenuator_with_synthetic_calibration(test_config, tmp_path, world):
    path = write_calibration_file(tmp_path / "calibration.dat", world)

    att = Attenuator("Test", attenuator={"calibrationFile": str(path), "fitKind": "quadratic"})

    assert att["powerMax"] == pytest.approx(world.max_power)
    assert float(att.atop(5.0)) == pytest.approx(world.power_of(5.0), rel=1e-6)
    assert float(att.ptoa(world.power_of(7.0))) == pytest.approx(7.0, rel=1e-4)


def test_attenuator_without_calibration_file(test_config):
    with pytest.raises(RuntimeError, match="calibrationFile is not configured"):
        Attenuator("Test", attenuator={})


def test_seam_protocols(world):
    assert isinstance(FakeA3200Transport(world), protocols.ControllerTransport)
    assert isinstance(DummyCameraDriver(world), protocols.CameraDriver)
    assert isinstance(DummyDhmClient(world), protocols.DhmDriver)
