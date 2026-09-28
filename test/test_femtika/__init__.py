import tempfile
import time
from unittest import TestCase

from nanofactorysystem.devices.aerotech import Aerotech3200


class FemtikaTest(TestCase):
    """ Base class: tests against the real A3200 controller (127.0.0.1:8000).

    Subclasses running on the real controller must be marked ``hardware``.
    Use :class:`DummyFemtikaMixin` to run the same tests on the simulated
    controller. The previous guard via ``EXECUTE_FEMTIKA_TESTS`` was inverted
    and raised instead of skipping; the ``hardware`` marker replaces it.
    """

    __test__ = False

    def make_controller(self) -> Aerotech3200:
        return Aerotech3200()

    def setUp(self):
        self.a3200 = self.make_controller()
        self.api = self.a3200.api
        self.api.connect()

    def tearDown(self):
        self.api.close()

        print("Commands:")
        for cmd in self.api.history:
            print(cmd)


class DummyFemtikaMixin:
    """ Run a FemtikaTest on the simulated controller of the dummy backend. """

    def make_controller(self) -> Aerotech3200:
        from nanofactorysystem.backends.dummy import FakeA3200Transport, SimulatedWorld
        self.world = SimulatedWorld(seed=0)
        transport = FakeA3200Transport(self.world)
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        # Polling loops sleep; advance the virtual clock instead
        original_sleep = time.sleep
        time.sleep = self.world.clock.sleep
        self.addCleanup(setattr, time, "sleep", original_sleep)
        return Aerotech3200(transport_factory=lambda: transport, program_dir=self._tmp.name)
