##########################################################################
# Copyright (c) 2026 Hannes Robben                                       #
# <hannes.robben@phoenixd.uni-hannover.de>                               #
# This program is free software under the terms of the MIT license.      #
##########################################################################
"""Print a height map from a 16-bit grayscale PNG in IFOV mode (one structure, on a socket).

Only the image block below has to be filled in: where the PNG is, how large one pixel is and how
many µm one gray value step is. Everything else has a working default:

- user, objective, resin drop and substrate data come from the SETTINGS block of ``main.py``
  (the same values as every other task);
- with ``SUBSTRATE_LABEL`` the experiment goes into that substrate below ``dataRoot`` (created if
  new, overlap with earlier experiments checked, ``substrate_layout.json``/``.png`` updated);
  with ``SUBSTRATE_LABEL = None`` into ``OUTPUT_ROOT`` of ``main.py``;
- the structure is placed in the center of the resin drop (``CENTER = None``);
- the experiment is named ``png_<file name>``.

Run with ``mains/`` as working directory::

    cd mains
    python main_PNG.py                 # statistics + preview, then the experiment (see ASK_EACH_STEP, SHOW_PLOTS)
    python main_PNG.py --preview       # only statistics and preview, no hardware
    python main_PNG.py --dry-run       # whole experiment on simulated hardware (temporary folder)

Height convention: gray value ``GRAY_OFFSET`` (default 0) is the top of the socket, every gray
step adds ``HEIGHT_PER_GRAY_UM``. Image row 0 is printed at +y, as shown in an image viewer.
The PNG is stored in the experiment by its path and SHA-256 (do not change the file afterwards,
a restart refuses a changed file).
"""

import argparse
import dataclasses
import datetime
import sys
from pathlib import Path
from typing import Optional

# main.py lies next to this file; make it importable however the script is started
# (from another working directory, the VS Code run button, an interactive window, ...)
sys.path.insert(0, str(Path(__file__).resolve().parent))

import main as settings  # noqa: E402
from nanofactorysystem.aerobasic.programs.drawings.height_map import HeightMap_IFOV
from nanofactorysystem.aerobasic.programs.drawings.lines import HatchingDirection
from nanofactorysystem.devices.coordinate_system import Point2D, Point3D
from nanofactorysystem.experiment import StructureType
from nanofactorysystem.experiment_spec import (
    ExperimentSpec,
    StructureSpec,
    messagebox_confirm,
)
from nanofactorysystem.plane_fitting import PlaneFitMode
from nanofactorysystem.resin_drop import ellipse_through

# =================================================================================================
# IMAGE: the only values you have to set
# =================================================================================================
PNG = Path(
    r"C:\Users\Nanofactory\Desktop\Hannes\REAL-TIME ARCHITECTURE\DOE Print\surface_16bit.png"
)  # 16-bit grayscale PNG
PIXEL_SIZE_UM = (
    0.25  # size of one pixel in µm; (x, y) for non-square pixels, e.g. (0.5, 1.0)
)
HEIGHT_PER_GRAY_UM = 0.0001  # µm per gray value step (16 bit: 65535 steps)
GRAY_OFFSET = 0  # gray value of height 0 (top of the socket); darker pixels count as 0

# =================================================================================================
# Printing: defaults that usually stay as they are
# =================================================================================================
POWER_MW = 0.3  # laser power
SLICE_UM = 0.1  # layer height of the structure
HATCH_UM: Optional[float] = None  # line distance; None: the pixel size
SOCKET_HEIGHT_UM = (
    3.0  # socket under the whole image (incl. SUBSTRATE_DEPTH_UM); 0: none
)
SOCKET_SLICE_UM: Optional[float] = 0.25  # None: SLICE_UM
SOCKET_HATCH_UM: Optional[float] = 0.25  # None: HATCH_UM
SUBSTRATE_DEPTH_UM = 1.0  # the socket starts this far inside the substrate (adhesion)
ADAPTIVE_SLICING = (
    False  # True: every distinct height of the image is hit exactly (multi-level DOEs)
)
ALTERNATING_HATCH = True  # turn the raster lines by 90° from layer to layer
CENTER: Optional[Point2D] = (
    500, -25000  # absolute stage position (µm); None: center of the resin drop
)
CAMERA_CAPTURE = True  # camera image after every layer
OVERVIEW_CAPTURE = False  # stitched camera mosaic of the area before and after printing
MARGIN_AROUND_UM = 100.0  # free space around the image inside the experiment area
# Unattended run: set both to False, then nothing waits for a click
ASK_EACH_STEP = False  # message boxes before plane fit and printing
SHOW_PLOTS = (
    False  # preview and layout windows (must be closed to continue); False: none,
)
# experiment.png is written into the folder anyway
SUBSTRATE_LABEL: Optional[str] = "DOE_circle_V1"
# Substrate (folder below dataRoot of the user in ~/nanofactory.json) the experiment is entered
# into: created if new, otherwise the experiment is added and checked for overlap with the
# experiments already on it; substrate_layout.json/.png are updated.
# None: a single experiment in OUTPUT_ROOT of main.py (no substrate index, no layout files).


def structure() -> HeightMap_IFOV:
    """The height map structure built from the IMAGE and printing settings.

    Returns
    -------
    HeightMap_IFOV
    """

    return HeightMap_IFOV.from_png(
        PNG,
        PIXEL_SIZE_UM,
        HEIGHT_PER_GRAY_UM,
        socket_height=SOCKET_HEIGHT_UM,
        center=Point3D(0, 0, -SUBSTRATE_DEPTH_UM),
        gray_offset=GRAY_OFFSET,
        slice_size=SLICE_UM,
        hatch_size=HATCH_UM,
        socket_slice_size=SOCKET_SLICE_UM,
        socket_hatch_size=SOCKET_HATCH_UM,
        adaptive_slicing=ADAPTIVE_SLICING,
        power=POWER_MW,
        objective=settings.OBJECTIVE,
        hatching_direction=HatchingDirection.Y,
        alternating_hatch=ALTERNATING_HATCH,
    )


def experiment_center() -> Point2D:
    """``CENTER``, or the center of the resin drop of ``main.RESIN_EDGES``."""

    if CENTER is not None:
        return CENTER
    drop = ellipse_through(settings.RESIN_EDGES)
    return Point2D(round(drop.cx), round(drop.cy))


def experiment_spec(height_map: HeightMap_IFOV) -> ExperimentSpec:
    """One IFOV experiment with the height map as its only structure.

    Parameters
    ----------
    height_map : HeightMap_IFOV
        The structure (see :func:`structure`).

    Returns
    -------
    ExperimentSpec
    """

    width, length, height = (
        height_map.width,
        height_map.length,
        height_map.structure_height,
    )
    return ExperimentSpec(
        name=f"png_{PNG.stem}",
        objective=settings.OBJECTIVE,
        center=experiment_center(),
        grid=(1, 1),
        structure_size_um=max(width, length) + MARGIN_AROUND_UM,
        setup="IFOV_on",
        plane_fit_mode=PlaneFitMode.CORNERS,
        dhm_usage=False,
        camera_capture=CAMERA_CAPTURE,
        overview_capture=OVERVIEW_CAPTURE,
        default_power_mw=POWER_MW,
        description=f"Height map {PNG.name}: {height_map.n_cols} x {height_map.n_rows} px of "
        f"{height_map.pixel_pitch[0]} x {height_map.pixel_pitch[1]} µm, {HEIGHT_PER_GRAY_UM} µm per "
        f"gray value, {width:.1f} x {length:.1f} x {height:.2f} µm incl. socket",
        tags=["height_map", "png", "ifov"],
        structures=[
            StructureSpec(
                PNG.stem,
                height_map,
                structure_type=StructureType.IFOV,
                axes="XYZ",
                power_mw=POWER_MW,
            )
        ],
    )


def preview(height_map: HeightMap_IFOV, show: bool = True) -> dict:
    """Print size, layers, lines and writing time; optionally show the height map and three layer masks.

    Parameters
    ----------
    height_map : HeightMap_IFOV
        The structure.
    show : bool
        Show the plot window.

    Returns
    -------
    dict
        ``HeightMap_IFOV.statistics()``.
    """

    stats = height_map.statistics()
    width, length, height = stats["size_um"]
    print(
        f"{PNG.name}: {height_map.n_cols} x {height_map.n_rows} px, max gray height {height_map.max_height:.3f} µm"
    )
    print(
        f"Structure {width:.1f} x {length:.1f} µm, {height:.2f} µm high incl. socket "
        f"({SUBSTRATE_DEPTH_UM} µm of it inside the substrate), center {experiment_center()}"
    )
    print(
        f"{stats['layers']} layers ({stats['socket_layers']} socket), {stats['lines']} lines "
        f"(max {stats['max_lines_per_layer']} per layer), {stats['length_mm'] / 1000:.2f} m, "
        f"about {stats['writing_time_min']:.0f} min writing (without jumps and layer overhead)"
    )
    if show:
        import matplotlib.pyplot as plt

        structure_layers = [
            (z, mask) for kind, z, mask in height_map.layers() if kind == "structure"
        ]
        picks = structure_layers[:: max(1, len(structure_layers) // 3)][:3]
        extent = [-width / 2, width / 2, -length / 2, length / 2]
        fig, axes = plt.subplots(
            1, 1 + len(picks), figsize=(4 * (1 + len(picks)), 4), squeeze=False
        )
        axes = axes[0]
        image = axes[0].imshow(height_map.height_map, extent=extent, origin="upper")
        axes[0].set_title("height above socket / µm")
        fig.colorbar(image, ax=axes[0])
        for ax, (z, mask) in zip(axes[1:], picks):
            ax.imshow(mask, extent=extent, origin="upper", cmap="gray")
            ax.set_title(f"layer z = {z:.2f} µm")
        plt.tight_layout()
        plt.show()
    return stats


def execute(spec: ExperimentSpec, session) -> Path:
    """Run the experiment on the substrate ``SUBSTRATE_LABEL``, or alone in ``OUTPUT_ROOT``.

    With a substrate label, the substrate of ``main.substrate_spec()`` (material, type,
    resin drop) is used under that label: created if new, and the experiment area is checked
    against the experiments already on it before anything is printed
    (``substrate_plan.run_substrate``).

    Parameters
    ----------
    spec : ExperimentSpec
        The experiment (see :func:`experiment_spec`).
    session : main.Session
        Backend, plane, confirmation, plots, data root and material registry.

    Returns
    -------
    Path
        The experiment folder.
    """

    if SUBSTRATE_LABEL is None:
        return session.run(spec)
    from nanofactorysystem.substrate_plan import SubstrateExperiment, run_substrate

    substrate = dataclasses.replace(settings.substrate_spec(), label=SUBSTRATE_LABEL)
    if session.data_root is not None:
        substrate = dataclasses.replace(substrate, data_root=session.data_root)
    [folder] = run_substrate(
        substrate,
        [SubstrateExperiment(spec)],
        backend=session.backend,
        plane=session.plane,
        confirm=session.confirm,
        show_plot=session.show_plot,
        material_registry=session.material_registry,
    )
    session.last_experiment = Path(folder)
    return session.last_experiment


def run(
    *, dry: bool = False, preview_only: bool = False, workdir: Optional[Path] = None
):
    """Preview the height map and run the experiment.

    Parameters
    ----------
    dry : bool
        Simulated hardware; output in ``workdir`` (default: a temporary folder).
    preview_only : bool
        Stop after the preview (no hardware).
    workdir : Path, optional
        Folder of a dry run.

    Returns
    -------
    Path or dict
        The experiment folder, or the statistics with ``preview_only``.
    """

    if dry:
        import matplotlib

        matplotlib.use("Agg")  # no plot windows in a dry run
    height_map = structure()
    stats = preview(height_map, show=SHOW_PLOTS and not dry)
    if preview_only:
        return stats
    spec = experiment_spec(height_map)
    if not dry:
        return execute(
            spec,
            settings.Session(
                confirm=messagebox_confirm if ASK_EACH_STEP else None,
                show_plot=SHOW_PLOTS,
            ),
        )

    from nanofactorysystem.backends.dummy.dry_run import dry_run

    with dry_run(settings.USER, workdir=workdir) as simulated:
        session = settings.Session(
            backend=simulated.backend,
            plane=simulated.plane,
            output_root=simulated.workdir / "out",
            data_root=simulated.workdir / "data_root",
            show_plot=False,
            material_registry=settings.dry_run_registry(simulated.workdir),
        )
        session.output_root.mkdir(parents=True, exist_ok=True)
        print(f"DRY RUN on simulated hardware, output in {simulated.workdir}")
        try:
            return execute(spec, session)
        finally:
            session.material_registry.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Print a 16-bit PNG height map in IFOV mode"
    )
    parser.add_argument("--dry-run", action="store_true", help="simulated hardware")
    parser.add_argument(
        "--preview", action="store_true", help="only statistics and preview"
    )
    parser.add_argument(
        "--workdir", type=Path, default=None, help="output folder of a dry run"
    )
    options = parser.parse_args()
    started = datetime.datetime.now()
    result = run(
        dry=options.dry_run, preview_only=options.preview, workdir=options.workdir
    )
    print(f"Finished after {datetime.datetime.now() - started}: {result}")
