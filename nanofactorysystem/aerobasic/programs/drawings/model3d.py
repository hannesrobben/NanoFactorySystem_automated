"""model3d.py — Model3D_Slicer: a DrawableObject that prints arbitrary 3D models.

This module is the *translator* between the tpp_slicer toolpath IR and the
IFOV/AeroBasic program world (slicer docs/04, roadmap step 10):

    mesh / height map                    (STL, GLB, OBJ, np.ndarray, Trimesh)
        │  tpp_slicer: preprocess → slice → hatch [→ optimize]
        ▼
    ToolpathJob (IR, structure-local µm)
        │  Model3D_Slicer.iterate_layers  ← THIS MODULE
        ▼
    IFOV_Lines per layer → AeroBasic IFOV program text

Analogy: ``IFOV_Lines`` is the *typesetter* (it casts line geometry into real
machine code); ``Model3D_Slicer`` is the *translator* that brings an arbitrary
design into that printable line form. Both the existing grating track
(``BinaryGrating_IFOV`` → ``Rectangle2D_IFOV``) and this new model track end
on the same typesetter — which is why a ``Model3D_Slicer`` instance is a
drop-in replacement for ``BinaryGrating_IFOV`` in ``experiment.add_structure``.

Placement contract (verified against ``Rectangle2D_IFOV`` and ``base.py``):
    * Line coordinates handed to ``IFOV_Lines`` are structure-local µm,
      *relative to the reference point* (galvo A/B receive only the µm→mm
      unit scaling in ``IFOV_AeroBasicProgram._apply_ifov_conversion``).
    * The reference point is ``center + (0, 0, layer_z)`` — structure-local.
      World placement (stage offsets, drop direction, plane fit z) is applied
      by the ``CoordinateSystem`` exactly as for every other DrawableObject.
    * Consequently the IR is re-centered once after preprocessing: footprint
      bounding-box centre → (0, 0), mesh z-min → 0 (work order §3.3, A3).

Stage 2 (this file): infill segments render via ``IFOV_Lines`` (laser
toggles per segment); contour rings, walls and multi-vertex paths render via
``IFOV_PolyLines`` (one continuous laser-on pass per path). Per layer the
contour block is emitted first (outer -> inner), then the infill block —
both bundled into one yielded layer program (docs/01 §6).
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Iterator, Optional

import numpy as np
import trimesh

# Leaf classes / geometry types of the drawings package (relative imports so
# this file only depends on its own package neighbourhood).
from .base import DrawableAeroBasicProgram, DrawableObject
from .lines import IFOV_Lines

from nanofactorysystem.devices.coordinate_system import (
    CoordinateSystem, Point2D, Point3D,
)

# Slicer engine (see work order §2: engine lives as a self-contained
# subpackage under nanofactorysystem.aerobasic.slicer).
from nanofactorysystem.aerobasic.slicer import (
    JobParameters, LaserParameters, MotionParameters, SlicingParameters,
    ToolpathJob, slice_geometry,
)
from nanofactorysystem.aerobasic.slicer import preprocess as _preprocess
from nanofactorysystem.aerobasic.slicer import storage as _storage
from nanofactorysystem.aerobasic.slicer.timing import estimate_toolpath
from nanofactorysystem.aerobasic.slicer.toolpath import ROLE_INFILL
from nanofactorysystem.aerobasic.slicer.units import UM_PER_UNIT

log = logging.getLogger(__name__)

# Sentinel to distinguish "caller did not pass this kwarg" from "caller
# passed the default value" — needed for the params-vs-kwargs precedence
# warning (work order A5).
_UNSET = object()

# Convenience-kwarg → SlicingParameters field defaults (work order §3.5).
_SLICING_KWARG_DEFAULTS = {
    "hatch_size": 0.2,          # → hatch_spacing_um
    "slice_size": 0.2,          # → layer_height_um
    "hatch_strategy": "alternating",
    "hatch_angle_deg": 0.0,
    "contour_offset_um": 0.0,
    "num_contour_lines": 0,
    "spacing_mode": "voxel_overlap",
    "voxel_overlap": 0.3,
}


class IFOV_PolyLines(IFOV_Lines):
    """IFOV leaf for continuous multi-point paths (contours, walls, spirals).

    The polyline counterpart to ``IFOV_Lines`` (work order §4, docs/01 §2.2):
    per path the laser is positioned once (RAPID, laser off) and then stays
    ON through *all* following vertices (LINEAR chain) — no on/off switching
    at every corner. For ``closed`` paths a final LINEAR returns to the start
    vertex, closing the ring.

    Inherits from ``IFOV_Lines`` **deliberately** (composition-over-
    duplication trade-off): the velocity heuristic (500–25000 treated as
    µm/s ÷ 1000), the power→analog calibration (``_get_power_val`` +
    calibration file) and ``center_point`` stay single-sourced in
    ``lines.py`` — if the calibration logic changes there, this class follows
    automatically. ``self.lines`` stays empty; only ``iterate_layers`` is
    overridden. The IFOV header block is mirrored 1:1 from
    ``IFOV_Lines.iterate_layers`` (verified by a skeleton test) because it is
    inlined there and cannot be reused without touching ``lines.py``.

    Coordinate convention (identical to ``IFOV_Lines``): vertex coordinates
    are structure-local µm *relative to the reference point*; galvo A/B only
    receive the µm→mm unit scaling, world placement is done by the
    ``CoordinateSystem`` via the reference-point RAPID.
    """

    def __init__(
            self,
            reference_point: Point2D | Point3D,
            polylines: list[list[Point2D | Point3D]],
            *,
            velocity: float,
            power: Optional[float] = None,
            closed: bool | list[bool] = False,
    ):
        """
        Args:
            reference_point: Structure-local reference (usually
                ``center + (0, 0, layer_z)``); the stage RAPIDs here first.
            polylines: One list of Point2D/Point3D per path, ≥ 2 vertices.
                Closed rings follow the IR convention: *without* repeating
                the first vertex at the end.
            velocity: Grating convention, see ``IFOV_Lines``.
            power: mW; converted via the calibration file. None = leave the
                experiment-set power untouched.
            closed: Single flag for all paths or one flag per path.
        """
        # Reuse velocity normalisation + power handling from IFOV_Lines.
        super().__init__(reference_point, lines=[],
                         velocity=velocity, power=power)

        if not polylines:
            raise ValueError("polylines must contain at least one path")
        for i, path in enumerate(polylines):
            if len(path) < 2:
                raise ValueError(
                    f"polyline {i} needs at least 2 vertices, got {len(path)}")
            for p in path:
                if not isinstance(p, Point2D):
                    raise TypeError(
                        f"polyline {i} contains {type(p).__name__}; "
                        "expected Point2D/Point3D")
        self.polylines = polylines

        if isinstance(closed, bool):
            self.closed: list[bool] = [closed] * len(polylines)
        else:
            if len(closed) != len(polylines):
                raise ValueError(
                    f"closed has {len(closed)} flags for "
                    f"{len(polylines)} polylines")
            self.closed = [bool(c) for c in closed]
        for i, (path, c) in enumerate(zip(self.polylines, self.closed)):
            if c and len(path) < 3:
                raise ValueError(
                    f"closed polyline {i} needs at least 3 vertices")

    def iterate_layers(self, coordinate_system: CoordinateSystem,
                       objective: str = "Zeiss 63x",
                       ) -> Iterator["DrawableAeroBasicProgram"]:
        from .base import IFOV_AeroBasicProgram
        from nanofactorysystem.aerobasic import SingleAxis

        program = IFOV_AeroBasicProgram(coordinate_system)

        # ---- IFOV header: mirrors IFOV_Lines.iterate_layers 1:1 ----------
        program.initialise_IFOV_configuration(objective=objective)
        if self.power is not None:
            power_val = self._get_power_val(self.power)
            program.comment(f"Power set to {self.power} mW")
            program.SET_POWER(power=float(power_val))
        if objective == "Zeiss 63x":
            program.SET_SPEED(F=5)
            program.SET_SPEED(F=5, ax="A")
            program.SET_SPEED(F=5, ax="B")
            program.SET_SPEED(F=1, ax="Z")
        elif objective == "Zeiss 20x":
            program.SET_SPEED(F=10)
            program.SET_SPEED(F=10, ax="A")
            program.SET_SPEED(F=10, ax="B")
            program.SET_SPEED(F=1, ax="Z")
        else:
            raise ValueError(f"Objective {objective} is not supported.")
        program.COMPENSATE_GALVO_ROTATION(axis=SingleAxis.A)
        program.ABSOLUTE()
        if isinstance(self.reference_point, Point3D):
            program.RAPID(X=self.reference_point.X,
                          Y=self.reference_point.Y,
                          Z=self.reference_point.Z)
        else:
            program.RAPID(X=self.reference_point.X,
                          Y=self.reference_point.Y)
        program.RESET_GALVO()
        program.START_IFOV()

        # ---- polyline body: one RAPID per path, laser stays on -----------
        for path, is_closed in zip(self.polylines, self.closed):
            start = path[0]
            program.RAPID(A=start.X, B=start.Y)        # laser off (AUTO)
            for vertex in path[1:]:
                program.LINEAR(A=vertex.X, B=vertex.Y)  # laser on
            if is_closed:
                program.LINEAR(A=start.X, B=start.Y)    # close the ring

        program.end_ifov_program()
        yield program


class Model3D_Slicer(DrawableObject):
    """Print an arbitrary 3D model (mesh / height map) via the tpp_slicer.

    Drop-in replacement for ``BinaryGrating_IFOV`` in
    ``experiment.add_structure(...)``::

        experiment.add_structure(
            structure_type=StructureType.IFOV,
            name="model3d_...",
            axes="XYZ",
            power=parameterset["power"],
            structure=Model3D_Slicer(
                center=Point3D(0, 0, -1),
                source="part.stl",                # or GLB/OBJ/ndarray/Trimesh
                unit="mm",                        # unit of the source file
                velocity=parameterset["velocity"],
                power=None,                       # None → experiment power
                hatch_size=parameterset["hatch size"],
                slice_size=parameterset["slice size"],
                hatch_strategy="alternating",
            ),
        )

    Units (slicer docs/03 §1):
        * ``hatch_size`` / ``slice_size`` and everything after the
          preprocessor are in **µm** (they map to ``hatch_spacing_um`` /
          ``layer_height_um``).
        * ``source`` coordinates are in ``unit`` and converted exactly once
          by the preprocessor.
        * ``velocity`` follows the *grating convention* consumed by
          ``IFOV_Lines``: values in 500–25000 are treated as µm/s (divided by
          1000 → mm/s); values below are treated as mm/s. NOTE (verified,
          work order §6): the *effective* mark speed in the generated program
          is currently objective-bound inside ``IFOV_Lines``
          (``SET_SPEED F=5`` for 63x / ``F=10`` for 20x); ``velocity`` is
          still forwarded for parity, provenance and the time estimate.

    Parameter precedence (work order A5): if ``params`` is given it wins;
    conflicting convenience kwargs are ignored with a ``log.warning``.

    Placement (work order §3.3, A3): the mesh footprint (bounding-box centre)
    is moved to ``(center.X, center.Y)`` and the mesh base (z-min) to
    ``center.Z``; the structure grows upwards from there — mirroring the
    grating, whose base starts at ``center.Z``.

    Rendering (stage 2): open 2-point infill elements go to ``IFOV_Lines``;
    contour rings (``num_contour_lines > 0``), shells and multi-vertex paths
    go to ``IFOV_PolyLines`` — one continuous laser-on pass per path, contours
    before infill within each layer (docs/01 §6). Note that
    ``hatch_strategy="concentric"`` emits its rings as 2-point infill
    segments and therefore renders via ``IFOV_Lines``. Only shell *groups*
    (no per-layer z) remain unrendered; they are counted in
    ``skipped_elements_report`` with a warning.

    Voxel-aware slicing (T54): with ``voxel_model`` (e.g.
    ``nanofactorysystem.voxel.DatabaseVoxelModel``) and data for ``power`` and
    ``velocity``, contours are offset inward by half the voxel width, the
    first and last slice lie half a voxel height inside the part, and
    ``spacing_mode="voxel_overlap"`` (default) derives hatch and slice size
    from the voxel size and ``voxel_overlap``; ``"static_hatching"`` keeps
    ``hatch_size``/``slice_size`` and only warns about gaps. The values used
    are in ``to_json()["voxel"]``. Without a model or data nothing changes.

    Debugging (docs/05): pass ``debug_plot_dir`` to get a per-layer PNG
    flipbook of the sliced IR (grey = design cross-section, blue = contour
    paths → IFOV_PolyLines, orange = infill → IFOV_Lines), written once
    right after slicing. Plot failures are logged, never raised —
    ``debug_plot_dir`` is intentionally absent from ``to_json``: it changes
    no geometry and does not belong in the provenance record.
    """

    def __init__(
            self,
            center: Point2D | Point3D,
            source: str | Path | np.ndarray | trimesh.Trimesh,
            *,
            # --- print parameters (grating parity) --------------------------
            velocity: float,
            power: Optional[float] = None,
            objective: str = "Zeiss 63x",
            # --- slicing convenience kwargs (used when params is None) ------
            hatch_size: float | object = _UNSET,          # µm
            slice_size: float | object = _UNSET,          # µm
            hatch_strategy: str | object = _UNSET,
            hatch_angle_deg: float | object = _UNSET,     # deg, 0 = along X
            contour_offset_um: float | object = _UNSET,   # µm (docs/03 §2)
            num_contour_lines: int | object = _UNSET,     # walls (stage 2)
            spacing_mode: str | object = _UNSET,          # voxel data: "voxel_overlap" / "static_hatching"
            voxel_overlap: float | object = _UNSET,       # voxel data: overlap ratio of lines/layers
            # --- voxel-aware slicing (T54) -------------------------------------
            voxel_model: Any = None,
            # --- input / behaviour -------------------------------------------
            unit: str = "um",
            pixel_size: Optional[float] = None,           # height maps, in `unit`
            base_height: float = 0.0,                     # height maps, in `unit`
            run_preprocess: bool = True,
            strict: bool = False,
            ground_truth_path: str | Path | None = None,
            optimize: bool = False,
            motion: Optional[MotionParameters] = None,
            debug_plot_dir: str | Path | None = None,
            # --- power-user override -----------------------------------------
            params: JobParameters | SlicingParameters | None = None,
    ):
        super().__init__()

        # ------------------------------------------------------------------
        # Fail fast: validate cheap things now, do NO expensive work here
        # (work order §3.2). Slicing runs lazily on first access.
        # ------------------------------------------------------------------
        if not isinstance(center, Point2D):
            raise TypeError(
                f"center must be Point2D/Point3D, got {type(center).__name__}")
        if isinstance(center, Point3D):
            self.center: Point3D = center
        else:
            self.center = Point3D(X=center.X, Y=center.Y, Z=0.0)

        if unit not in UM_PER_UNIT:
            raise ValueError(
                f"Unknown unit '{unit}'. Known: {sorted(UM_PER_UNIT)}")
        if isinstance(source, (str, Path)):
            src_path = Path(source)
            if not src_path.exists():
                raise FileNotFoundError(f"Geometry source not found: {src_path}")
            self.source: Any = src_path
        elif isinstance(source, (np.ndarray, trimesh.Trimesh)):
            self.source = source
        else:
            raise TypeError(
                "source must be a path, a 2D numpy height map or a "
                f"trimesh.Trimesh, got {type(source).__name__}")

        if velocity > 25_000:
            # Mirror IFOV_Lines' hard limit, but fail at construction time
            # instead of deep inside program generation.
            raise ValueError(
                f"Velocity value {velocity} exceeds 25 mm/s "
                "(IFOV_Lines limit).")
        self.velocity = velocity
        self.power = power
        self.objective = objective
        if voxel_model is not None and power is None:
            raise ValueError("Voxel-aware slicing needs the laser power of the structure (power=...).")
        self.voxel_model = voxel_model
        laser = LaserParameters(scan_speed_um_s=self._velocity_um_s(velocity),
                                **({"power_mw": float(power)} if power is not None else {}))

        self.unit = unit
        self.pixel_size = pixel_size
        self.base_height = base_height
        self.run_preprocess = run_preprocess
        self.strict = strict
        self.ground_truth_path = ground_truth_path
        self.optimize = optimize
        self.debug_plot_dir = (Path(debug_plot_dir)
                               if debug_plot_dir is not None else None)

        # ------------------------------------------------------------------
        # Parameter precedence (work order §3.5, A5)
        # ------------------------------------------------------------------
        passed_kwargs = {
            "hatch_size": hatch_size,
            "slice_size": slice_size,
            "hatch_strategy": hatch_strategy,
            "hatch_angle_deg": hatch_angle_deg,
            "contour_offset_um": contour_offset_um,
            "num_contour_lines": num_contour_lines,
            "spacing_mode": spacing_mode,
            "voxel_overlap": voxel_overlap,
        }
        explicitly_passed = {k: v for k, v in passed_kwargs.items()
                             if v is not _UNSET}

        if params is not None:
            if explicitly_passed:
                log.warning(
                    "Model3D_Slicer: `params` object given — ignoring "
                    "conflicting convenience kwargs %s (precedence rule A5).",
                    sorted(explicitly_passed))
            if isinstance(params, JobParameters):
                self.params: JobParameters = params
            elif isinstance(params, SlicingParameters):
                self.params = JobParameters(slicing=params, laser=laser)
            else:
                raise TypeError(
                    "params must be JobParameters or SlicingParameters, "
                    f"got {type(params).__name__}")
        else:
            merged = dict(_SLICING_KWARG_DEFAULTS)
            merged.update(explicitly_passed)
            if merged["slice_size"] <= 0:
                raise ValueError(f"slice_size must be > 0, got {merged['slice_size']}")
            if merged["hatch_size"] <= 0:
                raise ValueError(f"hatch_size must be > 0, got {merged['hatch_size']}")
            self.params = JobParameters(
                slicing=SlicingParameters(
                    layer_height_um=merged["slice_size"],
                    hatch_spacing_um=merged["hatch_size"],
                    hatch_strategy=merged["hatch_strategy"],
                    hatch_angle_deg=merged["hatch_angle_deg"],
                    contour_offset_um=merged["contour_offset_um"],
                    num_contour_lines=merged["num_contour_lines"],
                    spacing_mode=merged["spacing_mode"],
                    voxel_overlap=merged["voxel_overlap"],
                ),
                laser=laser,
            )

        self.motion = motion or MotionParameters(
            mark_speed_um_s=self.params.laser.scan_speed_um_s)

        # Lazy state --------------------------------------------------------
        self._job: Optional[ToolpathJob] = None
        self._recenter_offset_um: Optional[tuple[float, float, float]] = None
        self._skipped: dict[str, int] = {}

    # ----------------------------------------------------------------------
    # DrawableObject contract
    # ----------------------------------------------------------------------

    @property
    def center_point(self) -> Point3D:
        """Structure-local centre — used by the experiment for placement."""
        return self.center

    def iterate_layers(
            self,
            coordinate_system: CoordinateSystem,
            plot_name: Optional[str] = None,
    ) -> Iterator[DrawableAeroBasicProgram]:
        """Yield one IFOV program per printable layer (work order §3.4).

        The experiment enumerates these yields and writes one
        ``program_<name>.<layer_id>.txt`` per element, then concatenates —
        exactly the grating flow, with one layer = one IFOV block.

        ``plot_name`` is accepted for signature compatibility with
        ``DrawableObject.draw_on`` but currently unused.
        """
        del plot_name  # accepted for draw_on compatibility, not used (yet)
        job = self.toolpath_job
        self._skipped = {}

        for group in job.groups:
            if group.z_um is None:      # shell groups: stage 2 (work order §4)
                self._count_skipped(f"group:{group.kind}", len(group.elements))
                continue

            reference_point = Point3D(
                X=self.center.X,
                Y=self.center.Y,
                Z=self.center.Z + float(group.z_um),
            )

            # Route IR elements to the two leaf typesetters (stage 2,
            # work order §4). The IR element order is already the print
            # order from docs/01 §6 — group_from_layer emits contour rings
            # first (outer → inner, as produced by extract_contour_paths),
            # then infill lines — so we only have to preserve it.
            lines: list[list[Point2D]] = []
            polylines: list[list[Point2D]] = []
            closed_flags: list[bool] = []
            for element in group.elements:
                if (element.role == ROLE_INFILL
                        and not element.closed
                        and element.n_vertices == 2):
                    # Plain infill segment → IFOV_Lines (laser toggles per
                    # segment). Note: hatch_strategy="concentric" also lands
                    # here — the strategy emits its rings as 2-point infill
                    # segments, not as closed paths.
                    p0, p1 = element.points[0], element.points[1]
                    lines.append([
                        Point2D(X=float(p0[0]), Y=float(p0[1])),
                        Point2D(X=float(p1[0]), Y=float(p1[1])),
                    ])
                else:
                    # Contour/shell rings and multi-vertex paths →
                    # IFOV_PolyLines (one continuous laser-on pass per path,
                    # docs/01 §2.2 — no switching at every corner).
                    polylines.append([
                        Point2D(X=float(p[0]), Y=float(p[1]))
                        for p in element.points
                    ])
                    closed_flags.append(bool(element.closed))

            if not lines and not polylines:   # skip empty layers (§3.7)
                continue

            layer_program = DrawableAeroBasicProgram(coordinate_system)

            # Deliberately NOT leaf.draw_on(...): draw_on's signature is
            # (coordinate_system, plot_name=None) and swallows `objective`,
            # which would silently force the 63x IFOV configuration (verified
            # against base.py — work order §3.4/§6). Calling iterate_layers
            # directly is exactly what draw_on does internally, with the
            # objective threaded through correctly.

            # Contours first (outer → inner), then infill — docs/01 §6.
            if polylines:
                ifov_polylines = IFOV_PolyLines(
                    reference_point=reference_point,
                    polylines=polylines,
                    velocity=self.velocity,
                    power=self.power,
                    closed=closed_flags,
                )
                for sub_program in ifov_polylines.iterate_layers(
                        coordinate_system, objective=self.objective):
                    layer_program.add_programm(sub_program)

            if lines:
                ifov_lines = IFOV_Lines(
                    reference_point=reference_point,
                    lines=lines,
                    velocity=self.velocity,
                    power=self.power,
                )
                for sub_program in ifov_lines.iterate_layers(
                        coordinate_system, objective=self.objective):
                    layer_program.add_programm(sub_program)

            yield layer_program

        if self._skipped:
            log.warning(
                "Model3D_Slicer: %d element(s) not rendered: %s.",
                sum(self._skipped.values()), self.skipped_elements_report())

    # ----------------------------------------------------------------------
    # Slicing (lazy, cached) — work order §3.2
    # ----------------------------------------------------------------------

    @property
    def toolpath_job(self) -> ToolpathJob:
        """The sliced job (IR). Computed on first access, then cached.

        If ``debug_plot_dir`` is set, a per-layer PNG flipbook of the IR is
        written once, right after slicing (docs/05) — the same cached job
        that ``iterate_layers`` translates, so plot and print never diverge.
        """
        if self._job is None:
            self._job = self._run_slicer()
            if self.debug_plot_dir is not None:
                self._write_debug_plots(self._job)
        return self._job

    def _write_debug_plots(self, job: ToolpathJob) -> None:
        """Write the layer flipbook to ``debug_plot_dir``.

        Debug-only side channel: any failure here (missing matplotlib,
        full disk, ...) is logged and swallowed — a broken plot must never
        abort a print run. The import is lazy so matplotlib stays an
        optional dependency of the debug path, not of slicing.
        """
        try:
            from nanofactorysystem.aerobasic.slicer.visualization import (
                plot_job_layers)
            written = plot_job_layers(job, self.debug_plot_dir)
            log.info("Model3D_Slicer: wrote %d layer plots to %s",
                     len(written), self.debug_plot_dir)
        except Exception:
            log.exception(
                "Model3D_Slicer: layer plotting failed (debug_plot_dir=%s) "
                "— continuing without plots.", self.debug_plot_dir)

    def _run_slicer(self) -> ToolpathJob:
        """preprocess → re-center → slice+hatch(+optimize) → time estimate."""
        pre_report_dict: Optional[dict] = None

        # -- stage 0: obtain a µm mesh ------------------------------------
        if isinstance(self.source, trimesh.Trimesh):
            # Copy: never mutate a caller-owned mesh via re-centering.
            mesh = self.source.copy()
            # Honor `unit` for direct Trimesh input as well (least surprise:
            # "unit describes the source"). slice_geometry itself would
            # assume µm and silently ignore the kwarg. Default "um" → 1.0.
            from nanofactorysystem.aerobasic.slicer import units as _units
            scale = _units.scale_to_um(self.unit)
            if scale != 1.0:
                mesh.apply_scale(scale)
            source_name = "<in-memory mesh>"
        elif self.run_preprocess:
            result = _preprocess.run(
                self.source,
                unit=self.unit,
                pixel_size=self.pixel_size,
                base_height=self.base_height,
                strict=self.strict,
                ground_truth_path=self.ground_truth_path,
            )
            mesh = result.mesh
            pre_report_dict = result.report.to_dict()
            source_name = result.report.source
        else:
            from nanofactorysystem.aerobasic.slicer import (
                geometry_io as _geometry_io, units as _units)
            scale = _units.scale_to_um(self.unit)
            mesh = _geometry_io.load_geometry(
                self.source, unit_scale=scale,
                pixel_size_um=(_units.to_um(self.pixel_size, self.unit)
                               if self.pixel_size is not None else None),
                base_height_um=_units.to_um(self.base_height, self.unit))
            source_name = (str(self.source)
                           if not isinstance(self.source, np.ndarray)
                           else "<height map>")

        # -- re-centering: make the IR structure-local (work order §3.3) --
        bounds = mesh.bounds  # (2, 3): [[minx,miny,minz],[maxx,maxy,maxz]]
        cx = float((bounds[0, 0] + bounds[1, 0]) / 2.0)
        cy = float((bounds[0, 1] + bounds[1, 1]) / 2.0)
        z0 = float(bounds[0, 2])
        mesh.apply_translation([-cx, -cy, -z0])
        self._recenter_offset_um = (cx, cy, z0)

        # -- slice + hatch (+ optimize) on the centred Trimesh ------------
        # Passing a Trimesh makes slice_geometry skip its own preprocessor,
        # so nothing runs twice (verified in pipeline.py stage 0).
        job = slice_geometry(
            mesh,
            self.params,
            optimize=self.optimize,
            motion=self.motion,
            voxel_model=self.voxel_model,
        )
        job.source_file = source_name
        if pre_report_dict is not None:
            job.meta["preprocess"] = pre_report_dict
        job.meta["recenter_offset_um"] = {
            "x": cx, "y": cy, "z": z0,
            "note": ("subtracted from the source mesh so the IR is "
                     "structure-local: footprint bbox centre -> (0,0), "
                     "base -> z=0"),
        }
        log.info("Model3D_Slicer sliced %s | %s | est. %.2f s print time",
                 source_name, job.summary(),
                 job.meta["time_estimate"]["total_s"])
        return job

    # ----------------------------------------------------------------------
    # Storage / provenance — work order §3.6, §5
    # ----------------------------------------------------------------------

    def save_job(self, path: str | Path) -> Path:
        """Persist the sliced job as HDF5 (canonical scientific artifact).

        Thin delegate to ``slicer.storage.save_job``. The *experiment* decides
        when and where to call this (docs/INTEGRATION §4) — this class never
        auto-writes. Suggested target: the structure folder, next to the
        rendered ``program_*.txt`` files, e.g. ``<structure>/job.h5``.
        """
        estimate = estimate_toolpath(self.toolpath_job, self.motion)
        return _storage.save_job(self.toolpath_job, path,
                                 time_estimate=estimate)

    @property
    def estimated_print_time_s(self) -> float:
        """Total estimated print time in seconds (slicer motion model)."""
        return float(self.toolpath_job.meta["time_estimate"]["total_s"])

    def skipped_elements_report(self) -> dict[str, int]:
        """Elements not rendered, keyed by category (currently only shell
        groups, which have no per-layer z). Populated during
        ``iterate_layers``. Empty dict = everything was printed.
        """
        return dict(self._skipped)

    def _count_skipped(self, key: str, n: int) -> None:
        self._skipped[key] = self._skipped.get(key, 0) + n

    def to_json(self) -> dict[str, Any]:
        """Reproducible provenance for the experiment's structure config.

        Overrides the introspective ``DrawableObject.to_json`` default, which
        would stringify the Trimesh / JobParameters lossily and carry no
        slicer provenance. No mesh and no job object are embedded — the IR
        itself belongs in ``job.h5`` (see ``save_job``); this JSON is the
        *what-with-which-recipe* record (work order §3.6, §5.3).
        """
        job = self.toolpath_job
        source = (str(self.source) if isinstance(self.source, Path)
                  else "<height map>" if isinstance(self.source, np.ndarray)
                  else "<in-memory mesh>")
        return {
            "type": self.__class__.__name__,
            "source": source,
            "unit": self.unit,
            "center": self.center.to_json(),
            "objective": self.objective,
            "velocity": self.velocity,
            "power": self.power,
            "params": job.params.to_dict(),
            "recipe": job.recipe,
            "optimized": bool(self.optimize),
            "time_estimate": job.meta["time_estimate"],
            "preprocess": job.meta.get("preprocess"),
            "recenter_offset_um": job.meta.get("recenter_offset_um"),
            "n_groups": len(job.groups),
            "n_elements": job.n_elements,
            "mark_length_um": job.mark_length_um,
            "voxel": job.meta.get("voxel"),
        }

    # ----------------------------------------------------------------------
    # helpers
    # ----------------------------------------------------------------------

    @staticmethod
    def _velocity_um_s(velocity: float) -> float:
        """Grating velocity convention → µm/s for the slicer time model.

        Mirrors the ``IFOV_Lines`` heuristic: 500–25000 is assumed to be µm/s
        (IFOV_Lines divides by 1000 to get mm/s); smaller values are assumed
        to already be mm/s.
        """
        if 500 <= velocity <= 25_000:
            return float(velocity)
        return float(velocity) * 1000.0

    def __repr__(self) -> str:
        src = (self.source.name if isinstance(self.source, Path)
               else type(self.source).__name__)
        sliced = (f", {len(self._job.groups)} layers sliced"
                  if self._job is not None else ", not sliced yet")
        return (f"{self.__class__.__name__}({src} at {self.center}"
                f"{sliced})")
