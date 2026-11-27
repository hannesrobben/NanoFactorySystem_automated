"""Lines that switch the laser power in their middle, for the lab check of the power switch (T148, decision D9).

``PowerSwitchLines`` writes one group of lines, ``line_gap_um`` apart, on every z level from ``z_min_um`` to
``z_max_um`` (step ``slice_um``), so every line becomes a small wall. Each line runs along +x from
``-length/2`` to ``+length/2``: the first half with ``power_low_mw``, then the power command ``$AO[0].A=…``
(``SET_POWER``) at x = 0, the second half with ``power_high_mw``. The switch therefore lies at the same place
(x = 0) of every line and every z level.

The first line of the group switches without any pause (``LINEAR`` → ``$AO`` → ``LINEAR``). Each further line
uses one dwell of ``dwells_s``: ``LINEAR`` → ``WAIT MOVEDONE`` → ``$AO`` → ``DWELL`` → ``LINEAR``.

Why the two kinds of line (``docs/design/POWER_SWITCH_CHECK.md`` §2): since A3200 6.01 the controller buffers
motion commands (``LINEAR``, ``RAPID``, ``DWELL``), but not ``$AO``, which can run ahead of the buffered motion.

- On the line without a pause a transition that starts *before* x = 0 shows that ``$AO`` runs ahead of the
  motion; a transition *after* x = 0 shows the settling of the attenuator (length / IFOV speed).
- ``WAIT MOVEDONE`` on the dwell lines holds the program until the first half is written, so the power changes
  at x = 0 and the line stands still for the dwell; the shortest dwell without a transition after x = 0 is the
  settling time.

Before every line the program waits for the previous line to finish (``WAIT MOVEDONE``), sets the low power and
waits ``settle_s`` where the previous motion ended, so every first half starts with a settled low power. Points
written while the line stands still (in a ``DWELL``) are part of what the check shows; nothing is moved away.
``LOOKAHEAD FAST`` is removed from the IFOV header (it has no function since 6.01). With
``GALVO LASEROVERRIDE A AUTO`` it is not documented whether the laser is on while the line stands still in a
``DWELL``; a variant that gates the laser explicitly is a future idea (``future_todo.md``).

Maintainer decisions 2026-11-27: 50 µm lines, 0.25 → 0.75 mW at the middle, z from -1 to +1 µm in 0.2 µm
steps, 5 µm between the lines, one line without pause and four dwell levels, 5-10 repetitions (grid cells of
the lab script). The module changes no existing code (phase-11 rule).
"""
from __future__ import annotations

from typing import Iterator, Optional, Sequence

from nanofactorysystem.aerobasic import SingleAxis
from nanofactorysystem.aerobasic.constants.system import WaitMode
from nanofactorysystem.aerobasic.programs.drawings import DrawableAeroBasicProgram, DrawableObject
from nanofactorysystem.aerobasic.programs.drawings.base import IFOV_AeroBasicProgram
from nanofactorysystem.aerobasic.programs.drawings.lines import set_ifov_speeds
from nanofactorysystem.devices.coordinate_system import CoordinateSystem, Point3D
from nanofactorysystem.devices.power_calibration import PowerCalibration, resolve_power_calibration

__all__ = ["PowerSwitchLines", "DEFAULT_DWELLS_S", "WAIT_AXES"]

#: Dwell levels after the power change (maintainer decision 2026-11-27, about a factor 4-5 apart).
DEFAULT_DWELLS_S = (0.005, 0.02, 0.1, 0.5)
#: Axes ``WAIT MOVEDONE`` waits for: the IFOV axes A/B and the stages X/Y they are paired with.
WAIT_AXES = "X Y A B"
#: Fit kind of the power calibration, the same as ``IFOV_Lines`` uses.
FIT_KIND = "polynomial"


class PowerSwitchLines(DrawableObject):
    """ Lines that switch from a low to a high power at x = 0, without and with dwell, on several z levels (T148).

    Parameters
    ----------
    center : Point3D
        Centre of the pattern (local µm); its z is the reference plane the z levels are relative to.
    power_low_mw, power_high_mw : float
        Power of the first half (-x) and of the second half (+x) of every line.
    dwells_s : sequence of float
        One line per dwell after the line without pause; every value > 0.
    line_length_um : float
        Length of a line; the switch is at its middle.
    line_gap_um : float
        Distance between neighbouring lines in µm.
    z_min_um, z_max_um, slice_um : float
        z levels ``z_min_um, z_min_um + slice_um, …, z_max_um`` relative to ``center.Z`` (z = 0: interface).
    settle_s : float
        Wait after setting the low power before each line, where the previous motion ended (the end of the
        previous line; the centre before the first line).
    velocity : float
        Kept for the time estimate; IFOV writes with the fixed IFOV speed of the objective.
    objective : str
        Objective of the IFOV configuration.
    calibration : PowerCalibration, optional
        Power calibration; default as ``IFOV_Lines`` (the active one, else the one of the configuration).

    Raises
    ------
    ValueError
        For no or a non-positive dwell, a non-positive length, gap or slice, ``z_max_um < z_min_um`` or a
        negative ``settle_s``.
    """

    def __init__(self, center: Point3D, *, power_low_mw: float = 0.25, power_high_mw: float = 0.75,
                 dwells_s: Sequence[float] = DEFAULT_DWELLS_S, line_length_um: float = 50.0,
                 line_gap_um: float = 5.0, z_min_um: float = -1.0, z_max_um: float = 1.0, slice_um: float = 0.2,
                 settle_s: float = 0.5, velocity: float = 5000.0, objective: str = "Zeiss 63x",
                 calibration: Optional[PowerCalibration] = None):
        super().__init__()
        dwells = [float(d) for d in dwells_s]
        if not dwells or min(dwells) <= 0:
            raise ValueError("PowerSwitchLines needs at least one dwell, every dwell > 0")
        if line_length_um <= 0 or line_gap_um <= 0 or slice_um <= 0:
            raise ValueError("line_length_um, line_gap_um and slice_um must be > 0")
        if z_max_um < z_min_um or settle_s < 0:
            raise ValueError("PowerSwitchLines needs z_max_um >= z_min_um and settle_s >= 0")
        self.center = center
        self.power_low_mw = float(power_low_mw)
        self.power_high_mw = float(power_high_mw)
        self.dwells_s = dwells
        self.line_length_um = float(line_length_um)
        self.line_gap_um = float(line_gap_um)
        self.z_min_um = float(z_min_um)
        self.z_max_um = float(z_max_um)
        self.slice_um = float(slice_um)
        self.settle_s = float(settle_s)
        self.velocity = float(velocity)
        self.objective = objective
        self.calibration = calibration

    @property
    def center_point(self) -> Point3D:
        return self.center

    def z_levels_um(self) -> list[float]:
        """ The z levels relative to ``center.Z`` in ascending order, rounded to 1 nm. """

        n = int(round((self.z_max_um - self.z_min_um) / self.slice_um))
        return [round(self.z_min_um + k * self.slice_um, 3) for k in range(n + 1)]

    def line_rows(self) -> list[tuple[float, Optional[float]]]:
        """ The y position (µm, relative to the centre) and dwell (None: no pause) of every line, top to bottom. """

        dwells: list[Optional[float]] = [None, *self.dwells_s]
        top = (len(dwells) - 1) * self.line_gap_um / 2
        return [(round(top - k * self.line_gap_um, 6), dwell) for k, dwell in enumerate(dwells)]

    def _power_value(self, power_mw: float) -> float:
        return float(resolve_power_calibration(self.calibration, FIT_KIND).ptoa(power_mw))

    def _layer(self, coordinate_system: CoordinateSystem, z_um: float) -> DrawableAeroBasicProgram:
        """ One IFOV block that writes every line of the group on one z level. """

        low, high = self._power_value(self.power_low_mw), self._power_value(self.power_high_mw)
        half = self.line_length_um / 2
        program = IFOV_AeroBasicProgram(coordinate_system)
        program.initialise_IFOV_configuration(objective=self.objective)
        program.lines[:] = [line for line in program.lines if line.strip().upper() != "LOOKAHEAD FAST"]
        set_ifov_speeds(program, self.objective)
        program.COMPENSATE_GALVO_ROTATION(axis=SingleAxis.A)
        program.ABSOLUTE()
        program.RAPID(X=self.center.X, Y=self.center.Y, Z=self.center.Z + z_um)
        program.RESET_GALVO()
        program.START_IFOV()
        for y, dwell in self.line_rows():
            kind = "no pause" if dwell is None else f"WAIT MOVEDONE + DWELL {dwell:g} s"
            program.comment(f"\nT148 line at y = {y:.2f} um, z = {z_um:.3f} um: {kind}")
            program.WAIT(WaitMode.MOVE_DONE, WAIT_AXES)
            program.comment(f"Power set to {self.power_low_mw} mW (settled before the line)")
            program.SET_POWER(power=low)
            if self.settle_s > 0:
                program.DWELL(self.settle_s)
            program.RAPID(A=-half, B=y)
            program.LINEAR(A=0.0, B=y)
            if dwell is not None:
                program.WAIT(WaitMode.MOVE_DONE, WAIT_AXES)
            program.comment(f"Power set to {self.power_high_mw} mW (switch at x = 0)")
            program.SET_POWER(power=high)
            if dwell is not None:
                program.DWELL(dwell)
            program.LINEAR(A=half, B=y)
        program.WAIT(WaitMode.MOVE_DONE, WAIT_AXES)
        program.end_ifov_program()
        layer = DrawableAeroBasicProgram(coordinate_system)
        layer.add_programm(program)
        return layer

    def iterate_layers(self, coordinate_system: CoordinateSystem, plot_name=None) -> Iterator[DrawableAeroBasicProgram]:
        """ Yield one layer program per z level in ascending z.

        Parameters
        ----------
        coordinate_system : CoordinateSystem
        plot_name : str, optional
            Unused (``draw_on`` compatibility).

        Yields
        ------
        DrawableAeroBasicProgram
        """

        del plot_name
        for z_um in self.z_levels_um():
            yield self._layer(coordinate_system, z_um)
