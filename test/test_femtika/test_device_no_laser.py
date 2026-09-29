"""Controller tests without laser, on the real controller (hardware) and on the dummy controller.

Converted: the tests only printed the controller state; they now assert it.
"""
import datetime
import unittest

import pytest

from nanofactorysystem.aerobasic import SingleAxis, AxisStatusDataItem
from nanofactorysystem.aerobasic.constants import AxisStatus, Version
from nanofactorysystem.aerobasic.constants.tasks import TaskState
from nanofactorysystem.devices.aerotech import Aerotech3200
from nanofactorysystem.devices.aerotech.task import Task
from . import DummyFemtikaMixin, FemtikaTest


class NoLaserTests(FemtikaTest):
    __test__ = False

    def test_system_commands(self):
        version = self.a3200.version
        last_error = self.api.LAST_ERROR()
        system_time = self.a3200.system_time
        print(f"Version {version}, last error {last_error!r}, system time {system_time}")

        self.assertIsInstance(version, Version)
        self.assertTrue(version.major.isdigit())
        self.assertIsInstance(last_error, str)
        self.assertIsInstance(system_time, datetime.datetime)

    def test_get_position(self):
        point = self.a3200.xyz
        print(f"Position: {point}")

        self.assertTrue(all(isinstance(v, float) for v in (point.X, point.Y, point.Z)))

    def test_axis_status(self):
        axis_status = self.a3200.axis_status
        for ax, status in axis_status.items():
            print(f"{ax} -> {status}")

        self.assertEqual(set(axis_status), {SingleAxis.X, SingleAxis.Y, SingleAxis.Z, SingleAxis.A, SingleAxis.B})
        self.assertTrue(all(isinstance(s, AxisStatus) for s in axis_status.values()))

    @unittest.skip("Moves the stage to X=Y=Z=0; only for manual use")
    def test_linear(self):
        self.api.ABSOLUTE()
        self.api.LINEAR(X=0, Y=0, Z=0)
        point = self.a3200.xyz
        self.assertAlmostEqual(0, point.X, places=2)
        self.assertAlmostEqual(0, point.Y, places=2)
        self.assertAlmostEqual(0, point.Z, places=2)

    def test_tasks(self):
        for i in range(Aerotech3200.MAX_NUMBER_OF_TASKS):
            task = Task(self.api, task_id=i)
            print(f"Task {i:02d}: {task.task_state}, {task.task_mode}, line {task.current_line}")
            self.assertIsInstance(task.task_state, TaskState)
            self.assertIsInstance(task.current_line, int)
            task.wait_mode  # must be derivable from the task mode

    def test_get_axis_ramp_rate(self):
        for ax in SingleAxis.__members__.values():
            if not ax.is_single_axis():
                continue
            acceleration_rate = float(
                self.a3200.api.AXISSTATUS(ax, AxisStatusDataItem.AccelerationRate).replace(",", "."))
            print(f"{ax}: {acceleration_rate}")
            self.assertGreater(acceleration_rate, 0)

    def test_move_home(self):
        self.api.LINEAR(X=0, Y=0, Z=0)

        point = self.a3200.xyz
        self.assertAlmostEqual(0, point.X, places=2)
        self.assertAlmostEqual(0, point.Y, places=2)
        self.assertAlmostEqual(0, point.Z, places=2)

    def test_homing(self):
        self.a3200.home()

        point = self.a3200.xyz
        self.assertAlmostEqual(0, point.X, places=2)
        self.assertAlmostEqual(0, point.Y, places=2)


@pytest.mark.hardware
class TestFemtikaNoLaser(NoLaserTests):
    __test__ = True


class TestFemtikaNoLaserDummy(DummyFemtikaMixin, NoLaserTests):
    __test__ = True

    def test_homing_commands(self):
        self.a3200.home()

        self.assertEqual(self.world.calllog.commands()[-4:],
                         ["HOME Y Z A B", "LINEAR Y80.0000000000", "HOME X", "LINEAR Y0.0000000000"])
