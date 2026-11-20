##########################################################################
# Copyright (c) 2026 Hannes Robben                                       #
# <hannes.robben@phoenixd.uni-hannover.de>                               #
# This program is free software under the terms of the MIT license.      #
##########################################################################
"""Lab test for T117: why do IFOV rectangles print as a cross ("+") instead of a square?

The chain print on HR-26-002 showed that in IFOV mode the laser exposes only a band of about
20 µm of every 50 µm line. This substrate main prints the same 50 x 50 µm rectangle with four
program variants, one experiment per variant, so that exactly one thing changes at a time:

====  ======================  ==================================================================
Exp.  Variant                 Layer program
====  ======================  ==================================================================
a     ``current``             unchanged ``Rectangle3D_IFOV`` (configuration of 2026-06, laser
                              ``GALVO LASEROVERRIDE A AUTO``): should reproduce the cross
b     ``laser_on_off``        as a, but ``GALVO LASEROVERRIDE A ON`` / ``OFF`` around every line
c     ``config_march``        as a, but the IFOV configuration of the 20x gratings of 2026-03
                              (no ``RAMP RATE 0`` / ``LOOKAHEAD FAST`` / ``CRITICAL START`` /
                              ``IFOV SYNCAXES Z``; ``IFOV SIZE 75``, tracking 10000 / 20000,
                              galvo rotation A and B), laser AUTO
d     ``galvo_only``          no IFOV: galvo A/B with the stage at rest, explicit laser ON/OFF per
                              line, written like the corner markers (which printed correctly)
====  ======================  ==================================================================

Every experiment has a 2 x 2 grid: rows = power (0.25 mW, 0.7 mW), columns = line direction
(lines along x, lines along y). There is no cross hatching, so each rectangle shows directly in
which part of its lines the laser fired. All lines, hatch 0.2 µm, slice 0.25 µm, 5 mm/s, 3 µm
high (1 µm of it in the substrate).

Reading the result: the variant that prints full squares names the cause. Lines along x that
only polymerize in a band of x (and lines along y in a band of y) are the known failure.

Values that depend on the substrate in the lab are marked ``# LAB:``; check them before printing.

Run (with ``mains/`` as working directory)
------------------------------------------
- Check the layout only (no hardware): ``python -m Experiments.ifov_laser_test --layout``
- Dry run on simulated hardware:       ``python -m Experiments.ifov_laser_test --dry-run``
- Lab PC (every step confirmed):       ``python -m Experiments.ifov_laser_test``
"""
import argparse
from pathlib import Path
from typing import Iterator, Optional

from nanofactorysystem.aerobasic.programs.drawings.base import (DrawableAeroBasicProgram, DrawableObject,
                                                                IFOV_AeroBasicProgram)
from nanofactorysystem.aerobasic.programs.drawings.ifov_gratings import Rectangle3D_IFOV
from nanofactorysystem.aerobasic.programs.drawings.lines import (HatchingDirection, IFOV_Lines, PolyLines,
                                                                 ifov_writing_speed_mm_s, set_ifov_speeds)
from nanofactorysystem.devices.coordinate_system import CoordinateSystem, Point2D, Point3D
from nanofactorysystem.experiment import ProgramSource, StructureType
from nanofactorysystem.experiment_spec import ExperimentSpec, StructureSpec, default_sys_args, messagebox_confirm
from nanofactorysystem.plane_fitting import PlaneFitMode
from nanofactorysystem.structure_factories import BuildContext, structure_factory
from nanofactorysystem.substrate_plan import SubstrateExperiment, SubstrateSpec

# ------------------------------------------------------------------------------------------------
# Substrate and placement (absolute stage coordinates in µm)
# ------------------------------------------------------------------------------------------------
USER = "Hannes"
OBJECTIVE = "Zeiss 63x"
# LAB: edges of the resin drop measured with the camera: right, left, near, far
RESIN_EDGES = [[-4900, -2300], [4300, -700], [-800, -5900], [-200, 3600]]
# LAB: centers of the four experiments, side by side along x (checked by check_layout)
CENTERS = {    
    "current": Point2D(0, -1000),
    "laser_on_off": Point2D(1000, -1000),
    "config_march": Point2D(2000, -1000),
    "galvo_only": Point2D(3000, -1000),
}
SUBSTRATE_LABEL: Optional[str] = None                # LAB: e.g. "HR-26-003"; None = next free label
# Message boxes on the lab PC (former ask_continue_box); plots are shown either way
ASK_EACH_STEP = False                                 # confirm plane fit and printing inside every experiment
ASK_BETWEEN = False                                   # confirm before starting the next experiment

# ------------------------------------------------------------------------------------------------
# Test parameters
# ------------------------------------------------------------------------------------------------
VARIANTS = ["current", "laser_on_off", "config_march", "galvo_only"]   # print order (experiments a-d)
POWERS_MW = [0.25, 0.7]                              # rows of the grid
LINE_DIRECTIONS = ["x", "y"]                         # columns of the grid: direction of the written lines
HATCH_UM = 0.2
SLICE_UM = 0.25
SIZE_UM = 50.0
HEIGHT_UM = 3.0                                      # total height incl. the 1 µm in the substrate
SUBSTRATE_OVERLAP_UM = 1.0                           # start z = -1 µm
VELOCITY_MM_S = 5.0                                  # IFOV writing speed of the 63x (fixed)

# HatchingDirection of the drawing classes: Y = continuous lines along x, X = continuous lines along y
_HATCHING = {"x": HatchingDirection.Y, "y": HatchingDirection.X}

# IFOV configuration of the 20x gratings of 2026-03 (git 4522785, IFOV_SIZE_63x = 150 / 2 there)
MARCH_IFOV_SIZE_63X = 75.0
MARCH_TRACKING_SPEED = 10000.0
MARCH_TRACKING_ACCELERATION = 20000.0
MARCH_ROTATION_A = -0.6
MARCH_ROTATION_B = -1.1


def rectangle_lines(size_um: float, hatch_um: float, line_direction: str) -> list[tuple[Point2D, Point2D]]:
    """ Serpentine raster lines of a square, relative to its center (same lines as ``Rectangle2D_IFOV``).

    Parameters
    ----------
    size_um : float
        Edge length.
    hatch_um : float
        Line distance (adjusted so that the first and last line lie on the edges).
    line_direction : {"x", "y"}
        Direction of the written lines.

    Returns
    -------
    list of (Point2D, Point2D)
        Start and end of every line, every other line reversed.
    """

    n_lines = round(size_um / hatch_um) + 1
    step = size_um / (n_lines - 1)
    lines = []
    for i in range(n_lines):
        across = -size_um / 2 + i * step
        if line_direction == "x":  # from the +y edge downwards, as Rectangle2D_IFOV
            start, end = Point2D(-size_um / 2, -across), Point2D(size_um / 2, -across)
        elif line_direction == "y":
            start, end = Point2D(across, -size_um / 2), Point2D(across, size_um / 2)
        else:
            raise ValueError(f"line_direction must be 'x' or 'y', not {line_direction!r}")
        lines.append((start, end) if i % 2 == 0 else (end, start))
    return lines


def layer_heights(height_um: float, slice_um: float) -> list[float]:
    """ z of the layers relative to the bottom (like ``Rectangle3D_IFOV``: round(H / dz) + 1 layers). """

    n_layers = abs(round(height_um / slice_um)) + 1
    return [i * height_um / (n_layers - 1) for i in range(n_layers)]


class IfovLaserTestRectangle(DrawableObject):
    """ Square of the T117 lab test written with one of the variants ``laser_on_off``, ``config_march``
    or ``galvo_only`` (variant ``current`` is the unchanged ``Rectangle3D_IFOV``).

    Parameters
    ----------
    center : Point3D
        Center; ``center.Z`` is the z of the bottom layer. Keep X and Y at 0 (the experiment places it).
    size_um, height_um : float
        Edge length and height.
    hatch_um, slice_um : float
        Line distance and layer height.
    power_mw : float
        Laser power. The IFOV variants set it at the start of every layer program (as ``IFOV_Lines``);
        ``galvo_only`` relies on the power the experiment sets before the structure.
    line_direction : {"x", "y"}
        Direction of the written lines (the same in every layer).
    variant : {"laser_on_off", "config_march", "galvo_only"}
        Program variant (see the module docstring).
    objective : str
        Objective of the IFOV configuration.
    """

    def __init__(self, center: Point3D, size_um: float, height_um: float, *, hatch_um: float, slice_um: float,
                 power_mw: float, line_direction: str, variant: str, objective: str = "Zeiss 63x"):
        super().__init__()
        if variant not in ("laser_on_off", "config_march", "galvo_only"):
            raise ValueError(f"Unknown variant {variant!r}")
        self.center = center
        self.size_um = size_um
        self.height_um = height_um
        self.hatch_um = hatch_um
        self.slice_um = slice_um
        self.power_mw = power_mw
        self.line_direction = line_direction
        self.variant = variant
        self.objective = objective

    @property
    def center_point(self) -> Point3D:
        return self.center

    def iterate_layers(self, coordinate_system: CoordinateSystem) -> Iterator[DrawableAeroBasicProgram]:
        lines = rectangle_lines(self.size_um, self.hatch_um, self.line_direction)
        for z in layer_heights(self.height_um, self.slice_um):
            if self.variant == "galvo_only":
                yield self._galvo_layer(coordinate_system, lines, self.center.Z + z)
            else:
                yield self._ifov_layer(coordinate_system, lines, self.center.Z + z)

    def _galvo_layer(self, coordinate_system, lines, z) -> DrawableAeroBasicProgram:
        """ Galvo only, like ``Corner``: ``LINEAR Z A B F`` with laser ON/OFF around every line. """

        program = DrawableAeroBasicProgram(coordinate_system)
        program.LINEAR(Z=z)
        speed_um_s = ifov_writing_speed_mm_s(self.objective) * 1000
        poly_lines = PolyLines([[{"X": self.center.X + p.X, "Y": self.center.Y + p.Y, "Z": z} for p in line]
                                for line in lines], F=speed_um_s)
        program.add_programm(poly_lines.draw_on(coordinate_system))
        return program

    def _ifov_layer(self, coordinate_system, lines, z) -> IFOV_AeroBasicProgram:
        program = IFOV_AeroBasicProgram(coordinate_system)
        if self.variant == "config_march":
            self._march_configuration(program)
        else:
            program.initialise_IFOV_configuration(objective=self.objective)
        # Power exactly as IFOV_Lines sets it (same calibration and fit)
        power_value = IFOV_Lines(self.center, [], velocity=VELOCITY_MM_S)._get_power_val(self.power_mw)
        program.comment(f"Power set to {self.power_mw} mW")
        program.SET_POWER(power=float(power_value))
        if self.variant == "config_march":
            program.SET_SPEED(F=ifov_writing_speed_mm_s(self.objective))
            program.send(f"GALVO ROTATION A {MARCH_ROTATION_A:f}")
            program.send(f"GALVO ROTATION B {MARCH_ROTATION_B:f}")
        else:
            set_ifov_speeds(program, self.objective)
            program.send(f"GALVO ROTATION A {IFOV_AeroBasicProgram.ROTATION_A:f}")
        program.ABSOLUTE()
        program.RAPID(X=self.center.X, Y=self.center.Y, Z=z)
        program.RESET_GALVO()
        program.START_IFOV()
        for start, end in lines:
            program.RAPID(A=self.center.X + start.X, B=self.center.Y + start.Y)
            if self.variant == "laser_on_off":
                program.send("GALVO LASEROVERRIDE A ON")
            program.LINEAR(A=self.center.X + end.X, B=self.center.Y + end.Y)
            if self.variant == "laser_on_off":
                program.send("GALVO LASEROVERRIDE A OFF")
        if self.variant == "config_march":
            program.END_IFOV()
        else:
            program.end_ifov_program()
        return program

    def _march_configuration(self, program: IFOV_AeroBasicProgram) -> None:
        """ The IFOV header of the 20x gratings of 2026-03, with the 63x IFOV size of that time. """

        program.send("SECONDS")
        program.send("ABSOLUTE")
        program.VELOCITY(IFOV_AeroBasicProgram.VELOCITY_MODE)
        program.send("WAIT MODE AUTO")
        program.send("GALVO LASEROVERRIDE A AUTO")
        program.comment("\nSynchronize axes")
        program.send("IFOV AXISPAIR 0, A, X")
        program.send("IFOV AXISPAIR 1, B, Y")
        program.comment("\nIFOV Settings (configuration of 2026-03)")
        program.send(f"IFOV TIME {IFOV_AeroBasicProgram.IFOV_TIME:f}")
        program.send(f"IFOV SIZE {MARCH_IFOV_SIZE_63X:f}")
        program.send(f"IFOV TRACKINGSPEED {MARCH_TRACKING_SPEED:f}")
        program.send(f"IFOV TRACKINGACCEL {MARCH_TRACKING_ACCELERATION:f}")


# ------------------------------------------------------------------------------------------------
# Structure factory: stored by name and arguments in experiment_spec.json
# ------------------------------------------------------------------------------------------------
@structure_factory("ifov_laser_test.rectangle")
def rectangle(context: BuildContext, *, variant: str, power_mw: float, line_direction: str) -> DrawableObject:
    """ One test square of the given variant.

    Parameters
    ----------
    context : BuildContext
        Values of the running experiment.
    variant : str
        One of ``VARIANTS``.
    power_mw : float
        Laser power.
    line_direction : {"x", "y"}
        Direction of the written lines.

    Returns
    -------
    DrawableObject
        ``Rectangle3D_IFOV`` for ``current``, else :class:`IfovLaserTestRectangle`.
    """

    if context.power_min_mw is not None and context.power_max_mw is not None:
        context.check_power(power_mw)
    center = Point3D(0, 0, -SUBSTRATE_OVERLAP_UM)
    if variant == "current":
        return Rectangle3D_IFOV(center, SIZE_UM, SIZE_UM, HEIGHT_UM, hatch_size=HATCH_UM, slice_size=SLICE_UM,
                                velocity=VELOCITY_MM_S, power=power_mw, alternate_hatching=False,
                                hatching_direction=_HATCHING[line_direction])
    return IfovLaserTestRectangle(center, SIZE_UM, HEIGHT_UM, hatch_um=HATCH_UM, slice_um=SLICE_UM,
                                  power_mw=power_mw, line_direction=line_direction, variant=variant,
                                  objective=context.objective or OBJECTIVE)


def structures(variant: str) -> list[StructureSpec]:
    """ The four squares of one variant: rows = power, columns = line direction. """

    if variant not in VARIANTS:
        raise ValueError(f"Unknown variant {variant!r}")
    # galvo_only is written on the galvo coordinate system like the corners (axes ABZ, no IFOV)
    structure_type, axes = (StructureType.NORMAL, "ABZ") if variant == "galvo_only" else (StructureType.IFOV, "XYZ")
    return [StructureSpec(f"{variant}_p{power:.2f}_lines_{direction}",
                          factory=rectangle(variant=variant, power_mw=power, line_direction=direction),
                          power_mw=power, axes=axes, structure_type=structure_type)
            for power in POWERS_MW for direction in LINE_DIRECTIONS]


def experiment_spec(variant: str, center: Optional[Point2D] = None) -> ExperimentSpec:
    """ One experiment of the test (one variant, 2 x 2 squares).

    Parameters
    ----------
    variant : str
        One of ``VARIANTS``.
    center : Point2D, optional
        Absolute center of the grid; default ``CENTERS[variant]``.

    Returns
    -------
    ExperimentSpec
    """

    letter = "abcd"[VARIANTS.index(variant)]
    sys_args = default_sys_args()
    sys_args["attenuator"]["fitKind"] = "quadratic"
    sys_args["sample"]["name"] = f"ifov_test_{letter}_{variant}"
    sys_args["focus"]["exposureValue"] = 120
    sys_args["layer"]["laserPower"] = 0.7
    return ExperimentSpec(
        name=f"ifov_test_{letter}_{variant}",
        description=f"T117 IFOV laser test, variant {letter} ({variant}): 50 x 50 x 3 µm squares (1 µm in the "
                    f"substrate), lines only along x (left column) or y (right column), power 0.25 / 0.7 mW "
                    f"(rows), hatch {HATCH_UM} µm, slice {SLICE_UM} µm.",
        tags=["T117", "ifov_laser_test", variant],
        objective=OBJECTIVE,
        center=center if center is not None else CENTERS[variant],
        grid=(len(POWERS_MW), len(LINE_DIRECTIONS)),
        structures=structures(variant),
        program_source=ProgramSource.DRAWING,
        setup="IFOV_on",
        default_power_mw=0.7,                           # corner markers and QR code
        plane_fit_mode=PlaneFitMode.CORNERS,
        dhm_usage=False,
        camera_capture=True,                            # camera image after every layer
        overview_capture=True,
        materials={"resin": "SZ2080"},
        sys_args=sys_args,
    )


def substrate_spec(data_root: Optional[Path] = None) -> SubstrateSpec:
    """ The substrate of the test (substrate record version 2). """

    return SubstrateSpec(
        user=USER,
        objective=OBJECTIVE,
        resin_edges=RESIN_EDGES,
        label=SUBSTRATE_LABEL,
        # LAB: substrate and resin of this print
        material={"substrate": "boro-silicate glass", "thickness_um": 170.0, "resin": "SZ2080",
                  "resin_thickness_um": 75.0},
        substrate_type="cover_slip",
        dimensions={"shape": "round", "diameter_mm": 30.0, "thickness_um": 170.0},
        application="drop",
        notes="T117 IFOV laser test: current / laser on-off / March configuration / galvo only "
              "(mains/Experiments/ifov_laser_test.py).",
        data_root=data_root,
    )


def experiments() -> list[SubstrateExperiment]:
    """ The four experiments in print order (a-d). """

    return [SubstrateExperiment(experiment_spec(variant)) for variant in VARIANTS]


def main(*, backend=None, plane=None, data_root: Optional[Path] = None, material_registry=None) -> list[Path]:
    """ Check the layout and print the four experiments; on the lab PC every step is confirmed.

    Parameters
    ----------
    backend : DummyBackend, optional
        None: the lab hardware. A backend object for a dry run (no questions, no plots).
    plane : ZFunction, optional
        Known substrate plane for dry runs.
    data_root : Path, optional
        Data root instead of the user's default location.
    material_registry : MaterialRegistry, optional
        Registry for the material snapshot.

    Returns
    -------
    list of Path
        The experiment folders.
    """

    from nanofactorysystem.substrate_plan import run_substrate
    interactive = backend is None
    return run_substrate(substrate_spec(data_root), experiments(), backend=backend, plane=plane,
                         confirm=messagebox_confirm if interactive and ASK_EACH_STEP else None,
                         confirm_between=messagebox_confirm if interactive and ASK_BETWEEN else None,
                         show_plot=interactive,
                         material_registry=material_registry)


def check(show: bool = True):
    """ Check the layout of the four experiments on the resin drop and plot it, without hardware. """

    from nanofactorysystem.substrate_plan import check_layout, plot_substrate
    substrate = substrate_spec()
    areas = check_layout(substrate, experiments())
    for area in areas:
        print(f"  {area.name:28s} x {area.lower[0]:8.0f} .. {area.upper[0]:8.0f} µm, "
              f"y {area.lower[1]:8.0f} .. {area.upper[1]:8.0f} µm")
    plot_substrate(substrate, areas, show=show)
    return areas


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="run on simulated hardware")
    parser.add_argument("--layout", action="store_true", help="only check and plot the layout")
    options = parser.parse_args()
    if options.layout:
        check()
        print("Layout OK: no overlap, every experiment inside the resin drop.")
    elif options.dry_run:
        import matplotlib
        matplotlib.use("Agg")
        from nanofactorysystem.backends.dummy.dry_run import dry_run
        with dry_run(USER) as simulated:
            folders = main(backend=simulated.backend, plane=simulated.plane, data_root=simulated.workdir / "data")
        print("Dry run finished:", *folders, sep="\n  ")
    else:
        main()
