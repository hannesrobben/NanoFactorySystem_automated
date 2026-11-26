"""Layout of an experiment as plain data, and its figure without pyplot (T80).

:func:`grid_geometry` is the grid geometry of :class:`~nanofactorysystem.experiment.Experiment` (rows along y,
columns along x, the grid centred on the experiment centre). :func:`spec_layout` computes the layout of an
``ExperimentSpec`` without hardware (cells with their structure names, corner reference points, QR code),
:func:`experiment_layout` takes it from a running ``Experiment`` (corner markers with their actual centres).
:func:`draw_layout` draws a layout into an axes and :func:`layout_figure` returns a ``Figure`` that never opens a
window; ``Experiment.plot_experiment()`` and ``substrate_plan.plot_substrate()`` use them.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Optional

import numpy as np

__all__ = ["CellLayout", "MarkerLayout", "ExperimentLayout", "grid_geometry", "spec_layout", "experiment_layout",
           "draw_layout", "layout_figure"]


@dataclass
class CellLayout:
    """ One grid cell: index in print order, centre and edge length in µm, structure names printed in it. """

    index: int
    center_um: tuple[float, float]
    size_um: float
    structures: list[str] = field(default_factory=list)


@dataclass
class MarkerLayout:
    """ A corner marker: position name (TL, TR, BR, BL), reference point and centre in µm, double corner. """

    position: str
    reference_um: tuple[float, float]
    center_um: tuple[float, float]
    double: bool = False


@dataclass
class ExperimentLayout:
    """ Geometry of one experiment in absolute stage µm.

    Attributes
    ----------
    name : str
        Experiment name.
    center_um : tuple of float
        Centre of the grid.
    rectangle_um : list of tuple
        Corners TL, TR, BR, BL of the experiment rectangle (grid plus margin).
    cells : list of CellLayout
        Grid cells in print order.
    corners : list of MarkerLayout
        Corner markers (empty with ``skip_corner``).
    qrcode_um : tuple of float, optional
        Centre of the QR code (middle of the upper rectangle edge); None without corners.
    qrcode_text : str
        Text of the QR code (the experiment UUID once the experiment exists).
    plane_fit_points_um : list of tuple
        Sample points of the plane fit.
    """

    name: str
    center_um: tuple[float, float]
    rectangle_um: list[tuple[float, float]]
    cells: list[CellLayout]
    corners: list[MarkerLayout] = field(default_factory=list)
    qrcode_um: Optional[tuple[float, float]] = None
    qrcode_text: str = ""
    plane_fit_points_um: list[tuple[float, float]] = field(default_factory=list)

    def to_json(self) -> dict:
        """ Plain JSON form (lists and numbers). """

        return asdict(self)


def grid_geometry(center_um, grid: tuple[int, int], structure_size_um: float, padding_um: float,
                  margin_um: float) -> tuple[list[tuple[float, float]], list[tuple[float, float]]]:
    """ Rectangle corners (TL, TR, BR, BL) and cell centres (print order) of an experiment grid.

    The same geometry as ``Experiment.rectangle_tl`` / ``iter_experiment_locations``: ``grid[0]`` rows along y,
    ``grid[1]`` columns along x; "top" is the smaller y.

    Returns
    -------
    rectangle : list of (x, y)
    cells : list of (x, y)
    """

    rows, cols = int(grid[0]), int(grid[1])
    width = cols * (structure_size_um + padding_um) - padding_um + 2 * margin_um
    height = rows * (structure_size_um + padding_um) - padding_um + 2 * margin_um
    cx, cy = float(center_um[0]), float(center_um[1])
    tl = (cx - width / 2, cy - height / 2)
    rectangle = [tl, (cx + width / 2, cy - height / 2), (cx + width / 2, cy + height / 2), (cx - width / 2, cy + height / 2)]
    cells = []
    for i in range(rows):
        for j in range(cols):
            cells.append((tl[0] + margin_um + j * (structure_size_um + padding_um) + structure_size_um / 2,
                          tl[1] + margin_um + i * (structure_size_um + padding_um) + structure_size_um / 2))
    return rectangle, cells


#: Structure types that take a grid cell (as in ``Experiment._build_programs``; DUMMY leaves its cell empty)
GRID_TYPES = ("NORMAL", "STITCHING", "IFOV", "REPEAT")


def _cell_names(structures, n_cells: int) -> list[list[str]]:
    """ Names of the grid structures of a spec per cell (repetitions as ``<name>_rep<n>``). """

    names: list[list[str]] = [[] for _ in range(n_cells)]
    index = 0
    for structure in structures:
        kind = getattr(getattr(structure, "structure_type", None), "name", "NORMAL")
        if kind == "DUMMY":
            index += 1
            continue
        if kind not in GRID_TYPES:
            continue
        for copy in range(1 + int(getattr(structure, "repeat", 0) or 0)):
            if index < n_cells:
                names[index].append(structure.name if copy == 0 else f"{structure.name}_rep{copy}")
            index += 1
    return names


def _experiment_cell_names(structures: list[dict], n_cells: int) -> list[list[str]]:
    """ Names of the grid structures of an ``Experiment`` per cell (the order of ``_build_programs``). """

    names: list[list[str]] = [[] for _ in range(n_cells)]
    index = 0
    for structure in structures:
        kind = getattr(structure.get("structure_type"), "name", "")
        if kind == "DUMMY":
            index += 1
        elif kind in GRID_TYPES:
            if index < n_cells:
                names[index].append(str(structure.get("name", "")))
            index += 1
    return names


def spec_layout(spec) -> ExperimentLayout:
    """ Layout of an ``ExperimentSpec`` without hardware.

    Corner markers are given by their reference points (the rectangle corners); the double corner (TL, as
    ``Experiment.add_corner_structures`` marks it) is flagged.

    Parameters
    ----------
    spec : ExperimentSpec

    Returns
    -------
    ExperimentLayout
    """

    from .plane_fitting import sample_points

    resolved = spec.resolved()
    center = (float(resolved.center.X), float(resolved.center.Y))
    rectangle, centers = grid_geometry(center, resolved.grid, resolved.structure_size_um, resolved.padding_um,
                                       resolved.margin_um)
    names = _cell_names(resolved.structures, len(centers))
    cells = [CellLayout(i, c, float(resolved.structure_size_um), names[i]) for i, c in enumerate(centers)]
    corners, qrcode = [], None
    if not resolved.skip_corner:
        corners = [MarkerLayout(p, r, r, p == "TL") for p, r in zip(("TL", "TR", "BR", "BL"), rectangle)]
        qrcode = ((rectangle[0][0] + rectangle[1][0]) / 2, rectangle[0][1])
    points = sample_points(resolved.plane_fit_mode, np.asarray(rectangle[0]), resolved.margin_um, resolved.padding_um,
                           resolved.structure_size_um, tuple(resolved.grid))
    return ExperimentLayout(resolved.name, center, rectangle, cells, corners, qrcode, "",
                            [tuple(map(float, p)) for p in points])


def experiment_layout(experiment) -> ExperimentLayout:
    """ Layout of a running ``Experiment`` (corner markers with their actual centres, structures per cell).

    Parameters
    ----------
    experiment : Experiment

    Returns
    -------
    ExperimentLayout
    """

    record = experiment._layout()
    rectangle = [tuple(map(float, p)) for p in record.rectangle_um]
    centers = [tuple(map(float, p)) for p in record.grid_positions_um]
    names = _experiment_cell_names(experiment.structures, len(centers))
    cells = [CellLayout(i, c, float(experiment.structure_size), names[i]) for i, c in enumerate(centers)]
    corners = [MarkerLayout(c.position, tuple(map(float, c.reference_um)), tuple(map(float, c.center_um)), c.double)
               for c in record.corners]
    qrcode = tuple(map(float, record.qrcode_um)) if record.qrcode_um is not None else None
    center = tuple(map(float, np.asarray(experiment.absolute_grid_center)[:2]))
    return ExperimentLayout(getattr(experiment, "experiment_label", "") or "", center, rectangle, cells, corners,
                            qrcode, record.qrcode_text,
                            [tuple(map(float, p)) for p in experiment.sample_points_for_plane_fitting()])


def draw_layout(ax, layout: ExperimentLayout, *, color: str = "green", label_cells: bool = True,
                legend: bool = True) -> None:
    """ Draw an experiment layout into ``ax``: rectangle, cells (with index), plane-fit points, corners, QR code.

    Parameters
    ----------
    ax : matplotlib.axes.Axes
    layout : ExperimentLayout
    color : str
        Colour of the cells.
    label_cells : bool
        Write the cell index (and the structure names) at every cell.
    legend : bool
        Give the artists legend labels.
    """

    from matplotlib.patches import Polygon, Rectangle

    def label(text):
        return text if legend else None

    ax.add_patch(Polygon(np.asarray(layout.rectangle_um), closed=True, edgecolor="blue", facecolor="none", lw=2,
                         label=label("Experiment Field")))
    for cell in layout.cells:
        x0, y0 = cell.center_um[0] - cell.size_um / 2, cell.center_um[1] - cell.size_um / 2
        ax.add_patch(Rectangle((x0, y0), cell.size_um, cell.size_um, edgecolor=color, facecolor="none", lw=1))
        if label_cells:
            text = f"{cell.index}" + (f" {', '.join(cell.structures)}" if cell.structures else "")
            ax.text(x0, y0, text, color=color, fontsize=6)
    if layout.cells:
        ax.scatter([c.center_um[0] for c in layout.cells], [c.center_um[1] for c in layout.cells], s=3, marker="x",
                   color=color, label=label("Structures"))
    if layout.plane_fit_points_um:
        ax.scatter(*zip(*layout.plane_fit_points_um), s=3, marker=".", color="red",
                   label=label("Plane Fitting Probe Points"))
    single = [c for c in layout.corners if not c.double]
    if single:
        ax.scatter([c.center_um[0] for c in single], [c.center_um[1] for c in single], s=12, marker="s",
                   color="orange", label=label("Corners"))
    for corner in layout.corners:
        if corner.double:
            ax.scatter([corner.center_um[0]], [corner.center_um[1]], s=30, marker="D", color="darkred",
                       label=label("Double corner (orientation)"))
        ax.annotate(corner.position, corner.center_um, fontsize=6, color="darkorange")
    if layout.qrcode_um is not None:
        ax.scatter([layout.qrcode_um[0]], [layout.qrcode_um[1]], s=20, marker="s", color="black",
                   label=label("QR code"))


def layout_figure(layout: ExperimentLayout, *, limits=None, title: Optional[str] = None):
    """ A figure of one layout that never opens a window (no pyplot).

    Parameters
    ----------
    layout : ExperimentLayout
    limits : ((x0, x1), (y0, y1)), optional
        Axis limits; default: the rectangle with 10 % space.
    title : str, optional

    Returns
    -------
    matplotlib.figure.Figure
    """

    from .utils.figures import new_figure

    figure, ax = new_figure(False)
    draw_layout(ax, layout)
    if limits is None:
        corners = np.asarray(layout.rectangle_um)
        span = corners.max(axis=0) - corners.min(axis=0)
        limits = tuple(zip(corners.min(axis=0) - 0.1 * span, corners.max(axis=0) + 0.1 * span))
    ax.set_xlim(*limits[0])
    ax.set_ylim(*limits[1])
    ax.set_aspect("equal")
    ax.set_title(title or layout.name, fontsize=8)
    ax.set_xlabel("X [um]")
    ax.set_ylabel("Y [um]")
    return figure
