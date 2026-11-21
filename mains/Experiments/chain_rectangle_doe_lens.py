##########################################################################
# Copyright (c) 2026 Hannes Robben                                       #
# <hannes.robben@phoenixd.uni-hannover.de>                               #
# This program is free software under the terms of the MIT license.      #
##########################################################################
"""Chain of three experiments on one substrate: IFOV rectangle, DOE, aspheric lens (T113).

Every experiment is a 3 x 3 parameter grid of the same structure:

- rows (y): laser power 0.25 / 0.50 / 0.75 mW,
- columns (x): hatch distance 0.2 / 0.4 / 0.6 µm,
- slice distance 0.25 µm everywhere,
- cross hatching: the hatch lines alternate between x and y from layer to layer, with the same
  hatch distance in every layer of a structure (also in the DOE base),
- every structure starts 1 µm inside the substrate (bottom layer at z = -1 µm relative to the
  surface found by the plane fit). The heights below include this 1 µm; the height written above
  the substrate is 5 µm for the rectangle and the lens, 2.5 µm base + up to 2.5 µm DOE levels.

=============  ==================================================================================
Experiment     Structure
=============  ==================================================================================
1 rectangle    ``Rectangle3D_IFOV`` 50 x 50 µm, 6 µm high (z = -1 ... 5 µm)
2 doe          5 x 5 fields of 10 x 10 µm, heights ``DOE_LEVELS`` x 0.5 µm (0 ... 2.5 µm), on a
               50 x 50 µm IFOV base 3.5 µm high (z = -1 ... 2.5 µm; top of the fields up to 5 µm)
3 lens         aspheric lens R = 30 µm, k = 2.3, total sag 6 µm (z = -1 ... 5 µm), aperture
               diameter 31.06 µm (where the sag reaches 6 µm)
=============  ==================================================================================

All three are printed in IFOV mode with the 63x objective (the IFOV writing speed of the
objective is fixed, 5 mm/s). The DOE and the lens are rastered from a height map
(``HeightMap_IFOV``): the DOE map has one pixel per field, the lens map is computed from the
asphere equation on a ``LENS_PIXEL_UM`` grid.

The experiments run one after another on one substrate (``run_substrate``): the layout of all
three is checked against each other and against the resin drop before anything is printed,
then each gets its own folder ``<data root>/<substrate>/<label>-<letter>_<date>/`` with its own
``experiment.h5`` and is entered into the substrate index.

Values that depend on the substrate in the lab are marked ``# LAB:``; check them before printing.

Run (with ``mains/`` as working directory)
------------------------------------------
- Check the layout only (no hardware): ``python -m Experiments.chain_rectangle_doe_lens --layout``
- Dry run on simulated hardware:       ``python -m Experiments.chain_rectangle_doe_lens --dry-run``
- Lab PC (every step confirmed):       ``python -m Experiments.chain_rectangle_doe_lens``
"""
import argparse
import dataclasses
import math
from pathlib import Path
from typing import Optional

import numpy as np

from nanofactorysystem.aerobasic.programs.drawings.height_map import HeightMap_IFOV
from nanofactorysystem.aerobasic.programs.drawings.ifov_gratings import Rectangle3D_IFOV
from nanofactorysystem.aerobasic.programs.drawings.lines import HatchingDirection
from nanofactorysystem.devices.coordinate_system import Point2D, Point3D
from nanofactorysystem.experiment import ProgramSource, StructureType
from nanofactorysystem.experiment_spec import ExperimentSpec, StructureSpec, default_sys_args, messagebox_confirm
from nanofactorysystem.plane_fitting import PlaneFitMode
from nanofactorysystem.structure_factories import BuildContext, structure_factory
from nanofactorysystem.substrate_plan import SubstrateExperiment, SubstrateSpec

# ------------------------------------------------------------------------------------------------
# Substrate and placement (absolute stage coordinates in µm)
# ------------------------------------------------------------------------------------------------
USER = "Hannes"                                      # user key "user:<name>" of ~/nanofactory.json
OBJECTIVE = "Zeiss 63x"                              # the IFOV structures below are set up for 63x
# LAB: edges of the resin drop measured with the camera: right, left, near, far
# RESIN_EDGES = [[5720, 22330], [-3333, 22420], [1660, 17212], [1200, 27190]]
RESIN_EDGES = [[-4900, -2300], [4300, -700], [-800, -5900], [-200, 3600]]
# LAB: centers of the three experiment grids, side by side along x (checked by check_layout)
CENTERS = {
    "rectangle": Point2D(-1600, 0),
    "doe": Point2D(0, 0),
    "lens": Point2D(1600, 0),
}
SUBSTRATE_LABEL: Optional[str] = None                # LAB: e.g. "HR-26-001"; None = next free label
# Unattended run: set all three to False, then nothing waits for a click
ASK_EACH_STEP = True                                 # confirm plane fit and printing inside every experiment
ASK_BETWEEN = True                                   # confirm before starting the next experiment
SHOW_PLOTS = True                                    # layout plot windows (must be closed to continue); False: experiment.png only

# ------------------------------------------------------------------------------------------------
# Parameter grid shared by all three experiments
# ------------------------------------------------------------------------------------------------
POWERS_MW = [0.25, 0.50, 0.75]                       # rows (y direction of the grid)
HATCHES_UM = [0.2, 0.4, 0.6]                         # columns (x direction of the grid)
SLICE_UM = 0.25                                      # slice distance of every structure
SUBSTRATE_OVERLAP_UM = 1.0                           # depth written into the substrate (start z = -1 µm)
IFOV_VELOCITY_MM_S = 5.0                             # kept for the metadata; IFOV writes at the fixed
                                                     # speed of the objective (5 mm/s for 63x)
ALTERNATING_HATCH = True                             # cross hatching: lines along x and along y alternate
                                                     # from layer to layer; the hatch distance of a grid
                                                     # cell applies to every layer (incl. the DOE base)

# Experiment 1: rectangle
RECT_SIZE_UM = 50.0
RECT_HEIGHT_UM = 6.0                                 # total height incl. the 1 µm in the substrate

# Experiment 2: DOE on a base
DOE_FIELD_UM = 10.0                                  # edge length of one DOE field
DOE_STEP_UM = 0.5                                    # height of one level
DOE_BASE_HEIGHT_UM = 3.5                             # base incl. the 1 µm in the substrate
# Heights in levels 0 ... 5 (x DOE_STEP_UM = 0 ... 2.5 µm), drawn once with
# np.random.default_rng(20261120).integers(0, 6, size=(5, 5)) and fixed here, so every print and
# every rebuild uses the same DOE. Row 0 is the +y edge (as the matrix is written here).
DOE_LEVELS = [
    [4, 4, 2, 0, 2],
    [5, 0, 3, 4, 3],
    [2, 2, 0, 5, 3],
    [2, 1, 0, 4, 2],
    [5, 2, 1, 2, 4],
]

# Experiment 3: aspheric lens
LENS_RADIUS_UM = 30.0                                # radius of curvature R
LENS_CONIC = 2.3                                     # conic constant k
LENS_SAG_UM = 6.0                                    # total sag incl. the 1 µm in the substrate
LENS_PIXEL_UM = 0.2                                  # raster of the lens height map


# ------------------------------------------------------------------------------------------------
# Geometry helpers
# ------------------------------------------------------------------------------------------------
def doe_height_map(levels=DOE_LEVELS, step_um: float = DOE_STEP_UM) -> np.ndarray:
    """ Heights of the DOE fields in µm above the base.

    Parameters
    ----------
    levels : sequence of sequence of int
        Level of every field (row 0 = +y edge).
    step_um : float
        Height of one level in µm.

    Returns
    -------
    np.ndarray
        (rows, cols) heights in µm.
    """

    return np.asarray(levels, dtype=float) * float(step_um)


def asphere_sag(r_um, radius_um: float, conic: float) -> np.ndarray:
    """ Sag of a conic surface ``z(r) = r² / (R (1 + sqrt(1 - (1 + k) r² / R²)))`` in µm.

    Parameters
    ----------
    r_um : float or array
        Radial distance from the optical axis in µm.
    radius_um : float
        Radius of curvature R in µm.
    conic : float
        Conic constant k.

    Returns
    -------
    np.ndarray
        Sag in µm; NaN where the conic is not defined (``(1 + k) r² > R²``).
    """

    r2 = np.asarray(r_um, dtype=float) ** 2
    root = 1.0 - (1.0 + conic) * r2 / radius_um ** 2
    with np.errstate(invalid="ignore"):
        return np.where(root >= 0, r2 / (radius_um * (1.0 + np.sqrt(np.clip(root, 0, None)))), np.nan)


def lens_aperture_radius(radius_um: float, conic: float, sag_um: float) -> float:
    """ Radius at which the asphere reaches the given sag: ``r² = 2 R s - (1 + k) s²``.

    Raises
    ------
    ValueError
        If the conic surface does not reach ``sag_um`` (for k > -1 its largest sag is R / (1 + k)).
    """

    if conic > -1 and sag_um > radius_um / (1.0 + conic):
        raise ValueError(f"An asphere with R = {radius_um} µm and k = {conic} reaches at most a sag of "
                         f"{radius_um / (1.0 + conic):.3f} µm, not {sag_um} µm.")
    r2 = 2.0 * radius_um * sag_um - (1.0 + conic) * sag_um ** 2
    if r2 <= 0:
        raise ValueError(f"No aperture for R = {radius_um} µm, k = {conic}, sag = {sag_um} µm.")
    return math.sqrt(r2)


def lens_height_map(radius_um: float = LENS_RADIUS_UM, conic: float = LENS_CONIC, sag_um: float = LENS_SAG_UM,
                    pixel_um: float = LENS_PIXEL_UM) -> np.ndarray:
    """ Height map of a convex aspheric lens: ``sag - z(r)`` inside the aperture, 0 outside.

    The map is square, centered on the optical axis (pixel centers symmetric around 0) and just
    covers the aperture.

    Returns
    -------
    np.ndarray
        (n, n) heights in µm, maximum ``sag_um`` (up to the pixel sampling) on the axis.
    """

    aperture = lens_aperture_radius(radius_um, conic, sag_um)
    n = int(math.ceil(2 * aperture / pixel_um))
    coordinates = (np.arange(n) - (n - 1) / 2) * pixel_um
    x, y = np.meshgrid(coordinates, coordinates)
    r = np.hypot(x, y)
    heights = sag_um - asphere_sag(r, radius_um, conic)
    heights[~(r <= aperture)] = 0.0
    return np.clip(np.nan_to_num(heights, nan=0.0), 0.0, None)


def _check_power(context: BuildContext, power_mw: float) -> None:
    """ Refuse a power outside the attenuator calibration (only when the range is known). """

    if context.power_min_mw is not None and context.power_max_mw is not None:
        context.check_power(power_mw)


# ------------------------------------------------------------------------------------------------
# Structure factories: stored by name and arguments in experiment_spec.json, built when the
# experiment runs (objective and attenuator calibration of the running system)
# ------------------------------------------------------------------------------------------------
@structure_factory("chain_rectangle_doe_lens.rectangle")
def rectangle(context: BuildContext, *, power_mw: float, hatch_um: float) -> Rectangle3D_IFOV:
    """ Experiment 1: IFOV rectangle 50 x 50 µm, 6 µm high, starting 1 µm inside the substrate.

    Parameters
    ----------
    context : BuildContext
        Values of the running experiment.
    power_mw : float
        Laser power, set at the start of every layer.
    hatch_um : float
        Hatch distance.

    Returns
    -------
    Rectangle3D_IFOV
    """

    _check_power(context, power_mw)
    return Rectangle3D_IFOV(Point3D(0, 0, -SUBSTRATE_OVERLAP_UM), RECT_SIZE_UM, RECT_SIZE_UM, RECT_HEIGHT_UM,
                            hatch_size=hatch_um, slice_size=SLICE_UM, velocity=IFOV_VELOCITY_MM_S, power=power_mw,
                            alternate_hatching=ALTERNATING_HATCH, hatching_direction=HatchingDirection.X)


@structure_factory("chain_rectangle_doe_lens.doe")
def doe(context: BuildContext, *, power_mw: float, hatch_um: float, levels: list) -> HeightMap_IFOV:
    """ Experiment 2: DOE of 5 x 5 fields (10 µm) on a 50 x 50 x 3.5 µm IFOV base.

    The base is the socket of the height map (whole map, 3.5 µm incl. the 1 µm in the substrate),
    the fields are rastered on top of it; slice and hatch distance apply to both.

    Parameters
    ----------
    context : BuildContext
        Values of the running experiment.
    power_mw : float
        Laser power.
    hatch_um : float
        Hatch distance (base and fields).
    levels : list of list of int
        DOE levels (``DOE_LEVELS``), stored with the spec.

    Returns
    -------
    HeightMap_IFOV
    """

    _check_power(context, power_mw)
    return HeightMap_IFOV(Point3D(0, 0, -SUBSTRATE_OVERLAP_UM), doe_height_map(levels), DOE_FIELD_UM,
                          DOE_BASE_HEIGHT_UM, slice_size=SLICE_UM, hatch_size=hatch_um,
                          socket_slice_size=SLICE_UM, socket_hatch_size=hatch_um,  # base: same slice and hatch
                          velocity=IFOV_VELOCITY_MM_S, power=power_mw, objective=context.objective or OBJECTIVE,
                          alternating_hatch=ALTERNATING_HATCH)


@structure_factory("chain_rectangle_doe_lens.lens")
def lens(context: BuildContext, *, power_mw: float, hatch_um: float, radius_um: float, conic: float,
         sag_um: float, pixel_um: float) -> HeightMap_IFOV:
    """ Experiment 3: convex aspheric lens, starting 1 µm inside the substrate.

    Parameters
    ----------
    context : BuildContext
        Values of the running experiment.
    power_mw : float
        Laser power.
    hatch_um : float
        Hatch distance.
    radius_um, conic, sag_um : float
        Radius of curvature R, conic constant k and total sag (incl. the 1 µm in the substrate).
    pixel_um : float
        Raster of the height map.

    Returns
    -------
    HeightMap_IFOV
    """

    _check_power(context, power_mw)
    return HeightMap_IFOV(Point3D(0, 0, -SUBSTRATE_OVERLAP_UM), lens_height_map(radius_um, conic, sag_um, pixel_um),
                          pixel_um, 0.0, slice_size=SLICE_UM, hatch_size=hatch_um, velocity=IFOV_VELOCITY_MM_S,
                          power=power_mw, objective=context.objective or OBJECTIVE,
                          alternating_hatch=ALTERNATING_HATCH)


# ------------------------------------------------------------------------------------------------
# Experiment descriptions
# ------------------------------------------------------------------------------------------------
def parameter_grid() -> list[tuple[float, float]]:
    """ (power, hatch) of every grid cell in print order: row by row, one row per power.

    Returns
    -------
    list of (float, float)
    """

    return [(power, hatch) for power in POWERS_MW for hatch in HATCHES_UM]


def structures(kind: str) -> list[StructureSpec]:
    """ The nine structures of one experiment.

    Parameters
    ----------
    kind : {"rectangle", "doe", "lens"}

    Returns
    -------
    list of StructureSpec
    """

    entries = []
    for power, hatch in parameter_grid():
        if kind == "rectangle":
            call = rectangle(power_mw=power, hatch_um=hatch)
        elif kind == "doe":
            call = doe(power_mw=power, hatch_um=hatch, levels=DOE_LEVELS)
        elif kind == "lens":
            call = lens(power_mw=power, hatch_um=hatch, radius_um=LENS_RADIUS_UM, conic=LENS_CONIC,
                        sag_um=LENS_SAG_UM, pixel_um=LENS_PIXEL_UM)
        else:
            raise ValueError(f"Unknown structure kind {kind!r}")
        entries.append(StructureSpec(f"{kind}_p{power:.2f}_h{hatch:.1f}", factory=call, power_mw=power, axes="XYZ",
                                     structure_type=StructureType.IFOV))
    return entries


DESCRIPTIONS = {
    "rectangle": "IFOV rectangle 50 x 50 x 6 µm (1 µm in the substrate); power 0.25/0.5/0.75 mW (rows) x "
                 "hatch 0.2/0.4/0.6 µm (columns), slice 0.25 µm.",
    "doe": "DOE 5 x 5 fields of 10 µm, levels 0-5 x 0.5 µm, on an IFOV base 50 x 50 x 3.5 µm (1 µm in the "
           "substrate); power 0.25/0.5/0.75 mW (rows) x hatch 0.2/0.4/0.6 µm (columns), slice 0.25 µm.",
    "lens": "Aspheric lens R = 30 µm, k = 2.3, total sag 6 µm (1 µm in the substrate), IFOV height map; power "
            "0.25/0.5/0.75 mW (rows) x hatch 0.2/0.4/0.6 µm (columns), slice 0.25 µm.",
}


def experiment_spec(kind: str, center: Optional[Point2D] = None, objective: str = OBJECTIVE) -> ExperimentSpec:
    """ One experiment of the chain.

    Parameters
    ----------
    kind : {"rectangle", "doe", "lens"}
        Which experiment.
    center : Point2D, optional
        Absolute center of the grid; default ``CENTERS[kind]``.
    objective : str
        Only ``"Zeiss 63x"``: ``Rectangle3D_IFOV`` writes with the IFOV configuration of the 63x.

    Returns
    -------
    ExperimentSpec

    Raises
    ------
    ValueError
        For another objective or an unknown kind.
    """

    if objective != "Zeiss 63x":
        raise ValueError(f"The chain is set up for the Zeiss 63x objective, not {objective!r}.")
    sys_args = default_sys_args()
    sys_args["attenuator"]["fitKind"] = "quadratic"
    sys_args["sample"]["name"] = f"chain_{kind}"
    sys_args["focus"]["exposureValue"] = 120
    sys_args["layer"]["laserPower"] = 0.7               # power for the resin interface detection
    return ExperimentSpec(
        name=f"chain_{kind}",
        description=DESCRIPTIONS[kind],
        tags=["chain_rectangle_doe_lens", kind, "power_hatch_grid", "IFOV"],
        objective=objective,
        center=center if center is not None else CENTERS[kind],
        grid=(len(POWERS_MW), len(HATCHES_UM)),         # rows = powers (y), columns = hatches (x)
        structure_size_um=None,                         # grid cell = FOV of the objective (150 µm)
        fov_um=None,
        margin_um=None,
        padding_um=None,
        drop_direction=None,                            # DOWN for 63x
        z_max_um=None,                                  # 25480 µm for 63x
        skip_corner=False,                              # corner markers + QR code for finding it again
        corner=None,
        structures=structures(kind),
        program_source=ProgramSource.DRAWING,
        setup="IFOV_on",
        default_power_mw=0.7,                           # corner markers and QR code
        low_speed_um_s=1000.0,
        high_speed_um_s=5000.0,
        plane_fit_mode=PlaneFitMode.CORNERS,
        n_mid_points=0,
        tilt_warning_um=1.0,
        dhm_usage=False,
        opl_start_um=None,
        camera_capture=True,                            # one camera image after every structure
        overview_capture=True,                          # stitched camera mosaic before and after printing
        overview_single_images=False,
        materials={"resin": "SZ2080"},
        voxel_material=None,
        voxel_database=None,
        layer_overhead_s=5.0,
        sys_args=sys_args,
    )


def substrate_spec(data_root: Optional[Path] = None) -> SubstrateSpec:
    """ The substrate of the chain (substrate record version 2).

    Parameters
    ----------
    data_root : Path, optional
        Data root instead of ``dataRoot`` of the user (dry runs).

    Returns
    -------
    SubstrateSpec
    """

    return SubstrateSpec(
        user=USER,
        objective=OBJECTIVE,
        resin_edges=RESIN_EDGES,
        label=SUBSTRATE_LABEL,
        # LAB: substrate and resin of this print
        material={"substrate": "boro-silicate glass", "thickness_um": 170.0, "resin": "SZ2080",
                  "resin_thickness_um": 75.0},
        substrate_material="",
        substrate_type="cover_slip",
        dimensions={"shape": "round", "diameter_mm": 30.0, "thickness_um": 170.0},
        resin_batch="SZ2080_newBatch_Nov2026",                                 # LAB: batch of the resin bottle
        resin_thickness_um=None,
        application="drop",
        notes="Chain rectangle -> DOE -> aspheric lens, power x hatch grids (mains/Experiments/"
              "chain_rectangle_doe_lens.py).",
        data_root=data_root,
        allow_synced_root=False,
    )


def experiments() -> list[SubstrateExperiment]:
    """ The three experiments in print order. """

    return [SubstrateExperiment(experiment_spec(kind)) for kind in ("rectangle", "doe", "lens")]


def main(*, backend=None, plane=None, data_root: Optional[Path] = None, material_registry=None) -> list[Path]:
    """ Check the layout and print the chain; on the lab PC every step is confirmed in a message box.

    Parameters
    ----------
    backend : DummyBackend, optional
        None: the lab hardware. A backend object for a dry run (no questions, no plots).
    plane : ZFunction, optional
        Known substrate plane for dry runs.
    data_root : Path, optional
        Data root instead of the user's default location.
    material_registry : MaterialRegistry, optional
        Registry for the material snapshot; default: the default database if it exists.

    Returns
    -------
    list of Path
        The three experiment folders.
    """

    from nanofactorysystem.substrate_plan import run_substrate
    interactive = backend is None
    return run_substrate(substrate_spec(data_root), experiments(), backend=backend, plane=plane,
                         confirm=messagebox_confirm if interactive and ASK_EACH_STEP else None,
                         confirm_between=messagebox_confirm if interactive and ASK_BETWEEN else None,
                         show_plot=interactive and SHOW_PLOTS,
                         material_registry=material_registry)


def check(show: bool = True):
    """ Check the layout of the chain on the resin drop and plot it, without hardware.

    Returns
    -------
    list of Area
    """

    from nanofactorysystem.substrate_plan import check_layout, plot_substrate
    substrate = substrate_spec()
    areas = check_layout(substrate, experiments())
    for area in areas:
        print(f"  {area.name:16s} x {area.lower[0]:8.0f} .. {area.upper[0]:8.0f} µm, "
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
        # main()
        main(data_root=Path(r"C:\Users\Nanofactory\Desktop\Hannes\NEW_EXPERIMENTS\TEST_EXP_noDHM"))
