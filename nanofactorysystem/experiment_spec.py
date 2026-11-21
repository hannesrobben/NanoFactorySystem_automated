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

A spec can be stored as a project file (``to_json()`` / ``from_json()``,
``save()`` / ``load()``, schema ``nanofactory.experiment_spec/1``, T77,
docs/design/INFORMATION_MODEL.md §6); :func:`run_experiment` writes it into
the experiment folder (``experiment_spec.json``) and the experiment file
(``/spec``).
"""
import copy
import dataclasses
import hashlib
import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional, Union

import numpy as np

from .aerobasic.programs.drawings import DrawableObject
from .aerobasic.programs.drawings.base import decode_json_value, encode_json_value, structure_from_json
from .devices.coordinate_system import DropDirection, Point2D, Point3D, ZFunction
from .experiment import Experiment, ProgramSource, StructureType
from .plane_fitting import PlaneFitMode
from .runtime import getLogger
from .structure_factories import BuildContext, FactoryCall, factory_from_json

SPEC_SCHEMA = "nanofactory.experiment_spec/1"
STRUCTURE_SCHEMA = "nanofactory.structure_spec/1"
SPEC_FILE_NAME = "experiment_spec.json"
INPUTS_FOLDER = "inputs"


class SpecSerialisationError(ValueError):
    """ A spec cannot be stored or read; the message names the structure and the field. """


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


def _check_schema(schema: Optional[str], expected: str) -> None:
    """ Accept ``expected`` and every minor version of its major version. """

    family, _, major = expected.rpartition("/")
    if not isinstance(schema, str) or schema.rpartition("/")[0] != family \
            or schema.rpartition("/")[2].split(".")[0] != major:
        raise SpecSerialisationError(f"Unsupported schema {schema!r}; expected {expected!r}.")


def _check_keys(data: dict, allowed: set, where: str) -> None:
    unknown = sorted(set(data) - allowed)
    if unknown:
        raise SpecSerialisationError(f"Unknown keys {unknown} in {where}; allowed: {sorted(allowed)}.")


def _enum_name(value, enum_type) -> Optional[str]:
    if value is None:
        return None
    return value.name if isinstance(value, enum_type) else enum_type[str(value)].name


def _safe_name(name: str) -> str:
    return "".join(c if c.isalnum() or c in "-_." else "_" for c in name)


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fp:
        for block in iter(lambda: fp.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _array_sha256(array: np.ndarray) -> str:
    array = np.ascontiguousarray(array)
    digest = hashlib.sha256(f"{array.dtype.str}{array.shape}".encode())
    digest.update(array.tobytes())
    return digest.hexdigest()


def _source_from_json(source: dict, folder: Optional[Path], name: str):
    """ Height map (ndarray) or mesh file (Path) of a slicer geometry; checks the SHA-256. """

    def check(actual: str):
        if source.get("sha256") and actual != source["sha256"]:
            raise SpecSerialisationError(f"Structure {name!r}, field 'height_data': the input differs from the "
                                         f"stored one (SHA-256 {actual} != {source['sha256']}).")

    if "inline" in source:
        array = decode_json_value(source["inline"])
        check(_array_sha256(array))
        return array
    relative = source.get("array") or source.get("file")
    if relative is None:
        raise SpecSerialisationError(f"Structure {name!r}, field 'height_data': no input is stored.")
    path = Path(relative)
    if not path.is_absolute():
        if folder is None:
            raise SpecSerialisationError(f"Structure {name!r}, field 'height_data': {relative} is relative to the "
                                         f"project file; give its folder.")
        path = Path(folder) / path
    if not path.is_file():
        raise SpecSerialisationError(f"Structure {name!r}, field 'height_data': {path} does not exist.")
    check(_file_sha256(path))
    if "array" in source:
        return np.load(path, allow_pickle=False)
    return path


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
    factory : FactoryCall or callable, optional
        For program source DRAWING, for structures that need values of the
        running experiment (e.g. the acceleration read from the controller):
        a named factory called with its arguments (see
        :mod:`nanofactorysystem.structure_factories`), built with the
        :class:`~nanofactorysystem.structure_factories.BuildContext` of the
        experiment. A plain callable ``factory(experiment)`` still runs, but
        the spec can then not be stored.
    power_mw : float, optional
        Laser power; default: the experiment default power.
    layer_power : sequence of float or callable, optional
        Laser power in mW per layer (see Experiment.add_structure, T31).
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
    factory: Union[FactoryCall, Callable[[Experiment], DrawableObject], None] = None
    layer_power: Any = None

    @classmethod
    def empty(cls) -> "StructureSpec":
        """ An empty grid cell (``Experiment.skip_structure``). """

        return cls("dummy", structure_type=StructureType.DUMMY)

    def drawable(self, source: ProgramSource, objective: str,
                 experiment: Optional[Experiment] = None, *, voxel_model=None,
                 default_power_mw: Optional[float] = None) -> Optional[DrawableObject]:
        """ The structure to add to the experiment for the given program source.

        Returns None for an empty grid cell. For program source SLICER a
        ``voxel_model`` (see :meth:`ExperimentSpec.voxel_model`) makes the
        slicing voxel-aware (T54); the slicer then needs the power of the
        structure (``power_mw``, else ``default_power_mw``) and sets it
        itself. ``voxel_model`` in ``slicer`` takes precedence.

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
                if isinstance(self.factory, FactoryCall):
                    context = experiment if isinstance(experiment, BuildContext) \
                        else BuildContext.from_experiment(experiment)
                    return self.factory.build(context)
                return self.factory(experiment)
            if self.structure is None:
                raise ValueError(f"Structure {self.name}: program source DRAWING needs a structure or a factory.")
            return self.structure
        if source == ProgramSource.SLICER:
            if self.height_data is None:
                raise ValueError(f"Structure {self.name}: program source SLICER needs height data or a mesh.")
            from .aerobasic.programs.drawings.model3d import Model3D_Slicer
            arguments = {"center": Point3D(0, 0, 0), "objective": objective}
            if voxel_model is not None:
                power = self.power_mw if self.power_mw is not None else default_power_mw
                arguments |= {"voxel_model": voxel_model, "power": power}
            arguments |= self.slicer
            return Model3D_Slicer(source=self.height_data, **arguments)
        raise ValueError(f"Unknown program source {source}")

    def type_for(self, source: ProgramSource) -> StructureType:
        """ Structure type used in ``Experiment.add_structure``. """

        if self.structure_type is not None:
            return self.structure_type
        return StructureType.IFOV if source == ProgramSource.SLICER else StructureType.NORMAL

    # ------------------------------------------------------------ serialised form (T77)

    def to_json(self, folder: Optional[Path] = None) -> dict:
        """ Return the JSON form of this structure (INFORMATION_MODEL.md §6.2).

        Parameters
        ----------
        folder : Path, optional
            Folder of the project file. Slicer inputs (height maps, mesh files)
            are then copied into ``<folder>/inputs`` and referenced relative to
            it; without a folder a height map is stored inline and a mesh file
            by its absolute path. Every input carries its SHA-256.

        Raises
        ------
        SpecSerialisationError
            If a field cannot be stored (plain callable factory or layer power,
            a drawing whose constructor arguments are incomplete, values that
            are not JSON); the message names the structure and the field.
        """

        def fail(field_name: str, reason: str):
            return SpecSerialisationError(f"Structure {self.name!r}, field {field_name!r}: {reason}")

        data = {"name": self.name, "repeat": int(self.repeat),
                "structure_type": self.structure_type.name if self.structure_type is not None else None,
                "geometry": self._geometry_json(folder, fail)}
        if callable(self.layer_power):
            raise fail("layer_power", "a function cannot be stored; give the powers per layer as a list.")
        layer_power = None if self.layer_power is None else [float(p) for p in self.layer_power]
        data["settings"] = {"axes": self.axes, "power_mw": self.power_mw, "layer_power": layer_power}
        return data

    def _geometry_json(self, folder: Optional[Path], fail) -> dict:
        if self.structure_type == StructureType.DUMMY:
            return {"kind": "empty"}
        kinds = [name for name, value in (("structure", self.structure), ("height_data", self.height_data),
                                          ("factory", self.factory)) if value is not None]
        if len(kinds) > 1:
            raise fail(kinds[1], f"a structure has exactly one geometry, but {kinds} are set.")
        if self.factory is not None:
            if not isinstance(self.factory, FactoryCall):
                raise fail("factory", "a plain callable cannot be stored; register the function with "
                                      "@structure_factory(name) and call it with its arguments.")
            try:
                return self.factory.to_json()
            except (TypeError, KeyError) as error:
                raise fail("factory", str(error)) from None
        if self.structure is not None:
            structure = self.structure.to_json()
            if structure.get("__missing__"):
                raise fail("structure", f"{type(self.structure).__name__} does not keep the constructor "
                                        f"arguments {structure['__missing__']}; it cannot be rebuilt.")
            return {"kind": "drawing", "structure": structure}
        if self.height_data is not None:
            slicer = {}
            for key, value in self.slicer.items():
                try:
                    slicer[key] = encode_json_value(value)
                except TypeError as error:
                    raise fail(f"slicer.{key}", str(error)) from None
            return {"kind": "slicer", "source": self._source_json(folder), "slicer": slicer}
        raise fail("geometry", "no structure, factory or height data is set.")

    def _source_json(self, folder: Optional[Path]) -> dict:
        if isinstance(self.height_data, np.ndarray):
            array = np.asarray(self.height_data)
            if folder is None:
                return {"inline": encode_json_value(array), "sha256": _array_sha256(array)}
            relative = Path(INPUTS_FOLDER) / f"{_safe_name(self.name)}_height.npy"
            (Path(folder) / relative).parent.mkdir(parents=True, exist_ok=True)
            np.save(Path(folder) / relative, array, allow_pickle=False)
            return {"array": relative.as_posix(), "sha256": _file_sha256(Path(folder) / relative)}
        if isinstance(self.height_data, (str, Path)):
            source = Path(self.height_data).resolve()
            if not source.is_file():
                raise SpecSerialisationError(f"Structure {self.name!r}, field 'height_data': {source} does not exist.")
            if folder is None:
                return {"file": str(source), "sha256": _file_sha256(source)}
            relative = Path(INPUTS_FOLDER) / source.name
            target = Path(folder) / relative
            if target.resolve() != source:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
            return {"file": relative.as_posix(), "sha256": _file_sha256(target)}
        raise SpecSerialisationError(f"Structure {self.name!r}, field 'height_data': "
                                     f"{type(self.height_data).__name__} cannot be stored (array or file expected).")

    @classmethod
    def from_json(cls, data: dict, folder: Optional[Path] = None) -> "StructureSpec":
        """ Rebuild a structure from :meth:`to_json`.

        Parameters
        ----------
        data : dict
            JSON form; a stand-alone structure file carries
            ``schema: "nanofactory.structure_spec/1"``.
        folder : Path, optional
            Folder of the project file, for inputs stored relative to it.

        Raises
        ------
        SpecSerialisationError
            For unknown keys, an unknown schema or geometry kind, a missing
            factory, or an input file whose SHA-256 differs.
        """

        data = dict(data)
        schema = data.pop("schema", STRUCTURE_SCHEMA)
        _check_schema(schema, STRUCTURE_SCHEMA)
        name = data.get("name", "?")
        _check_keys(data, {"name", "repeat", "structure_type", "geometry", "settings"}, f"structure {name!r}")
        settings = dict(data.get("settings") or {})
        _check_keys(settings, {"axes", "power_mw", "layer_power"}, f"structure {name!r}, settings")
        structure_type = data.get("structure_type")
        arguments = dict(name=data["name"], repeat=int(data.get("repeat", 0)),
                         structure_type=StructureType[structure_type] if structure_type else None,
                         axes=settings.get("axes", "ABZ"), power_mw=settings.get("power_mw"),
                         layer_power=settings.get("layer_power"))
        geometry = data.get("geometry") or {"kind": "empty"}
        kind = geometry.get("kind")
        if kind == "empty":
            arguments["structure_type"] = StructureType.DUMMY
        elif kind == "drawing":
            arguments["structure"] = structure_from_json(geometry["structure"])
        elif kind == "factory":
            try:
                arguments["factory"] = factory_from_json(geometry)
            except KeyError as error:
                raise SpecSerialisationError(f"Structure {name!r}, field 'factory': {error.args[0]}") from None
        elif kind == "slicer":
            arguments["height_data"] = _source_from_json(geometry["source"], folder, name)
            arguments["slicer"] = {k: decode_json_value(v) for k, v in geometry.get("slicer", {}).items()}
        else:
            raise SpecSerialisationError(f"Structure {name!r}: unknown geometry kind {kind!r}.")
        return cls(**arguments)


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
    voxel_material : str, optional
        Resin name in the voxel database. With program source SLICER the
        structures are sliced with the measured voxel size of this material,
        objective and setup (T54; spacing per ``slicer["spacing_mode"]``,
        default ``"voxel_overlap"``). None: no voxel compensation.
    voxel_database : Path, optional
        Voxel database; default: ``system.voxelDatabase`` of the configuration.
    layer_overhead_s : float
        Overhead per layer of the expected printing time (T28).
    overview_capture, overview_single_images : bool
        Stitched camera overview before and after printing, optionally with
        the single images (T28).
    materials : dict
        Material registry names per role (``"resin"``, ``"substrate"``,
        ``"medium"``); roles not given come from the substrate, then from
        ``sys_args["sample"]``. Snapshots are stored with the experiment (T75).
    description : str
        Free text describing the experiment.
    tags : list of str
        Free keywords, e.g. for a library of standard experiments.
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
    voxel_material: Optional[str] = None
    voxel_database: Optional[Path] = None
    layer_overhead_s: float = 5.0
    overview_capture: bool = False
    overview_single_images: bool = False
    materials: dict = field(default_factory=dict)
    description: str = ""
    tags: list = field(default_factory=list)

    def __post_init__(self):
        # A center written as a plain (x, y) pair is accepted and converted,
        # every consumer expects a Point2D (e.g. substrate_plan.experiment_area).
        if not isinstance(self.center, Point2D):
            try:
                x, y = self.center
            except (TypeError, ValueError):
                raise TypeError(f"ExperimentSpec.center must be a Point2D or an (x, y) pair in µm, "
                                f"got {self.center!r}") from None
            self.center = Point2D(float(x), float(y))

    # ------------------------------------------------------------ serialised form (T77)

    def to_json(self, folder: Optional[Path] = None) -> dict:
        """ Return the project-file form of this spec (INFORMATION_MODEL.md §6.1).

        Values left as None stay ``null`` ("default of the objective"); the
        spec is stored as written, not resolved.

        Parameters
        ----------
        folder : Path, optional
            Folder of the project file; slicer inputs are copied into its
            ``inputs`` subfolder (see :meth:`StructureSpec.to_json`).

        Raises
        ------
        SpecSerialisationError
            If a field cannot be stored; the message names it.
        """

        def encoded(value, field_name):
            try:
                return encode_json_value(value)
            except TypeError as error:
                raise SpecSerialisationError(f"Experiment {self.name!r}, field {field_name!r}: {error}") from None

        corner = None if self.corner is None else dataclasses.asdict(self.corner)
        sys_args = {key: encoded(value, f"sys_args.{key}") for key, value in self.sys_args.items()}
        return {
            "schema": SPEC_SCHEMA,
            "name": self.name,
            "description": self.description,
            "tags": [str(t) for t in self.tags],
            "objective": self.objective,
            "center_um": [float(self.center.X), float(self.center.Y)],
            "grid": [int(self.grid[0]), int(self.grid[1])],
            "placement": {"structure_size_um": self.structure_size_um, "fov_um": self.fov_um,
                          "margin_um": self.margin_um, "padding_um": self.padding_um,
                          "drop_direction": _enum_name(self.drop_direction, DropDirection),
                          "z_max_um": self.z_max_um, "corner": corner, "skip_corner": bool(self.skip_corner)},
            "calibration": {"plane_fit_mode": PlaneFitMode.parse(self.plane_fit_mode).name,
                            "tilt_warning_um": self.tilt_warning_um, "opl_start_um": self.opl_start_um,
                            "n_mid_points": int(self.n_mid_points)},
            "captures": {"dhm_usage": bool(self.dhm_usage), "camera_capture": bool(self.camera_capture),
                         "overview_capture": bool(self.overview_capture),
                         "overview_single_images": bool(self.overview_single_images)},
            "materials": {str(role): encoded(name, f"materials.{role}") for role, name in self.materials.items()},
            "defaults": {"program_source": ProgramSource.parse(self.program_source).name, "setup": self.setup,
                         "default_power_mw": self.default_power_mw, "low_speed_um_s": self.low_speed_um_s,
                         "high_speed_um_s": self.high_speed_um_s, "voxel_material": self.voxel_material,
                         "voxel_database": None if self.voxel_database is None else str(self.voxel_database)},
            "runtime": {"sys_args": sys_args, "layer_overhead_s": self.layer_overhead_s},
            "structures": [s.to_json(folder) for s in self.structures],
        }

    @classmethod
    def from_json(cls, data: dict, folder: Optional[Path] = None) -> "ExperimentSpec":
        """ Rebuild a spec from :meth:`to_json`.

        Unknown keys (typos) are refused at every level except inside
        ``runtime.sys_args``, which is passed on untouched.

        Parameters
        ----------
        data : dict
        folder : Path, optional
            Folder of the project file, for inputs stored relative to it.

        Raises
        ------
        SpecSerialisationError
            For an unknown major schema version, unknown keys or a structure
            that cannot be rebuilt.
        """

        data = dict(data)
        _check_schema(data.pop("schema", None), SPEC_SCHEMA)
        groups = {"placement": {"structure_size_um", "fov_um", "margin_um", "padding_um", "drop_direction",
                                "z_max_um", "corner", "skip_corner"},
                  "calibration": {"plane_fit_mode", "tilt_warning_um", "opl_start_um", "n_mid_points"},
                  "captures": {"dhm_usage", "camera_capture", "overview_capture", "overview_single_images"},
                  "defaults": {"program_source", "setup", "default_power_mw", "low_speed_um_s", "high_speed_um_s",
                               "voxel_material", "voxel_database"},
                  "runtime": {"sys_args", "layer_overhead_s"}}
        _check_keys(data, {"name", "description", "tags", "objective", "center_um", "grid", "materials",
                           "structures"} | set(groups), "experiment")
        values = {}
        for group, keys in groups.items():
            section = dict(data.get(group) or {})
            _check_keys(section, keys, group)
            values |= section
        if values.get("drop_direction") is not None:
            values["drop_direction"] = DropDirection[values["drop_direction"]]
        if values.get("corner") is not None:
            values["corner"] = CornerSpec(**values["corner"])
        if "plane_fit_mode" in values:
            values["plane_fit_mode"] = PlaneFitMode.parse(values["plane_fit_mode"])
        if "program_source" in values:
            values["program_source"] = ProgramSource.parse(values["program_source"])
        if values.get("voxel_database") is not None:
            values["voxel_database"] = Path(values["voxel_database"])
        if "sys_args" in values:
            values["sys_args"] = {k: decode_json_value(v) for k, v in (values["sys_args"] or {}).items()}
        structures = [StructureSpec.from_json(s, folder) for s in data.get("structures", [])]
        return cls(name=data["name"], objective=data["objective"], center=Point2D(*data["center_um"]),
                   grid=tuple(data["grid"]), structures=structures,
                   materials={k: decode_json_value(v) for k, v in (data.get("materials") or {}).items()},
                   description=data.get("description", ""), tags=list(data.get("tags", [])), **values)

    def save(self, path: Path) -> Path:
        """ Write the spec as project file; slicer inputs go into ``inputs/`` next to it.

        Returns
        -------
        Path
            The written file.
        """

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = self.to_json(path.parent)
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        tmp.replace(path)
        return path

    @classmethod
    def load(cls, path: Path) -> "ExperimentSpec":
        """ Read a project file written by :meth:`save` (inputs relative to its folder). """

        path = Path(path)
        return cls.from_json(json.loads(path.read_text(encoding="utf-8")), path.parent)

    def voxel_model(self):
        """ The voxel model of the experiment (:class:`~nanofactorysystem.voxel.DatabaseVoxelModel`), or None
        without ``voxel_material``. """

        if self.voxel_material is None:
            return None
        from .voxel import DatabaseVoxelModel
        return DatabaseVoxelModel(self.voxel_material, self.objective, self.setup, database=self.voxel_database)

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
            Edges of the resin drop in µm (at least two points). Their bounding
            box is passed on; four points also as ``resin_edges`` for the
            ellipse check of the experiment center (T62).
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
            resin_edges=[tuple(map(float, e)) for e in edges] if len(edges) == 4 else None,
            layer_overhead_s=spec.layer_overhead_s, overview_capture=spec.overview_capture,
            overview_single_images=spec.overview_single_images, materials=dict(spec.materials) or None,
        )


def run_experiment(spec: ExperimentSpec, *, user: str, resin_edges, path: Optional[Path] = None,
                   substrate: Optional[str] = None, data_root: Optional[Path] = None, backend=None,
                   plane: Optional[ZFunction] = None, confirm: Optional[Callable[[str], bool]] = None,
                   show_plot: bool = False, substrate_information: Optional[dict] = None,
                   allow_synced_root: bool = False, material_registry=None, plan_id: Optional[str] = None) -> Path:
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
    material_registry : MaterialRegistry, Path or False, optional
        Registry for the material snapshots (see :class:`Experiment`).
    plan_id : str, optional
        Planned entry of the substrate index that the experiment replaces
        (see :class:`Experiment`).

    Returns
    -------
    Path
        The experiment folder.
    """

    written_spec, spec = spec, spec.resolved()
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
    arguments["material_registry"] = material_registry
    arguments["plan_id"] = plan_id

    def ask(question: str) -> bool:
        return confirm is None or confirm(question)

    voxel_model = spec.voxel_model()
    with Experiment(**arguments) as experiment:
        store_spec(written_spec, experiment)
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
                power=structure.power_mw, layer_power=structure.layer_power,
                structure=structure.drawable(spec.program_source, spec.objective, experiment,
                                             voxel_model=voxel_model, default_power_mw=spec.default_power_mw))
            for _ in range(structure.repeat):
                experiment.add_structure(StructureType.REPEAT, name)
        experiment.build_programs()
        if not ask("FINAL STEP: Print experiment?"):
            return experiment.path
        experiment.print_experiment()
        return experiment.path


def store_spec(spec: ExperimentSpec, experiment: Experiment) -> Optional[dict]:
    """ Store the spec in the experiment folder and file (T77).

    Writes ``experiment_spec.json`` and the slicer inputs (``inputs/``) into
    the experiment folder and both into ``experiment.h5`` (``/spec``,
    ``/inputs``). A spec that cannot be stored (e.g. a plain callable
    factory) is logged as a warning and the experiment runs without it.

    Returns
    -------
    dict or None
        The stored JSON form, or None.
    """

    from .storage.json_copies import SPEC_NAME, write_json

    folder = Path(experiment.path)
    try:
        data = spec.to_json(folder)
    except SpecSerialisationError as error:
        experiment.log.warning(f"The experiment spec is not stored: {error}")
        return None
    inputs = {}
    for structure in data["structures"]:
        source = structure["geometry"].get("source", {})
        relative = source.get("array") or source.get("file")
        if relative and not Path(relative).is_absolute():
            inputs[relative] = folder / relative
    experiment.store.write_spec(data, inputs)
    write_json(folder / SPEC_NAME, data)
    return data


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

    import gc
    import tkinter
    from tkinter import messagebox

    # Own hidden root, destroyed and collected in this (main) thread: a Tk object freed later by
    # another thread aborts the process (Tcl_AsyncDelete, T120)
    root = tkinter.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        return messagebox.askyesno(message=question, parent=root)
    finally:
        root.destroy()
        del root
        gc.collect()
