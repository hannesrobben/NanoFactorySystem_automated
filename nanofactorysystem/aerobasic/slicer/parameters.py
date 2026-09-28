# parameters.py
"""Process parameters for TPP slicing.

All spatial values are in micrometers (um), consistent with the HDF5
protocol (voxel_size_um, scan_speed in um/s). Input geometry is scaled
to um at load time (see geometry_io.load_geometry).
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass(frozen=True)
class LaserParameters:
    """Laser process parameters (stored as HDF5 metadata)."""
    power_mw: float = 50.0
    scan_speed_um_s: float = 10_000.0


@dataclass(frozen=True)
class SlicingParameters:
    """Geometric slicing/hatching parameters.

    Attributes:
        layer_height_um: Distance between slice planes.
        hatch_spacing_um: Distance between hatch lines within a layer.
        hatch_strategy: Name of a registered hatching strategy
            (see hatching.available_strategies()).
        hatch_angle_deg: Base hatch direction (0 = along X).
        contour_offset_um: Inward offset of the outline before hatching.
            Compensates for the lateral voxel radius so the printed part
            matches the design dimensions. 0 disables it.
        num_contour_lines: Perimeter lines to print before infill
            (like "walls" in FDM slicing). 0 = infill only.
        z_epsilon_um: Offset of the first slice plane above z_min. Slicing
            exactly at z_min hits the mesh tangentially and yields
            degenerate sections.
    """
    layer_height_um: float = 0.2
    hatch_spacing_um: float = 0.2
    hatch_strategy: str = "alternating"
    hatch_angle_deg: float = 0.0
    contour_offset_um: float = 0.0
    num_contour_lines: int = 0
    z_epsilon_um: float = 1e-3

    def __post_init__(self) -> None:
        if self.layer_height_um <= 0:
            raise ValueError("layer_height_um must be > 0")
        if self.hatch_spacing_um <= 0:
            raise ValueError("hatch_spacing_um must be > 0")
        if self.num_contour_lines < 0:
            raise ValueError("num_contour_lines must be >= 0")


@dataclass(frozen=True)
class JobParameters:
    """Everything needed to reproduce a slicing job."""
    slicing: SlicingParameters = field(default_factory=SlicingParameters)
    laser: LaserParameters = field(default_factory=LaserParameters)
    voxel_size_um: tuple[float, float, float] = (0.1, 0.1, 0.2)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
