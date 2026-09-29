"""Manual laser tests: run on the lab PC and watch whether the laser is visible.

Moved from test/test_femtika: the outcome can only be judged by looking at the laser, so there is
nothing to assert. Run explicitly on the lab PC:
    python -m pytest test/manual/femtika/test_device_WITH_laser.py
"""
import time
import unittest

from nanofactorysystem.aerobasic import Axis, GalvoLaserOverrideMode, SingleAxis
from nanofactorysystem.aerobasic.ascii import AerotechError
from nanofactorysystem.aerobasic.programs import AeroBasicProgram
from nanofactorysystem.devices.aerotech import Aerotech3200


class TestFemtikaWithLaser(unittest.TestCase):
    def setUp(self):
        self.a3200 = Aerotech3200()
        self.api = self.a3200.api
        self.api.connect()

    def tearDown(self):
        self.api.close()
        for cmd in self.api.history:
            print(cmd)

    def test_laser_override_commands_manual(self):
        self.api.GALVO_LASER_OVERRIDE(GalvoLaserOverrideMode.ON)
        time.sleep(5)
        self.api.GALVO_LASER_OVERRIDE(GalvoLaserOverrideMode.OFF)

    def test_laser_override_auto(self):
        self.api.ABSOLUTE()
        self.api.send("ACKNOWLEDGEALL\n")
        self.api.send("IFOV OFF\n")
        self.api.send("GALVO LASERONDELAY A 0\n")
        self.api.send("GALVO LASEROFFDELAY A 0\n")
        # self.api.send("GALVO LASER1PULSEWIDTH A 500000\n")
        # self.api.send("GALVO LASEROUTPUTPERIOD A 500000\n")
        self.api.send("GALVO LASERMODE A 0\n")
        self.api.send("IFOV AXISPAIR 0, A, X")
        self.api.send("IFOV AXISPAIR 1, B, Y")
        self.api.send("ENCODER OUT X ON 0,0")
        self.api.send("ENCODER OUT Y ON 0,0")
        self.api.send("IFOV SYNCAXES Z\n")
        self.api.send("IFOV SIZE 0.50000\n")
        self.api.send("IFOV TIME 10.00000\n")
        self.api.send("IFOV TRACKINGSPEED 500.00000\n")
        self.api.send("IFOV TRACKINGACCEL 500.00000")

        self.api.send("IFOV ON\n")

        # No Laser visible
        self.api.LINEAR(A=-5)
        self.api.LINEAR(A=0)

        # Activate
        self.api.GALVO_LASER_OVERRIDE(GalvoLaserOverrideMode.AUTO)
        time.sleep(1)

        # Laser visible
        self.api.LINEAR(A=5)
