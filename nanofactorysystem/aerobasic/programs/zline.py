from nanofactorysystem.aerobasic import GalvoLaserOverrideMode, VelocityMode, WaitMode
from nanofactorysystem.aerobasic.programs import AeroBasicProgram


class ZLine(AeroBasicProgram):
    """ Program for an axial line (z-line) exposure of length ``dz`` around the current position. """

    def __init__(self, dz: float, fast_speed: float, slow_speed: float):
        super().__init__()
        self.dz = dz
        dz_half = -dz / 2

        self.comment("Setup")
        self.send("LOOKAHEAD FAST")
        with self.critical_section():
            self.VELOCITY(VelocityMode.ON)
            self.send("RAMP MODE RATE")
            self.send("RAMP RATE 0.00000")
            self.WAIT_MODE(WaitMode.AUTO)
            self.INCREMENTAL()

            self.comment("\nDraw Line")
            self.LINEAR(Z=dz_half, F=fast_speed)
            self.GALVO_LASER_OVERRIDE(GalvoLaserOverrideMode.ON)
            self.LINEAR(Z=dz, F=slow_speed)
            self.GALVO_LASER_OVERRIDE(GalvoLaserOverrideMode.OFF)
            self.LINEAR(Z=dz_half, F=fast_speed)

        self.comment("\nReturn to absolute coordinates")
        self.ABSOLUTE()
