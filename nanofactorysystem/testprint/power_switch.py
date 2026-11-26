"""Line pairs with power switches for the lab check of the attenuator settling (T148, decision D9).

``PowerSwitchLines`` writes ``repetitions`` line pairs. Each line consists of ``n_segments`` segments of
``segment_um`` along x whose power alternates between ``power_low_mw`` and ``power_high_mw``; every segment is
its own IFOV block that starts with ``$AO[0].A=…`` (``SET_POWER``), exactly like the blocks of
``ParameterFieldStructure``. The first line of a pair switches without a pause, the second line, ``pair_gap_um``
next to it, is written the same way with ``DWELL dwell_s`` after every power change. Two reference lines at
constant low and high power follow below the pairs.

What the print shows (SEM or camera, width along the line):

- a narrow start of a segment after a switch to the high power (and a wide start after a switch to the low
  power) means the attenuator settles slower than the motion starts: the dwell line next to it shows whether
  ``dwell_s`` is enough;
- a widened *end* of a segment before a switch to the high power means the power command was executed before
  the preceding motion ended (A3200 6.01 and later buffer motion commands, ``$AO`` is not buffered and may run
  ahead of them); then a dwell does not help and the power change needs a synchronised command.

Maintainer decisions 2026-11-26: lines only, line pairs 2 µm apart, 0.25 ↔ 0.75 mW, several dwell levels,
10 repetitions. The module changes no existing code (phase-11 rule).
"""
from __future__ import annotations

from typing import Iterator

from nanofactorysystem.aerobasic.programs import AeroBasicProgram
from nanofactorysystem.aerobasic.programs.drawings import DrawableAeroBasicProgram, DrawableObject
from nanofactorysystem.aerobasic.programs.drawings.lines import IFOV_Lines
from nanofactorysystem.devices.coordinate_system import CoordinateSystem, Point2D, Point3D

__all__ = ["PowerSwitchLines"]


class PowerSwitchLines(DrawableObject):
    """ Line pairs with alternating power segments, without and with a dwell after each power change (T148).

    Parameters
    ----------
    center : Point3D
        Centre of the pattern (local µm); its z is the writing plane relative to the substrate.
    power_low_mw, power_high_mw : float
        The two powers the segments alternate between, starting with the low power.
    dwell_s : float
        Dwell after every power change on the second line of each pair (0 writes both lines alike).
    repetitions : int
        Number of line pairs.
    n_segments : int
        Segments per line (at least 2).
    segment_um : float
        Length of one segment in µm.
    pair_gap_um : float
        Distance of the two lines of a pair in µm.
    pair_pitch_um : float
        Distance of consecutive pairs in µm.
    reference_gap_um : float
        Distance of the two reference lines from the last pair (and from each other) in µm.
    velocity : float
        Kept for the time estimate; IFOV writes with the fixed IFOV speed of the objective.
    objective : str
        Objective of the IFOV configuration.

    Raises
    ------
    ValueError
        For fewer than 2 segments, no repetition or a negative dwell.
    """

    def __init__(self, center: Point3D, *, power_low_mw: float = 0.25, power_high_mw: float = 0.75,
                 dwell_s: float = 0.05, repetitions: int = 10, n_segments: int = 4, segment_um: float = 6.0,
                 pair_gap_um: float = 2.0, pair_pitch_um: float = 6.0, reference_gap_um: float = 4.0,
                 velocity: float = 5000.0, objective: str = "Zeiss 63x"):
        super().__init__()
        if int(n_segments) < 2 or int(repetitions) < 1 or dwell_s < 0:
            raise ValueError("PowerSwitchLines needs n_segments >= 2, repetitions >= 1 and dwell_s >= 0")
        self.center = center
        self.power_low_mw = float(power_low_mw)
        self.power_high_mw = float(power_high_mw)
        self.dwell_s = float(dwell_s)
        self.repetitions = int(repetitions)
        self.n_segments = int(n_segments)
        self.segment_um = float(segment_um)
        self.pair_gap_um = float(pair_gap_um)
        self.pair_pitch_um = float(pair_pitch_um)
        self.reference_gap_um = float(reference_gap_um)
        self.velocity = float(velocity)
        self.objective = objective

    @property
    def center_point(self) -> Point3D:
        return self.center

    @property
    def length_um(self) -> float:
        """ Length of one line in µm. """

        return self.n_segments * self.segment_um

    def line_rows(self) -> list[tuple[float, str]]:
        """ The y position (µm, relative to the centre) and kind of every line: ``"switch"``, ``"dwell"``,
        ``"reference_low"``, ``"reference_high"``; from top to bottom. """

        height = (self.repetitions - 1) * self.pair_pitch_um + self.pair_gap_um + 2 * self.reference_gap_um
        top = height / 2
        rows = []
        for r in range(self.repetitions):
            y = top - r * self.pair_pitch_um
            rows += [(y, "switch"), (y - self.pair_gap_um, "dwell")]
        last = top - (self.repetitions - 1) * self.pair_pitch_um - self.pair_gap_um
        rows += [(last - self.reference_gap_um, "reference_low"), (last - 2 * self.reference_gap_um, "reference_high")]
        return rows

    def _segments(self, y: float, kind: str) -> list[tuple[float, list[list[Point2D]]]]:
        """ (power, [line]) per block of one line, in writing order (+x). """

        x0 = -self.length_um / 2
        if kind == "reference_low":
            return [(self.power_low_mw, [[Point2D(x0, y), Point2D(-x0, y)]])]
        if kind == "reference_high":
            return [(self.power_high_mw, [[Point2D(x0, y), Point2D(-x0, y)]])]
        blocks = []
        for k in range(self.n_segments):
            power = self.power_low_mw if k % 2 == 0 else self.power_high_mw
            start, end = x0 + k * self.segment_um, x0 + (k + 1) * self.segment_um
            blocks.append((power, [[Point2D(start, y), Point2D(end, y)]]))
        return blocks

    def _block(self, coordinate_system: CoordinateSystem, power: float, lines: list,
               dwell: bool) -> DrawableAeroBasicProgram:
        leaf = IFOV_Lines(reference_point=Point3D(self.center.X, self.center.Y, self.center.Z), lines=lines,
                          velocity=self.velocity, power=power)
        program = DrawableAeroBasicProgram(coordinate_system)
        for sub_program in leaf.iterate_layers(coordinate_system, objective=self.objective):
            program.add_programm(sub_program)
        if dwell and self.dwell_s > 0:
            pause = AeroBasicProgram()
            pause.DWELL(self.dwell_s)
            for index, line in enumerate(program.lines):
                if line.startswith("$AO[0].A="):
                    program.lines[index + 1:index + 1] = ["' Dwell after the power change (T148)", *pause.lines]
                    break
        return program

    def iterate_layers(self, coordinate_system: CoordinateSystem, plot_name=None) -> Iterator[DrawableAeroBasicProgram]:
        """ Yield one layer program with every line (one IFOV block per segment).

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
        program = DrawableAeroBasicProgram(coordinate_system)
        for y, kind in self.line_rows():
            program.comment(f"\nT148 {kind} line at y = {y:.2f} um")
            for power, lines in self._segments(y, kind):
                program.add_programm(self._block(coordinate_system, power, lines, dwell=kind == "dwell"))
        yield program
