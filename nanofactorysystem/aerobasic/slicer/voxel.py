# voxel.py
"""Voxel-aware slicing parameters (T54).

With a known voxel size (lateral width, axial height) the slicer compensates
the enlargement of the printed part by the voxel:

* contours are offset inward by half the voxel width
  (``SlicingParameters.contour_offset_um``),
* the first and the last slice lie half a voxel height inside the bottom and
  top surface (``SlicingParameters.voxel_height_um``, see
  ``slicing.compute_z_levels``),
* the hatch and layer spacing follow the spacing mode:
  ``VOXEL_OVERLAP`` derives both from the voxel size and an overlap ratio,
  ``STATIC_HATCHING`` keeps the given spacing and warns about gaps between
  neighbouring lines or layers.

Without voxel data nothing changes. The slicer only depends on the
:class:`VoxelModel` protocol; the database-backed model lives in
``nanofactorysystem.voxel.model``.
"""
from __future__ import annotations

import dataclasses
import enum
import logging
from dataclasses import dataclass
from typing import Any, Optional, Protocol

from .parameters import JobParameters

log = logging.getLogger(__name__)


class SpacingMode(str, enum.Enum):
    """How hatch and layer spacing are chosen when voxel data exists."""

    VOXEL_OVERLAP = "voxel_overlap"      # spacing = voxel size * (1 - overlap)
    STATIC_HATCHING = "static_hatching"  # the given spacing; gaps only warned about

    @classmethod
    def parse(cls, value: "SpacingMode | str") -> "SpacingMode":
        """Accept a member, its value or its name."""
        if isinstance(value, cls):
            return value
        try:
            return cls(str(value).lower())
        except ValueError:
            return cls[str(value).upper()]


class VoxelSizeLike(Protocol):
    """What the slicer reads from a voxel size (e.g. ``voxel.VoxelSize``)."""

    width_um: Optional[float]
    height_um: Optional[float]


class VoxelModel(Protocol):
    """Voxel width and height for laser parameters.

    Implementations: ``nanofactorysystem.voxel.model.NoVoxelData``,
    ``DatabaseVoxelModel`` (measured data) and ``FixedVoxelModel``.
    """

    def voxel_size(self, power_mw: float, velocity_um_s: float) -> Optional[VoxelSizeLike]:
        """The voxel size, or None without data for these parameters."""
        ...

    def describe(self) -> dict[str, Any]:
        """JSON-compatible description of the model for the metadata."""
        ...


@dataclass(frozen=True)
class VoxelContext:
    """Voxel information handed to the hatching strategies.

    Attributes:
        model: The voxel model, so that strategies can query other laser
            parameters (adaptive strategies, F7).
        width_um / height_um: Voxel size for the job's laser parameters
            (None if unknown).
        power_mw / velocity_um_s: The laser parameters of the job.
    """
    model: VoxelModel
    width_um: Optional[float]
    height_um: Optional[float]
    power_mw: float
    velocity_um_s: float


@dataclass(frozen=True)
class VoxelCompensation:
    """Result of :func:`compensate`: the parameters to slice with and a report."""
    params: JobParameters
    context: Optional[VoxelContext]
    report: dict[str, Any]


def compensate(params: JobParameters, model: Optional[VoxelModel]) -> VoxelCompensation:
    """Adapt the slicing parameters to the voxel size of the job's laser parameters.

    The spacing mode and the overlap ratio are taken from
    ``params.slicing.spacing_mode`` and ``params.slicing.voxel_overlap``.

    Args:
        params: Parameters as given by the user.
        model: Voxel model; None or a model without data keeps ``params``.

    Returns:
        The parameters to slice with, the context for the hatching strategies
        and a JSON-compatible report of the values used (stored in
        ``job.meta["voxel"]``).
    """
    mode = SpacingMode.parse(params.slicing.spacing_mode)
    overlap = params.slicing.voxel_overlap
    power, velocity = params.laser.power_mw, params.laser.scan_speed_um_s
    report: dict[str, Any] = {"model": model.describe() if model is not None else None,
                              "power_mw": power, "velocity_um_s": velocity,
                              "mode": mode.value, "overlap": overlap, "width_um": None, "height_um": None,
                              "warnings": []}
    size = model.voxel_size(power, velocity) if model is not None else None
    if size is None or (size.width_um is None and size.height_um is None):
        return VoxelCompensation(params, None, report)

    width, height = size.width_um, size.height_um
    report.update(width_um=width, height_um=height,
                  width_method=getattr(size, "width_method", ""), height_method=getattr(size, "height_method", ""))
    slicing = params.slicing
    changes: dict[str, Any] = {}
    if width is not None:
        if slicing.contour_offset_um > 0:
            log.info("Explicit contour_offset_um=%g kept (half voxel width: %g)",
                     slicing.contour_offset_um, width / 2)
        else:
            changes["contour_offset_um"] = width / 2
        if mode == SpacingMode.VOXEL_OVERLAP:
            changes["hatch_spacing_um"] = width * (1 - overlap)
        elif slicing.hatch_spacing_um > width:
            report["warnings"].append(
                f"hatch spacing {slicing.hatch_spacing_um:g} um is larger than the voxel width {width:g} um: "
                f"gaps between neighbouring lines")
    if height is not None:
        changes["voxel_height_um"] = height
        if mode == SpacingMode.VOXEL_OVERLAP:
            changes["layer_height_um"] = height * (1 - overlap)
        elif slicing.layer_height_um > height:
            report["warnings"].append(
                f"layer height {slicing.layer_height_um:g} um is larger than the voxel height {height:g} um: "
                f"gaps between neighbouring layers")
    for warning in report["warnings"]:
        log.warning("Voxel-aware slicing: %s", warning)

    slicing = dataclasses.replace(slicing, **changes)
    voxel_size_um = (width if width is not None else params.voxel_size_um[0],
                     width if width is not None else params.voxel_size_um[1],
                     height if height is not None else params.voxel_size_um[2])
    report["slicing"] = {"layer_height_um": slicing.layer_height_um, "hatch_spacing_um": slicing.hatch_spacing_um,
                         "contour_offset_um": slicing.contour_offset_um, "voxel_height_um": slicing.voxel_height_um}
    context = VoxelContext(model, width, height, power, velocity)
    return VoxelCompensation(dataclasses.replace(params, slicing=slicing, voxel_size_um=voxel_size_um),
                             context, report)
