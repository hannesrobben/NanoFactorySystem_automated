##########################################################################
# Copyright (c) 2026 Hannes Robben                                       #
# <hannes.robben@phoenixd.uni-hannover.de>                               #
# This program is free software under the terms of the MIT license.      #
##########################################################################
"""Experiments described by one parameter object instead of values edited in a script (T51).

An :class:`ExperimentSpec` holds everything that defines an experiment; the
objective-specific values that the old experiment scripts set by hand (FOV,
drop direction, zMax, margins, corner sizes) have defaults per objective and
can be overridden. :func:`run_experiment` runs the usual flow:
plot, plane fit, OPL scan (DHM only), structures, build, print.
"""
import copy
import dataclasses
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

import numpy as np

from .aerobasic.programs.drawings import DrawableObject
from .devices.coordinate_system import DropDirection, Point2D, Point3D, ZFunction
from .experiment import Experiment, ProgramSource, StructureType
from .plane_fitting import PlaneFitMode
from .runtime import getLogger


@dataclass(frozen=True)
class CornerSpec:
    """ Size of the corner markers in µm. """

    z_um: float = -2.0
    width_um: float = 50.0
    length_um: float = 300.0
    height_um: float = 7.0
    hatch_um: float = 0.5
    slice_um: float = 0.75


@dataclass(frozen=True)
class ObjectiveDefaults:
    """ Values that depend on the objective (from the experiment template, T51). """

    fov_um: float
    drop_direction: DropDirection
    z_max_um: float
    margin_um: float
    padding_um: float
    corner: CornerSpec


OBJECTIVE_DEFAULTS = {
    "Zeiss 20x": ObjectiveDefaults(fov_um=500.0, drop_direction=DropDirection.UP, z_max_um=24550.0,
                                   margin_um=200.0, padding_um=100.0,
                                   corner=CornerSpec(width_um=50.0, length_um=300.0, hatch_um=0.5)),
    # zMax could possibly be up to 25550 um
    "Zeiss 63x": ObjectiveDefaults(fov_um=150.0, drop_direction=DropDirection.DOWN, z_max_um=25480.0,
                                   margin_um=50.0, padding_um=100.0,
                                   corner=CornerSpec(width_um=30.0, length_um=120.0, hatch_um=0.3)),
}


def default_sys_args() -> dict:
    """ Runtime sections of the experiment template (focus detection and layer scan settings). """

    return {
        "attenuator": {"fitKind": "quadratic"},
        "sample": {"name": "#1", "substrate": "boro-silicate glass", "substrateThickness": 700.0,
                   "material": "SZ2080", "materialThickness": 75.0},
        "focus": {"OffsetFocusDetection": [120, -80], "minCircularity": 0.6, "exposureValue": 120},
        "layer": {"dzFineDefault": 25.0, "laserPower": 0.7},
        "plane": {},
    }


@dataclass
class StructureSpec:
    """ One structure of an experiment.

    Parameters
    ----------
    name : str
        Structure name.
    structure : DrawableObject, optional
        The structure (program source DRAWING).
    height_data : ndarray, str or Path, optional
        Height map in µm or a mesh file (program source SLICER).
    slicer : dict
        Keyword arguments of ``Model3D_Slicer`` (``velocity``, ``hatch_size``,
        ``slice_size``, ``pixel_size``, ``unit``, …) for program source SLICER.
    factory : callable, optional
        ``factory(experiment) -> DrawableObject`` for program source DRAWING,
        for structures that need values of the running experiment (e.g. the
        acceleration ``experiment.accel_a_um`` read from the controller).
    power_mw : float, optional
        Laser power; default: the experiment default power.
    axes : str
        Printing axes, ``"ABZ"`` (galvo) or ``"XYZ"`` (stages).
    repeat : int
        Number of repetitions of this structure in the following grid cells.
    structure_type : StructureType, optional
        Default: ``NORMAL`` for DRAWING, ``IFOV`` for SLICER; ``DUMMY`` leaves
        the grid cell empty (see :meth:`empty`).
    """

    name: str
    structure: Optional[DrawableObject] = None
    height_data: Any = None
    slicer: dict = field(default_factory=dict)
    power_mw: Optional[float] = None
    axes: str = "ABZ"
    repeat: int = 0
    structure_type: Optional[StructureType] = None
    factory: Optional[Callable[[Experiment], DrawableObject]] = None

    @classmethod
    def empty(cls) -> "StructureSpec":
        """ An empty grid cell (``Experiment.skip_structure``). """

        return cls("dummy", structure_type=StructureType.DUMMY)

    def drawable(self, source: ProgramSource, objective: str,
                 experiment: Optional[Experiment] = None) -> Optional[DrawableObject]:
        """ The structure to add to the experiment for the given program source.

        Returns None for an empty grid cell.

        Raises
        ------
        ValueError
            If the data needed by the program source is missing.
        """

        if self.structure_type == StructureType.DUMMY:
            return None
        if source == ProgramSource.DRAWING:
            if self.factory is not None:
                if experiment is None:
                    raise ValueError(f"Structure {self.name}: a factory needs the running experiment.")
                return self.factory(experiment)
            if self.structure is None:
                raise ValueError(f"Structure {self.name}: program source DRAWING needs a structure or a factory.")
            return self.structure
        if source == ProgramSource.SLICER:
            if self.height_data is None:
                raise ValueError(f"Structure {self.name}: program source SLICER needs height data or a mesh.")
            from .aerobasic.programs.drawings.model3d import Model3D_Slicer
            arguments = {"center": Point3D(0, 0, 0), "objective": objective} | self.slicer
            return Model3D_Slicer(source=self.height_data, **arguments)
        raise ValueError(f"Unknown program source {source}")

    def type_for(self, source: ProgramSource) -> StructureType:
        """ Structure type used in ``Experiment.add_structure``. """

        if self.structure_type is not None:
            return self.structure_type
        return StructureType.IFOV if source == ProgramSource.SLICER else StructureType.NORMAL


@dataclass
class ExperimentSpec:
    """ Complete description of an experiment.

    Values left as None take the default of the objective
    (:data:`OBJECTIVE_DEFAULTS`); ``structure_size_um`` defaults to the FOV.

    Parameters
    ----------
    name : str
        Short name, used as folder name when the experiment is not placed on a
        substrate.
    objective : str
        Objective key, e.g. ``"Zeiss 63x"``.
    center : Point2D
        Absolute center of the structure grid in µm.
    grid : tuple of int
        (rows, cols) of the structure grid.
    structures : list of StructureSpec
        Structures in print order (repetitions follow their structure).
    program_source : ProgramSource
        DRAWING or SLICER.
    setup : {"IFOV_off", "IFOV_on"}
        SLICER needs ``"IFOV_on"``.
    """

    name: str
    objective: str
    center: Point2D
    grid: tuple[int, int]
    structures: list[StructureSpec] = field(default_factory=list)
    program_source: ProgramSource = ProgramSource.DRAWING
    setup: str = "IFOV_off"
    drop_direction: Optional[DropDirection] = None
    plane_fit_mode: PlaneFitMode = PlaneFitMode.CORNERS
    dhm_usage: bool = False
    camera_capture: bool = False
    structure_size_um: Optional[float] = None
    fov_um: Optional[float] = None
    margin_um: Optional[float] = None
    padding_um: Optional[float] = None
    z_max_um: Optional[float] = None
    corner: Optional[CornerSpec] = None
    skip_corner: bool = False
    default_power_mw: float = 0.7
    low_speed_um_s: float = 1000.0
    high_speed_um_s: float = 5000.0
    n_mid_points: int = 0
    opl_start_um: Optional[float] = None
    tilt_warning_um: float = 1.0
    sys_args: dict = field(default_factory=default_sys_args)

    def resolved(self) -> "ExperimentSpec":
        """ Return a copy with every None replaced by the default of the objective.

        Raises
        ------
        ValueError
            For an unknown objective, a SLICER experiment without IFOV setup,
            or more structures than grid cells.
        """

        if self.objective not in OBJECTIVE_DEFAULTS:
            raise ValueError(f"No defaults for objective {self.objective!r}; known: {sorted(OBJECTIVE_DEFAULTS)}")
        source = ProgramSource.parse(self.program_source)
        if source == ProgramSource.SLICER and self.setup != "IFOV_on":
            raise ValueError("Program source SLICER prints with IFOV structures and needs setup='IFOV_on'.")
        cells = sum(1 + s.repeat for s in self.structures)
        if cells > self.grid[0] * self.grid[1]:
            raise ValueError(f"{cells} structures (with repetitions) do not fit into a {self.grid} grid.")
        defaults = OBJECTIVE_DEFAULTS[self.objective]
        fov = self.fov_um if self.fov_um is not None else defaults.fov_um
        return dataclasses.replace(
            self,
            program_source=source,
            plane_fit_mode=PlaneFitMode.parse(self.plane_fit_mode),
            drop_direction=self.drop_direction or defaults.drop_direction,
            fov_um=fov,
            structure_size_um=self.structure_size_um if self.structure_size_um is not None else fov,
            margin_um=self.margin_um if self.margin_um is not None else defaults.margin_um,
            padding_um=self.padding_um if self.padding_um is not None else defaults.padding_um,
            z_max_um=self.z_max_um if self.z_max_um is not None else defaults.z_max_um,
            corner=self.corner or defaults.corner,
            sys_args=copy.deepcopy(self.sys_args),
        )

    def experiment_arguments(self, *, user: str, resin_edges, logger, backend=None, path: Optional[Path] = None,
                             substrate: Optional[str] = None, data_root: Optional[Path] = None) -> dict:
        """ Keyword arguments for :class:`Experiment`.

        Parameters
        ----------
        user : str
            User key.
        resin_edges : sequence of (x, y)
            Edges of the resin drop in µm (at least two points); their bounding box is used.
        logger : logging.Logger
        backend : {"real", "dummy"}, Backend or None
        path, substrate, data_root
            Experiment folder, or a substrate (and data root) for the default
            location (see :class:`Experiment`).
        """

        spec = self.resolved()
        edges = np.asarray(resin_edges, dtype=float)
        sys_args = spec.sys_args
        sys_args.setdefault("controller", {})["zMax"] = spec.z_max_um
        sys_args.setdefault("dhm", {})["usage"] = spec.dhm_usage
        corner = spec.corner
        return dict(
            path=path, user=user, objective=spec.objective, logger=logger, sys_args=sys_args,
            default_power=spec.default_power_mw, low_speed_um=spec.low_speed_um_s,
            high_speed_um=spec.high_speed_um_s,
            resin_corner_tr=Point2D(*edges.max(axis=0)), resin_corner_bl=Point2D(*edges.min(axis=0)),
            structure_size=spec.structure_size_um, margin=spec.margin_um, padding=spec.padding_um,
            absolute_grid_center=spec.center, grid=tuple(spec.grid), n_mid_points=spec.n_mid_points,
            drop_direction=spec.drop_direction, corner_z=corner.z_um, corner_width=corner.width_um,
            corner_length=corner.length_um, corner_height=corner.height_um, corner_hatch=corner.hatch_um,
            corner_slice=corner.slice_um, fov_dim=(spec.fov_um, spec.fov_um), skip_corner=spec.skip_corner,
            plane_fit_mode=spec.plane_fit_mode, setup=spec.setup, backend=backend, substrate=substrate,
            data_root=data_root, tilt_warning_um=spec.tilt_warning_um, camera_capture=spec.camera_capture,
            program_source=spec.program_source,
        )


def run_experiment(spec: ExperimentSpec, *, user: str, resin_edges, path: Optional[Path] = None,
                   substrate: Optional[str] = None, data_root: Optional[Path] = None, backend=None,
                   plane: Optional[ZFunction] = None, confirm: Optional[Callable[[str], bool]] = None,
                   show_plot: bool = False, substrate_information: Optional[dict] = None,
                   allow_synced_root: bool = False) -> Path:
    """ Run an experiment: plot, plane fit, OPL scan (DHM), structures, build and print.

    Parameters
    ----------
    spec : ExperimentSpec
    user : str
        User key.
    resin_edges : sequence of (x, y)
        Edges of the resin drop in µm.
    path : Path, optional
        Root folder; the experiment is written to ``<path>/<spec.name>``.
        Without ``path`` a ``substrate`` is required and the default location
        is used.
    substrate, data_root : optional
        Substrate label/UUID and data root for the default location.
    backend : {"real", "dummy"}, Backend or None
        Hardware backend (default: the lab hardware).
    plane : ZFunction, optional
        Known substrate plane (dry runs); otherwise the plane is measured.
    confirm : callable, optional
        ``confirm(question) -> bool`` before the plane fit, the OPL scan and
        printing (e.g. a message box on the lab PC); returning False stops.
    show_plot : bool
        Show the experiment plot window.
    substrate_information : dict, optional
        Free substrate information of older scripts, stored in the experiment file.
    allow_synced_root : bool
        Accept a data root inside a synchronised folder.

    Returns
    -------
    Path
        The experiment folder.
    """

    spec = spec.resolved()
    if path is not None:
        folder = Path(path) / spec.name
        folder.mkdir(parents=True, exist_ok=True)
        logger = getLogger(logfile=folder / "console.log")
    else:
        folder, logger = None, getLogger()
    arguments = spec.experiment_arguments(user=user, resin_edges=resin_edges, logger=logger, backend=backend,
                                          path=folder, substrate=substrate, data_root=data_root)
    arguments["substrate_information"] = substrate_information
    arguments["allow_synced_root"] = allow_synced_root

    def ask(question: str) -> bool:
        return confirm is None or confirm(question)

    with Experiment(**arguments) as experiment:
        experiment.plot_experiment(show=show_plot)
        if not ask("Run plane fitting?"):
            return experiment.path
        experiment.plane_fit(plane=plane)
        if spec.dhm_usage:
            if not ask("Run OPL motor scan?"):
                return experiment.path
            experiment.opl_scan(m0=spec.opl_start_um)
        for structure in spec.structures:
            if structure.structure_type == StructureType.DUMMY:
                experiment.skip_structure()
                continue
            name = experiment.add_structure(
                structure.type_for(spec.program_source), structure.name, axes=structure.axes,
                power=structure.power_mw,
                structure=structure.drawable(spec.program_source, spec.objective, experiment))
            for _ in range(structure.repeat):
                experiment.add_structure(StructureType.REPEAT, name)
        experiment.build_programs()
        if not ask("FINAL STEP: Print experiment?"):
            return experiment.path
        experiment.print_experiment()
        return experiment.path


def script_output(path: Optional[Path], default: Path, folder_name: str) -> tuple[Path, str]:
    """ Root folder and experiment name in the convention of the older experiment scripts.

    Parameters
    ----------
    path : Path or None
        Root folder passed to the script.
    default : Path
        Folder used without ``path`` (e.g. ``.output/<topic>/<name>_<date>``).
    folder_name : str
        Subfolder of ``path``.

    Returns
    -------
    tuple of (Path, str)
        ``(root, name)`` for :func:`run_experiment` (``path=root`` with
        ``spec.name = name``).
    """

    if path is None:
        return Path(default).parent, Path(default).name
    return Path(path), folder_name


def messagebox_confirm(question: str) -> bool:
    """ Ask a yes/no question in a message box (lab PC). """

    from tkinter import messagebox
    return messagebox.askyesno(message=question)
