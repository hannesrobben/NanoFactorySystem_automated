"""
Drawings Module
===============
Provides drawable objects for 2PP fabrication programs.

This module contains:
- Base classes (DrawableObject, DrawableAeroBasicProgram)
- Line primitives (XLines, YLines, PolyLine, PolyLines, etc.)
- 3D structures (Rectangle3D, Stair, Corner)
- Height function structures (Gratings, Lenses, DOEs)
- Standalone modules (Apertures, HatchGenerator, LaserSegments)
- Tile management for large structures

Author: PhoenixD / Hannes Robben
"""

# =============================================================================
# BASE CLASSES
# =============================================================================
from .base import (
    DrawableAeroBasicProgram,
    IFOV_AeroBasicProgram,
    DrawableObject,
    DrawablePoint,
    VoidStructure,
)

# =============================================================================
# LINE PRIMITIVES AND BASIC STRUCTURES
# =============================================================================
from .lines import (
    IFOV_Lines,
    XLines,
    YLines,
    ZLines,
    PolyLine,
    PolyLines,
    Rectangle2D,
    Rectangle3D,
    Stair,
    Corner,
)

# =============================================================================
# TILE MANAGEMENT
# =============================================================================
from .tile_manager import (
    TileManager,
    TilePlotter,
    PlotSettings,
)

# =============================================================================
# STANDALONE MODULES (Reusable by Rectangle3D, etc.)
# =============================================================================
from .apertures import Apertures

from .laser_segments import (
    LaserSegment,
    LaserSegments,
    LaserSegmentsConfig,
    SortingStrategy,
)

from .hatch_generator import (
    HatchGenerator,
    HatchConfig,
)

from nanofactorysystem.aerobasic.programs.drawings.height_function_structures.height_functions import HeightFunctions

# =============================================================================
# HEIGHT FUNCTION STRUCTURES (use standalone modules internally)
# =============================================================================
from .height_function_structures import (
    # Main structure classes
    HeightFunctionStructure,
    SinusoidalGrating,
    BinaryGrating,
    BlazedGrating,
    TriangularGrating,
    CrossedGrating,
    FresnelLens,
    CustomHeightFunctionStructure,

    # Slicing (structure-specific)
    TileAwareSlicer,
    SlicerConfig,
    SliceResult,
    TileSliceResult,
)


# =============================================================================
# IFOV Structures
# =============================================================================
from .ifov_gratings import (
    Rectangle2D_IFOV,
    Rectangle3D_IFOV,
    BinaryGrating_IFOV)


# =============================================================================
# PUBLIC API
# =============================================================================
__all__ = [
    # Base
    "DrawableAeroBasicProgram",
    "DrawableObject",
    "DrawablePoint",
    "VoidStructure",
    "IFOV_AeroBasicProgram",

    # Lines
    "XLines",
    "YLines",
    "ZLines",
    "IFOV_Lines",
    "PolyLine",
    "PolyLines",
    "Rectangle2D",
    "Rectangle3D",
    "Stair",
    "Corner",

    # Tile Management
    "TileManager",
    "TilePlotter",
    "PlotSettings",

    # Standalone Modules (for Rectangle3D, etc.)
    "Apertures",
    "LaserSegment",
    "LaserSegments",
    "LaserSegmentsConfig",
    "SortingStrategy",
    "HatchGenerator",
    "HatchConfig",
    "HeightFunctions",

    # Height Function Structures
    "HeightFunctionStructure",
    "SinusoidalGrating",
    "BinaryGrating",
    "BlazedGrating",
    "TriangularGrating",
    "CrossedGrating",
    "FresnelLens",
    "CustomHeightFunctionStructure",

    # Slicing
    "TileAwareSlicer",
    "SlicerConfig",
    "SliceResult",
    "TileSliceResult",

    # IFOV Structures
    "BinaryGrating_IFOV",
    "Rectangle3D_IFOV"
]