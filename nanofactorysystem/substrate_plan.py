##########################################################################
# Copyright (c) 2026 Hannes Robben                                       #
# <hannes.robben@phoenixd.uni-hannover.de>                               #
# This program is free software under the terms of the MIT license.      #
##########################################################################
"""Several experiments on one substrate (T52).

A substrate main file describes the substrate (:class:`SubstrateSpec`) and the
experiments printed on it (:class:`SubstrateExperiment`, each with its
:class:`~nanofactorysystem.experiment_spec.ExperimentSpec`).
:func:`run_substrate` checks the layout before anything is printed, then runs
the experiments one after another; each one is entered into the substrate
index (``substrate.json``).
"""
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional, Union

import numpy as np

from .devices.coordinate_system import ZFunction
from .experiment import QR_CODE_WIDTH_UM
from .experiment_spec import ExperimentSpec, run_experiment
from .resin_drop import drop_outline, has_drop_boundary, rectangle_inside
from .runtime import getLogger
from .voxel.materials import as_material_dict
from .storage.substrate_store import (SubstrateRecord, SubstrateStore, check_not_synced, default_root,
                                      initials, substrate_overview)



class LayoutError(ValueError):
    """ Experiment areas overlap each other or leave the resin drop. """


@dataclass
class SubstrateSpec:
    """ The substrate a main file prints on.

    Parameters
    ----------
    user : str
        User key.
    objective : str
        Objective of all experiments, e.g. ``"Zeiss 63x"``.
    resin_edges : sequence of (x, y)
        Edges of the resin drop in µm, e.g. [[right], [left], [near], [far]];
        the ellipse through four points is the printable area (T62), with
        fewer points their bounding box.
    label : str, optional
        Label of the substrate, e.g. ``"HR-26-001"``. A substrate that does
        not exist yet is created; without a label the next free label of the
        user is used.
    material : str or dict
        Resin of the drop and substrate: a material registry name of the
        resin, or a dictionary as in older mains (``resin``, ``substrate``,
        ``medium``, ``batch``, thicknesses, …). The dictionary is stored when
        the substrate is created; its ``resin``/``batch`` also name the
        material of a newly recorded drop (T75, T76).
    substrate_material : str
        Registry name of the substrate material; default: ``material["substrate"]``.
    substrate_type : str
        ``"cover_slip"``, ``"slide"``, ``"wafer"``, ``"other"`` or ``""``.
    dimensions : dict
        ``shape`` (``"rectangle"``/``"round"``) with ``width_mm``,
        ``length_mm`` / ``diameter_mm`` and ``thickness_um``.
    resin_batch : str
        Batch of the resin; default: ``material["batch"]``.
    resin_thickness_um : float, optional
        Thickness of the resin drop.
    application : {"drop", "dip_in"}
        How the resin is applied.
    notes : str
        Free text (stored when the substrate is created).
    data_root : Path, optional
        Data root with the substrates; default: the user's default location.
    allow_synced_root : bool
        Accept a data root inside a synchronised folder.
    """

    user: str
    objective: str
    resin_edges: list
    label: Optional[str] = None
    material: Union[str, dict] = field(default_factory=dict)
    notes: str = ""
    data_root: Optional[Path] = None
    allow_synced_root: bool = False
    substrate_material: str = ""
    substrate_type: str = ""
    dimensions: dict = field(default_factory=dict)
    resin_batch: str = ""
    resin_thickness_um: Optional[float] = None
    application: str = "drop"

    def root(self) -> Path:
        """ The data root (see :func:`default_root`). """

        if self.data_root is None:
            return default_root(self.user, allow_synced_root=self.allow_synced_root)
        if not self.allow_synced_root:
            check_not_synced(self.data_root)
        return Path(self.data_root)

    def bounds(self) -> tuple[np.ndarray, np.ndarray]:
        """ Lower-left and upper-right corner of the resin drop's bounding box in µm. """

        edges = np.asarray(self.resin_edges, dtype=float)
        return edges.min(axis=0), edges.max(axis=0)


@dataclass
class SubstrateExperiment:
    """ One experiment of a substrate main file.

    Parameters
    ----------
    spec : ExperimentSpec
        The experiment.
    path : Path, optional
        Root folder; the experiment is stored in ``<path>/<spec.name>``.
        Default: the substrate folder below the data root.
    """

    spec: ExperimentSpec
    path: Optional[Path] = None


@dataclass(frozen=True)
class Area:
    """ Axis-parallel rectangle on the substrate in µm.

    Parameters
    ----------
    name : str
        Experiment name (or label for experiments already on the substrate).
    lower : tuple of float
        (x, y) of the lower-left corner.
    upper : tuple of float
        (x, y) of the upper-right corner.
    """

    name: str
    lower: tuple[float, float]
    upper: tuple[float, float]

    def overlaps(self, other: "Area") -> bool:
        """ True if the interiors of both rectangles intersect. """

        return all(self.lower[i] < other.upper[i] and other.lower[i] < self.upper[i] for i in range(2))

    def inside(self, lower, upper) -> bool:
        """ True if the rectangle lies within ``lower``–``upper``. """

        return all(lower[i] <= self.lower[i] and self.upper[i] <= upper[i] for i in range(2))


def marker_clearance(spec: ExperimentSpec) -> float:
    """ How far corner markers and QR code reach beyond the experiment rectangle, in µm.

    The corners are centred on the rectangle corners (half their width lies
    outside); the QR code is centred on the upper edge.
    """

    spec = spec.resolved()
    if spec.skip_corner:
        return 0.0
    return max(spec.corner.width_um, QR_CODE_WIDTH_UM) / 2


def experiment_area(spec: ExperimentSpec) -> Area:
    """ Area an experiment occupies on the substrate: its rectangle (grid plus margin) and markers.

    Uses the same geometry as :class:`~nanofactorysystem.experiment.Experiment`
    (``rows = grid[0]`` along y, ``cols = grid[1]`` along x).
    """

    resolved = spec.resolved()
    rows, cols = resolved.grid
    step = resolved.structure_size_um + resolved.padding_um
    half = np.array([cols * step - resolved.padding_um + 2 * resolved.margin_um,
                     rows * step - resolved.padding_um + 2 * resolved.margin_um]) / 2
    half = half + marker_clearance(resolved)
    center = np.array(resolved.center.as_tuple(), dtype=float)
    return Area(resolved.name, tuple(map(float, center - half)), tuple(map(float, center + half)))


def existing_areas(root: Path, label: str, logger: Optional[logging.Logger] = None) -> list[Area]:
    """ Areas of the experiments already entered into the index of a substrate.

    The rectangle is read from each experiment file; for experiments with
    markers the QR code clearance is added (it is larger than half a corner
    width). Experiments whose file cannot be read
    are skipped with a warning.
    """

    logger = logger or getLogger()
    areas = []
    for item in substrate_overview(root, label, qr_clearance_um=QR_CODE_WIDTH_UM / 2):
        if item.state == "planned":
            continue  # nothing printed yet; a substrate main plans its experiments again
        if item.error:
            logger.warning(f"Experiment {item.name} ({item.folder}) is not checked for overlap: {item.error}")
            continue
        if item.area_um is None:
            continue
        areas.append(Area(item.name, tuple(map(float, item.area_um[0])), tuple(map(float, item.area_um[1]))))
    return areas


def check_layout(substrate: SubstrateSpec, experiments: list[SubstrateExperiment],
                 existing: Optional[list[Area]] = None) -> list[Area]:
    """ Check the experiments of a substrate before printing.

    Raises
    ------
    LayoutError
        If an experiment uses another objective than the substrate, leaves the
        resin drop (the ellipse through its four edge points, T62, else
        their bounding box; not checked for dip-in), or overlaps another experiment of the
        list or one that is already on the substrate (``existing``). The
        message lists every problem.

    Returns
    -------
    list of Area
        The areas of the experiments, in list order.
    """

    problems = []
    names = [e.spec.name for e in experiments]
    duplicates = sorted({n for n in names if names.count(n) > 1})
    if duplicates:
        problems.append(f"experiment names used more than once: {duplicates}")
    for experiment in experiments:
        if experiment.spec.objective != substrate.objective:
            problems.append(f"{experiment.spec.name}: objective {experiment.spec.objective!r} differs from the "
                            f"substrate objective {substrate.objective!r}")
    areas = [experiment_area(e.spec) for e in experiments]
    lower, upper = substrate.bounds()
    outline = drop_outline(substrate.resin_edges)
    for experiment, area in zip(experiments, areas):
        if not has_drop_boundary(experiment.spec.resolved().drop_direction):
            continue  # dip-in: no drop boundary (F8)
        if outline is not None:
            if not rectangle_inside(outline, area.lower, area.upper):
                problems.append(f"{area.name}: area {area.lower} - {area.upper} leaves the resin drop "
                                f"(ellipse through the edge points)")
        elif not area.inside(lower, upper):
            problems.append(f"{area.name}: area {area.lower} - {area.upper} leaves the resin drop "
                            f"{tuple(lower.tolist())} - {tuple(upper.tolist())}")
    for i, area in enumerate(areas):
        for other in areas[i + 1:]:
            if area.overlaps(other):
                problems.append(f"{area.name} overlaps {other.name}")
        for other in existing or []:
            if area.overlaps(other):
                problems.append(f"{area.name} overlaps experiment {other.name} already on the substrate")
    if problems:
        raise LayoutError("The substrate layout is not valid:\n- " + "\n- ".join(problems))
    return areas


def plot_substrate(substrate: SubstrateSpec, areas: list[Area], existing: Optional[list[Area]] = None,
                   show: bool = False):
    """ Plot the resin drop, the planned experiment areas and those already on the substrate.

    Returns
    -------
    matplotlib.figure.Figure
    """

    from matplotlib.patches import Rectangle

    from .utils.figures import finish_figure, new_figure

    figure, ax = new_figure(show)  # no Tk objects unless shown (T120)
    lower, upper = substrate.bounds()
    edges = np.asarray(substrate.resin_edges, dtype=float)
    ax.add_patch(Rectangle(lower, *(upper - lower), fill=False, linestyle="--", color="grey"))
    outline = drop_outline(substrate.resin_edges)
    if outline is not None:
        from matplotlib.patches import Ellipse as EllipsePatch
        ax.add_patch(EllipsePatch((outline.cx, outline.cy), 2 * outline.a, 2 * outline.b, fill=False, color="grey"))
    ax.plot(edges[:, 0], edges[:, 1], "x", color="grey", label="resin edges")
    for area, color in [(a, "tab:grey") for a in existing or []] + [(a, "tab:blue") for a in areas]:
        size = np.subtract(area.upper, area.lower)
        ax.add_patch(Rectangle(area.lower, *size, alpha=0.3, color=color))
        ax.annotate(area.name, np.add(area.lower, size / 2), ha="center", va="center", fontsize=8)
    ax.set_xlim(lower[0], upper[0])
    ax.set_ylim(lower[1], upper[1])
    ax.set_aspect("equal")
    ax.set_xlabel("x [µm]")
    ax.set_ylabel("y [µm]")
    ax.set_title(f"Substrate {substrate.label or '(new)'}: {len(areas)} experiments")
    finish_figure(figure, show)
    return figure


def open_substrate(substrate: SubstrateSpec, store: SubstrateStore) -> SubstrateRecord:
    """ Return the substrate record, creating it if needed, with the resin drop recorded.

    A new substrate gets the version-2 fields of the spec; a new drop the
    resin name, batch, thickness and application (T76). An existing record is
    not changed apart from a new drop.
    """

    from .config import sysConfig

    material = as_material_dict(substrate.material)
    if substrate.label is not None and substrate.label in store.labels():
        record = store.get(substrate.label)
    else:
        record = store.create(substrate.user, initials(sysConfig.user(substrate.user)), label=substrate.label,
                              material=material, notes=substrate.notes,
                              substrate_material=substrate.substrate_material or str(material.get("substrate", "")),
                              substrate_type=substrate.substrate_type, dimensions=substrate.dimensions)
    edges = [list(map(float, e)) for e in substrate.resin_edges]
    if record.drop_index(edges) is None:
        thickness = substrate.resin_thickness_um
        if thickness is None and material.get("resin_thickness_um") is not None:
            thickness = float(material["resin_thickness_um"])
        record = store.add_resin_drop(record.label, edges, material=str(material.get("resin", "")),
                                      batch=substrate.resin_batch or str(material.get("batch", "")),
                                      thickness_um=thickness, application=substrate.application)
    return record


def run_substrate(substrate: SubstrateSpec, experiments: list[SubstrateExperiment], *, backend=None,
                  plane: Optional[ZFunction] = None, confirm: Optional[Callable[[str], bool]] = None,
                  confirm_between: Optional[Callable[[str], bool]] = None, show_plot: bool = False,
                  logger: Optional[logging.Logger] = None, material_registry=None) -> list[Path]:
    """ Check the layout, then run the experiments of a substrate one after another.

    Parameters
    ----------
    substrate : SubstrateSpec
    experiments : list of SubstrateExperiment
        Experiments in print order.
    backend : {"real", "dummy"}, Backend or None
        Hardware backend (default: the lab hardware).
    plane : ZFunction, optional
        Known substrate plane (dry runs); otherwise each experiment measures it.
    confirm : callable, optional
        ``confirm(question) -> bool`` inside each experiment (see
        :func:`run_experiment`).
    confirm_between : callable, optional
        ``confirm_between(question) -> bool`` before every experiment after
        the first; returning False stops the run.
    show_plot : bool
        Show the substrate layout and each experiment plot.
    logger : logging.Logger, optional
    material_registry : MaterialRegistry, Path or False, optional
        Registry for the material snapshots of the experiments (see
        :class:`~nanofactorysystem.experiment.Experiment`).

    Returns
    -------
    list of Path
        Folders of the experiments that were run.

    Raises
    ------
    LayoutError
        Before anything is created or printed, if the layout is not valid
        (see :func:`check_layout`).
    """

    logger = logger or getLogger()
    store = SubstrateStore(substrate.root())
    known = substrate.label is not None and substrate.label in store.labels()
    existing = existing_areas(store.root, substrate.label, logger) if known else []
    areas = check_layout(substrate, experiments, existing)
    if show_plot:
        plot_substrate(substrate, areas, existing, show=True)

    record = open_substrate(substrate, store)
    logger.info(f"Substrate {record.label}: {len(experiments)} experiments, {len(existing)} already on it")
    drop = record.drop_index(substrate.resin_edges)
    plan_ids = [store.plan_experiment(record.label, experiment.spec.name, objective=experiment.spec.objective,
                                      area_um=(area.lower, area.upper), resin_drop=drop,
                                      center_um=experiment.spec.center.as_tuple())
                for experiment, area in zip(experiments, areas)]
    folders = []
    for index, experiment in enumerate(experiments):
        if index > 0 and confirm_between is not None \
                and not confirm_between(f"Start experiment {experiment.spec.name} "
                                        f"({index + 1}/{len(experiments)})?"):
            logger.info(f"Stopped before experiment {experiment.spec.name}")
            break
        logger.info(f"Experiment {index + 1}/{len(experiments)}: {experiment.spec.name}")
        folders.append(run_experiment(
            experiment.spec, user=substrate.user, resin_edges=substrate.resin_edges, path=experiment.path,
            substrate=record.label, data_root=store.root, backend=backend, plane=plane, confirm=confirm,
            show_plot=show_plot, allow_synced_root=substrate.allow_synced_root,
            material_registry=material_registry, plan_id=plan_ids[index]))
    return folders
