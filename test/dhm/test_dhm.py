"""Tests for the DHM client (dhm/dhmclient.py).

Converted: the hardware test used a hardcoded address and only logged
values; it now takes the address from the configuration and asserts the
answers. The dummy test checks the same sequence on the simulated DHM.
"""
import numpy as np
import pytest

from nanofactorysystem.backends.dummy import DummyDhmClient, SimulatedWorld
from nanofactorysystem.config import sysConfig
from nanofactorysystem.dhm import DhmClient

OBJECTIVE_20X = 178


def check_client(client, config_id):
    """ Select the objective configuration and check the basic answers of a DHM client. """

    configs = dict(client.ConfigList)
    assert config_id in configs
    client.Config = config_id
    assert client.Config == config_id

    assert client.MotorMinPos <= client.MotorPos <= client.MotorMaxPos

    shutter = client.CameraShutter
    assert client.CameraMinShutter <= shutter <= client.CameraMaxShutter
    assert client.CameraShutterUs > 0

    img = client.CameraImage
    assert img.ndim == 2 and img.size > 0
    assert img.dtype in (np.uint8, np.uint16)
    assert img.max() > img.min(), "hologram image has no contrast"


def test_dummy_client():
    with DummyDhmClient(SimulatedWorld(seed=0), width=64, height=64) as client:
        check_client(client, OBJECTIVE_20X)


@pytest.mark.hardware
def test_real_client():
    dhm = sysConfig.section("dhm")
    with DhmClient(host=dhm["host"], port=dhm["port"]) as client:
        assert client.ServerVersion >= 3
        check_client(client, OBJECTIVE_20X)
