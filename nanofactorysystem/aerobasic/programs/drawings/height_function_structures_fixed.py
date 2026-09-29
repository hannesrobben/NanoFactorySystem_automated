"""
Height Function Structures - Integration Module for NanoFactorySystem

This module provides height-function-based structures (sinusoidal gratings,
blazed gratings, etc.) that integrate with the existing DrawableObject system.

Features:
- Arbitrary height functions z(x,y)
- Automatic slicing and hatching
- Seamless stitching integration
- Compatible with existing iterate_layers() workflow

Usage:
    from height_function_structures import SinusoidalGrating, HeightFunctionStructure

    grating = SinusoidalGrating(
        center=Point3D(0, 0, 0),
        width=100, length=100,
        period=2.0, height=1.0,
        grating_angle_deg=30,
        hatch_size=0.3, slice_size=0.2,
        velocity=1000, acceleration=10000
    )

    for program in grating.iterate_layers(coordinate_system):
        # Execute program...
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Callable, Iterator, List, Tuple, Optional, Dict, Any
from enum import Enum
import numpy as np

from skimage.measure import label, regionprops, find_contours

# Import from nanofactorysystem
from .base import DrawableObject, DrawableAeroBasicProgram
from nanofactorysystem.aerobasic.programs.drawings.lines import PolyLines, HatchingDirection, Rectangle3D
from nanofactorysystem.devices.coordinate_system import CoordinateSystem, Point2D, Point3D


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class HeightFunctionConfig:
    """Configuration for height-function-based structures"""
    hatch_size: float
    slice_size: float
    velocity: float
    acceleration: float

    # Slicing options
    slice_from_bottom: bool = True  # Start slicing from z_min

    # Hatching options
    hatch_angle_deg: float = 0.0
    alternating_hatch: bool = True
    hatch_angle_increment: float = 90.0

    # Stitching options
    fov_size: Tuple[float, float] = (150.0, 150.0)
    usable_fov_fraction: float = 0.85
    auto_stitch: bool = True

    # Resolution for polygon extraction
    grid_resolution: int = 500


# =============================================================================
# HEIGHT FUNCTIONS
# =============================================================================

class HeightFunctions:
    """Collection of standard height functions for gratings/DOEs"""

    @staticmethod
    def sinusoidal(period: float, height: float, angle_deg: float = 0,
                   z0: float = 0, phase_deg: float = 0) -> Callable:
        """
        Sinusoidal grating

        period: Gitterperiode (z.B. in Âµm)
        height: GesamthÃ¶he (z0 bis z0 + height)
        phase_deg: Phasenverschiebung in Grad [0, 360)
        z0: Minimaler z-Wert

        angle_deg: Rotation des gratings
        """
        theta = np.deg2rad(angle_deg)
        phase_frac = phase_deg / 360.0

        def f(x, y):
            s = x * np.cos(theta) + y * np.sin(theta)
            return z0 + (height / 2) * (1 + np.sin(2 * np.pi * (s / period + phase_frac)))

        return f
    '''
    def sinusoidal(period: float, height: float, angle_deg: float = 0,
                   z0: float = 0, phase: float = 0) -> Callable:
        """
        Sinusoidal grating: z = z0 + (h/2) * sin(2Ï€/L * s + Ï†)
        where s(x,y) = x*cos(Î¸) + y*sin(Î¸)
        """
        theta = np.deg2rad(angle_deg)

        def f(x, y):
            s = x * np.cos(theta) + y * np.sin(theta)
            return z0 + (height / 2) * np.sin(2 * np.pi / period * s + phase)

        return f'''

    @staticmethod
    def binary_grating(period: float, height: float, duty_cycle: float,
                       angle_deg: float = 0, z0: float = 0, phase_deg: float = 0) -> Callable:
        """Binary (step) grating

        period: Gitterperiode (z.B. in Âµm)
        duty_cycle: Breite des Plateaus in gleicher Einheit wie period
        phase_deg: Phasenverschiebung in Grad [0, 360)

        angle_deg: Rotation des gratings
        z0: Offset der HÃ¶he
        height: HÃ¶he des Gratingplateaus
        """
        theta = np.deg2rad(angle_deg)
        dc_frac = duty_cycle / period
        phase_frac = phase_deg / 360.0

        def f(x, y):
            s = x * np.cos(theta) + y * np.sin(theta)
            frac = np.mod(s / period + phase_frac, 1.0)
            return z0 + height * (frac < dc_frac).astype(float)

        return f
    '''
    def binary_grating(period: float, height: float, duty_cycle: float = 0.5,
                       angle_deg: float = 0, z0: float = 0) -> Callable:
        """Binary (step) grating"""
        theta = np.deg2rad(angle_deg)

        def f(x, y):
            s = x * np.cos(theta) + y * np.sin(theta)
            frac = np.mod(s, period) / period
            return z0 + height * (frac < duty_cycle).astype(float)

        return f'''

    @staticmethod
    def blazed_grating(period: float, height: float, angle_deg: float = 0,
                       z0: float = 0) -> Callable:
        """Blazed (sawtooth) grating"""
        theta = np.deg2rad(angle_deg)

        def f(x, y):
            s = x * np.cos(theta) + y * np.sin(theta)
            return z0 + height * np.mod(s, period) / period

        return f

    @staticmethod
    def triangular_grating(period: float, height: float, angle_deg: float = 0,
                           z0: float = 0) -> Callable:
        """Symmetric triangular grating"""
        theta = np.deg2rad(angle_deg)

        def f(x, y):
            s = x * np.cos(theta) + y * np.sin(theta)
            frac = np.mod(s, period) / period
            return z0 + height * (1 - 2 * np.abs(frac - 0.5))

        return f

    @staticmethod
    def crossed_gratings(period1: float, period2: float, height: float,
                         angle1_deg: float = 0, angle2_deg: float = 90,
                         z0: float = 0) -> Callable:
        """Crossed gratings (2D grating)"""
        theta1 = np.deg2rad(angle1_deg)
        theta2 = np.deg2rad(angle2_deg)

        def f(x, y):
            s1 = x * np.cos(theta1) + y * np.sin(theta1)
            s2 = x * np.cos(theta2) + y * np.sin(theta2)
            z1 = np.sin(2 * np.pi / period1 * s1)
            z2 = np.sin(2 * np.pi / period2 * s2)
            return z0 + (height / 2) * (z1 + z2) / 2

        return f

    @staticmethod
    def fresnel_lens(focal_length: float, wavelength: float, height: float,
                     cx: float = 0, cy: float = 0) -> Callable:
        """Fresnel lens (radial phase)"""

        def f(x, y):
            r2 = (x - cx) ** 2 + (y - cy) ** 2
            phase = np.pi * r2 / (wavelength * focal_length)
            return height * np.mod(phase, 2 * np.pi) / (2 * np.pi)

        return f


# =============================================================================
# APERTURES
# =============================================================================

class Apertures:
    """Standard apertures/boundaries"""

    @staticmethod
    def circular(radius: float, cx: float = 0, cy: float = 0) -> Callable:
        def f(x, y):
            return (x - cx) ** 2 + (y - cy) ** 2 <= radius ** 2

        return f

    @staticmethod
    def rectangular(width: float, height: float,
                    cx: float = 0, cy: float = 0) -> Callable:
        def f(x, y):
            return (np.abs(x - cx) <= width / 2) & (np.abs(y - cy) <= height / 2)

        return f

    @staticmethod
    def elliptical(a: float, b: float,
                   cx: float = 0, cy: float = 0) -> Callable:
        def f(x, y):
            return ((x - cx) / a) ** 2 + ((y - cy) / b) ** 2 <= 1

        return f

    @staticmethod
    def none() -> Callable:
        def f(x, y):
            return np.ones_like(x, dtype=bool)

        return f


# =============================================================================
# CORE ALGORITHMS
# =============================================================================

def _intersect_line_with_segment(p0: np.ndarray, d: np.ndarray,
                                 a: np.ndarray, b: np.ndarray) -> Optional[float]:
    """Line-segment intersection"""
    v = b - a
    det = d[0] * (-v[1]) - d[1] * (-v[0])

    if abs(det) < 1e-12:
        return None

    rhs = a - p0
    t = (rhs[0] * (-v[1]) - rhs[1] * (-v[0])) / det
    s = (d[0] * rhs[1] - d[1] * rhs[0]) / det

    if 0 <= s <= 1:
        return t
    return None


def _hatch_polygon(polygon: np.ndarray, angle_deg: float,
                   distance: float) -> List[Tuple[Tuple[float, float], Tuple[float, float]]]:
    """Generate hatch segments for a closed polygon (2D)"""
    poly = np.array(polygon)
    if len(poly) < 3:
        return []

    theta = np.deg2rad(angle_deg)
    d = np.array([np.cos(theta), np.sin(theta)])
    n = np.array([-d[1], d[0]])

    projections = poly @ n
    proj_min = projections.min()
    proj_max = projections.max()

    offsets = np.arange(proj_min, proj_max + distance, distance)

    segments = []
    edges = [(poly[i], poly[(i + 1) % len(poly)]) for i in range(len(poly))]

    for off in offsets:
        p0 = n * off

        ts = []
        for a, b in edges:
            t = _intersect_line_with_segment(p0, d, a, b)
            if t is not None:
                ts.append(t)

        if len(ts) < 2:
            continue

        ts.sort()

        filtered = [ts[0]]
        for t in ts[1:]:
            if abs(t - filtered[-1]) > 1e-9:
                filtered.append(t)
        ts = filtered

        for i in range(0, len(ts) - 1, 2):
            t0, t1 = ts[i], ts[i + 1]
            p_start = p0 + t0 * d
            p_end = p0 + t1 * d

            if np.linalg.norm(p_end - p_start) > 1e-9:
                segments.append((
                    (float(p_start[0]), float(p_start[1])),
                    (float(p_end[0]), float(p_end[1]))
                ))

    return segments


def _mask_to_polygons(mask: np.ndarray, xs: np.ndarray, ys: np.ndarray,
                      min_area: int = 10) -> List[np.ndarray]:
    """
    Convert binary mask to closed polygons.
    
    FIXED: Uses region bounding boxes instead of find_contours() for
    edge-touching regions. find_contours() returns degenerate lines
    (extent ≈ 0) for stripe-shaped regions that touch the evaluation bounds.
    """
    labels_img = label(mask.astype(np.uint8))
    regions = regionprops(labels_img)

    polygons = []
    for region in regions:
        if region.area < min_area:
            continue

        region_mask = (labels_img == region.label).astype(float)
        
        # Check if region touches any edge of the evaluation area
        touches_edge = (
            region.bbox[0] == 0 or                    # Top edge
            region.bbox[1] == 0 or                    # Left edge
            region.bbox[2] >= mask.shape[0] or        # Bottom edge
            region.bbox[3] >= mask.shape[1]           # Right edge
        )
        
        if touches_edge:
            # Use bounding box as rectangle polygon for edge-touching regions
            bbox = region.bbox  # (min_row, min_col, max_row, max_col)
            
            x_min_idx = max(0, bbox[1])
            x_max_idx = min(bbox[3], len(xs) - 1)
            y_min_idx = max(0, bbox[0])
            y_max_idx = min(bbox[2], len(ys) - 1)
            
            x_min = xs[x_min_idx]
            x_max = xs[x_max_idx]
            y_min = ys[y_min_idx]
            y_max = ys[y_max_idx]
            
            # Create closed rectangle polygon
            poly = np.array([
                [x_min, y_min],
                [x_max, y_min],
                [x_max, y_max],
                [x_min, y_max],
                [x_min, y_min]  # Close polygon
            ])
            
            polygons.append(poly)
        else:
            # Use find_contours for interior regions (works correctly here)
            contours = find_contours(region_mask, 0.5)

            for contour in contours:
                poly = []
                for yi, xi in contour:
                    x_coord = xs[0] + (xs[-1] - xs[0]) * xi / (len(xs) - 1)
                    y_coord = ys[0] + (ys[-1] - ys[0]) * yi / (len(ys) - 1)
                    poly.append([x_coord, y_coord])

                poly = np.array(poly)

                if len(poly) > 2 and not np.allclose(poly[0], poly[-1]):
                    poly = np.vstack([poly, poly[0]])

                if len(poly) >= 4:
                    polygons.append(poly)

    return polygons


def _clip_segments_to_bounds(segments: List[Tuple],
                             bounds: Tuple[float, float, float, float]
                             ) -> List[Tuple]:
    """Clip segments to rectangular bounds (x_min, x_max, y_min, y_max)"""
    x_min, x_max, y_min, y_max = bounds
    clipped = []

    for (x1, y1), (x2, y2) in segments:
        # Simple point-in-bounds check (could be improved with proper clipping)
        if (x_min <= x1 <= x_max and y_min <= y1 <= y_max and
                x_min <= x2 <= x_max and y_min <= y2 <= y_max):
            clipped.append(((x1, y1), (x2, y2)))
        else:
            # For now, skip segments that extend outside bounds
            pass

    return clipped


# =============================================================================
# SLICING ENGINE
# =============================================================================

@dataclass
class SliceData:
    """Data for a single slice/layer"""
    z_level: float
    polygons: List[np.ndarray]
    segments_2d: List[Tuple[Tuple[float, float], Tuple[float, float]]]

    def get_segments_3d(self) -> List[Tuple[Tuple[float, float, float], Tuple[float, float, float]]]:
        """Convert 2D segments to 3D with z-coordinate"""
        return [
            ((x1, y1, self.z_level), (x2, y2, self.z_level))
            for (x1, y1), (x2, y2) in self.segments_2d
        ]


class SlicingEngine:
    """Engine for slicing height functions into layers"""

    def __init__(self, config: HeightFunctionConfig):
        self.config = config

    def slice_height_function(
            self,
            height_func: Callable,
            x_range: Tuple[float, float],
            y_range: Tuple[float, float],
            z_min: float,
            z_max: float,
            aperture: Optional[Callable] = None
    ) -> List[SliceData]:
        """
        Slice a height function into layers with hatching.

        Returns list of SliceData objects, one per z-level.
        """
        cfg = self.config

        # Create evaluation grid
        xs = np.linspace(x_range[0], x_range[1], cfg.grid_resolution)
        ys = np.linspace(y_range[0], y_range[1], cfg.grid_resolution)
        X, Y = np.meshgrid(xs, ys)

        # Evaluate height function
        Z = height_func(X, Y)

        # Apply aperture if provided
        if aperture is not None:
            aperture_mask = aperture(X, Y)
            Z = np.where(aperture_mask, Z, np.nan)

        # Calculate z-levels
        n_slices = max(1, round((z_max - z_min) / cfg.slice_size))
        slice_size_opt = (z_max - z_min) / n_slices
        z_levels = np.linspace(z_min, z_max, n_slices + 1)

        slices = []

        for i, z_level in enumerate(z_levels):
            # Binary mask: where z >= z_level
            mask = (Z >= z_level) & ~np.isnan(Z)

            # Extract polygons
            polygons = _mask_to_polygons(mask, xs, ys, min_area=10)

            # Calculate hatch angle (optionally alternating)
            if cfg.alternating_hatch:
                hatch_angle = cfg.hatch_angle_deg + i * cfg.hatch_angle_increment
            else:
                hatch_angle = cfg.hatch_angle_deg

            # Generate hatch segments for each polygon
            all_segments = []
            for poly in polygons:
                segs = _hatch_polygon(poly, hatch_angle, cfg.hatch_size)
                all_segments.extend(segs)

            slices.append(SliceData(
                z_level=z_level,
                polygons=polygons,
                segments_2d=all_segments
            ))

        return slices


# =============================================================================
# TILE MANAGER (for stitching integration)
# =============================================================================

@dataclass
class TileBounds:
    """Bounds for a single tile"""
    x_min: float
    x_max: float
    y_min: float
    y_max: float
    center_x: float
    center_y: float

    @property
    def as_tuple(self) -> Tuple[float, float, float, float]:
        return (self.x_min, self.x_max, self.y_min, self.y_max)


class TileManager:
    """Manages tile generation for stitching"""

    def __init__(self, fov_size: Tuple[float, float], usable_fraction: float = 0.85):
        self.fov_width, self.fov_height = fov_size
        self.usable_fraction = usable_fraction
        self.tile_width = self.fov_width * usable_fraction
        self.tile_height = self.fov_height * usable_fraction

    def needs_stitching(self, width: float, height: float) -> bool:
        """Check if structure needs stitching"""
        return width > self.tile_width or height > self.tile_height

    def generate_tiles(self, x_range: Tuple[float, float],
                       y_range: Tuple[float, float]) -> List[TileBounds]:
        """Generate tiles for a given area"""
        x_min, x_max = x_range
        y_min, y_max = y_range

        width = x_max - x_min
        height = y_max - y_min

        if not self.needs_stitching(width, height):
            # Single tile
            return [TileBounds(
                x_min=x_min, x_max=x_max,
                y_min=y_min, y_max=y_max,
                center_x=(x_min + x_max) / 2,
                center_y=(y_min + y_max) / 2
            )]

        # Calculate number of tiles needed
        n_tiles_x = int(np.ceil(width / self.tile_width))
        n_tiles_y = int(np.ceil(height / self.tile_height))

        tiles = []
        for row in range(n_tiles_y):
            for col in range(n_tiles_x):
                tile_x_min = x_min + col * self.tile_width
                tile_x_max = min(tile_x_min + self.tile_width, x_max)
                tile_y_min = y_min + row * self.tile_height
                tile_y_max = min(tile_y_min + self.tile_height, y_max)

                tiles.append(TileBounds(
                    x_min=tile_x_min, x_max=tile_x_max,
                    y_min=tile_y_min, y_max=tile_y_max,
                    center_x=(tile_x_min + tile_x_max) / 2,
                    center_y=(tile_y_min + tile_y_max) / 2
                ))

        return tiles


# =============================================================================
# MAIN CLASS: HeightFunctionStructure
# =============================================================================

class HeightFunctionStructure(DrawableObject):
    """
    Base class for height-function-based structures.

    Integrates with existing DrawableObject interface and provides
    automatic slicing, hatching, and stitching.

    Subclasses should implement:
    - _create_height_function() -> Callable
    - _get_z_range() -> Tuple[float, float]
    """

    def __init__(
            self,
            center: Point2D | Point3D,
            width: float,
            length: float,
            *,
            hatch_size: float,
            slice_size: float,
            velocity: float,
            acceleration: float,
            aperture: Optional[Callable] = None,
            hatch_angle_deg: float = 0.0,
            alternating_hatch: bool = True,
            fov_size: Tuple[float, float] = (150.0, 150.0),
            usable_fov_fraction: float = 0.85,
            grid_resolution: int = 500
    ):
        super().__init__()
        self.center = center
        self.width = width
        self.length = length
        self.aperture = aperture

        # Store config
        self.config = HeightFunctionConfig(
            hatch_size=hatch_size,
            slice_size=slice_size,
            velocity=velocity,
            acceleration=acceleration,
            hatch_angle_deg=hatch_angle_deg,
            alternating_hatch=alternating_hatch,
            fov_size=fov_size,
            usable_fov_fraction=usable_fov_fraction,
            grid_resolution=grid_resolution
        )

        # Initialize engines
        self._slicing_engine = SlicingEngine(self.config)
        self._tile_manager = TileManager(fov_size, usable_fov_fraction)

    @property
    def center_point(self) -> Point2D:
        return self.center

    @property
    def structure_width(self) -> float:
        return self.width

    @property
    def structure_length(self) -> float:
        return self.length

    @property
    def x_range(self) -> Tuple[float, float]:
        return (self.center.X - self.width / 2, self.center.X + self.width / 2)

    @property
    def y_range(self) -> Tuple[float, float]:
        return (self.center.Y - self.length / 2, self.center.Y + self.length / 2)

    @property
    def bounding_box(self) -> Tuple[float, float, float, float]:
        """(x_min, x_max, y_min, y_max)"""
        return (*self.x_range, *self.y_range)

    @property
    def needs_stitching(self) -> bool:
        return self._tile_manager.needs_stitching(self.width, self.length)

    @abstractmethod
    def _create_height_function(self) -> Callable:
        """Create the height function z(x,y). Override in subclasses."""
        pass

    @abstractmethod
    def _get_z_range(self) -> Tuple[float, float]:
        """Get (z_min, z_max) of the structure. Override in subclasses."""
        pass

    def _slice_structure(self) -> List[SliceData]:
        """Perform slicing of the height function"""
        height_func = self._create_height_function()
        z_min, z_max = self._get_z_range()

        return self._slicing_engine.slice_height_function(
            height_func=height_func,
            x_range=self.x_range,
            y_range=self.y_range,
            z_min=z_min,
            z_max=z_max,
            aperture=self.aperture
        )

    def _segments_to_polylines(self, segments_3d: List[Tuple],
                               z_offset: float = 0) -> List[List[Dict]]:
        """Convert segments to PolyLines format"""
        lines = []
        for (x1, y1, z1), (x2, y2, z2) in segments_3d:
            line = [
                {"X": x1, "Y": y1, "Z": z1 + z_offset},
                {"X": x2, "Y": y2, "Z": z2 + z_offset}
            ]
            lines.append(line)
        return lines

    def iterate_layers_self_new(self, coordinate_system: CoordinateSystem) -> Iterator[DrawableAeroBasicProgram]:
        program = DrawableAeroBasicProgram(coordinate_system)

        # stitching process
        if self.needs_stitching:
            # subdivide structure into tiles
            tiles = self._tile_manager

            for tile in tiles:
                x_min, x_max, y_min, y_max = tile["tile_dimension"]  # get dimensions of tile
                length, width = tile["structure_dimension"]
                center_point_structure = tile["center_point_structure"]  # center point for the structure because there could be issues regarding the endtiles and the beginning of the printing process

                #move to center - absolut coordinate system with LINEAR movement

                if self.center.Z <= self.base_height:
                    socket = Rectangle3D(
                        center=self.center,
                        width=x_max-x_min,
                        length=self.structure_length,
                        height=self.base_height,
                        hatch_size=self.hatch_size,
                        slice_size=self.slice_size,
                        velocity=self.velocity,
                        acceleration=self.acceleration
                    )
                    yield from socket.iterate_layers(coordinate_system)


        '''
            if self.height == 0:
                return program
        
            n_layer = abs(round(self.height / self.slice_size)) + 1
            slice_size_opt = self.height / (n_layer - 1)
        
            hatching_direction = HatchingDirection.X
            for i in range(n_layer):
                z_offset = i * slice_size_opt
                rectangle = Rectangle2D(
                    center=self.center + Point3D(0, 0, z_offset),
                    width=self.width,
                    length=self.length,
                    hatch_size=self.hatch_size,
                    velocity=self.velocity,
                    acceleration=self.acceleration,
                    hatching_direction=hatching_direction
                )
                program = DrawableAeroBasicProgram(coordinate_system)
                program.LINEAR(Z=z_offset + self.center.Z)
                program.add_programm(rectangle.draw_on(coordinate_system))
                yield program
                hatching_direction = hatching_direction.flip()
        '''

    def iterate_layers(self, coordinate_system: CoordinateSystem) -> Iterator[DrawableAeroBasicProgram]:
        """
        Main entry point for layer iteration.

        Implements the workflow:
        1. Slice structure into z-levels
        2. For each z-level, generate hatch segments
        3. If stitching needed: clip to tiles and yield per-tile programs
        4. If no stitching: yield complete layer programs
        """
        # Get base Z from center
        base_z = self.center.Z if hasattr(self.center, 'Z') else 0

        # Perform slicing
        slices = self._slice_structure()

        if not self.needs_stitching:
            # Simple case: no stitching needed
            yield from self._iterate_layers_simple(slices, base_z, coordinate_system)
        else:
            # Stitching case: generate tiles and process each
            yield from self._iterate_layers_stitched(slices, base_z, coordinate_system)

    def _iterate_layers_simple(self, slices: List[SliceData], base_z: float,
                               coordinate_system: CoordinateSystem) -> Iterator[DrawableAeroBasicProgram]:
        """Iterate layers without stitching (TILE_FIRST equivalent for single tile)"""

        for slice_data in slices:
            if not slice_data.segments_2d:
                continue

            program = DrawableAeroBasicProgram(coordinate_system)

            # Move to Z level
            z_absolute = base_z + slice_data.z_level
            program.LINEAR(Z=z_absolute)

            # Convert segments to polylines format
            segments_3d = slice_data.get_segments_3d()
            lines = self._segments_to_polylines(segments_3d, z_offset=base_z)

            # Create PolyLines and add to program
            if lines:
                poly_lines = PolyLines(lines, F=self.config.velocity, E=self.config.acceleration)
                program.add_programm(poly_lines.draw_on(coordinate_system))

            yield program

    def _iterate_layers_stitched(self, slices: List[SliceData], base_z: float,
                                 coordinate_system: CoordinateSystem) -> Iterator[DrawableAeroBasicProgram]:
        """Iterate layers with stitching (TILE_FIRST strategy)"""

        # Generate tiles
        tiles = self._tile_manager.generate_tiles(self.x_range, self.y_range)

        # TILE_FIRST: Complete all layers for one tile before moving to next
        for tile_idx, tile in enumerate(tiles):
            # Move to tile center
            program = DrawableAeroBasicProgram(coordinate_system)
            program.comment(f"\n[Tile {tile_idx}] Moving to center ({tile.center_x:.2f}, {tile.center_y:.2f})")
            program.LINEAR(X=tile.center_x, Y=tile.center_y, F=self.config.velocity)
            yield program

            # Process all layers for this tile
            for slice_data in slices:
                if not slice_data.segments_2d:
                    continue

                # Clip segments to tile bounds
                clipped_segments = _clip_segments_to_bounds(
                    slice_data.segments_2d,
                    tile.as_tuple
                )

                if not clipped_segments:
                    continue

                program = DrawableAeroBasicProgram(coordinate_system)

                # Move to Z level
                z_absolute = base_z + slice_data.z_level
                program.LINEAR(Z=z_absolute)

                # Convert to 3D and then to polylines
                segments_3d = [
                    ((x1, y1, slice_data.z_level), (x2, y2, slice_data.z_level))
                    for (x1, y1), (x2, y2) in clipped_segments
                ]
                lines = self._segments_to_polylines(segments_3d, z_offset=base_z)

                if lines:
                    poly_lines = PolyLines(lines, F=self.config.velocity, E=self.config.acceleration)
                    program.add_programm(poly_lines.draw_on(coordinate_system))

                yield program


# =============================================================================
# CONCRETE IMPLEMENTATIONS
# =============================================================================

class SinusoidalGrating(HeightFunctionStructure):
    """
    Sinusoidal grating structure.

    z(x,y) = z0 + (h/2) * sin(2Ï€/L * s(x,y) + Ï†)
    where s = x*cos(Î¸) + y*sin(Î¸)
    """

    def __init__(
            self,
            center: Point2D | Point3D,
            width: float,
            length: float,
            period: float,
            height: float,
            grating_angle_deg: float = 0.0,
            phase: float = 0.0,
            base_height: float = 0.0,
            **kwargs
    ):
        super().__init__(center, width, length, **kwargs)
        self.period = period
        self.height = height
        self.grating_angle_deg = grating_angle_deg
        self.phase = phase
        self.base_height = base_height

    def _create_height_function(self) -> Callable:
        return HeightFunctions.sinusoidal(
            period=self.period,
            height=self.height,
            angle_deg=self.grating_angle_deg,
            z0=self.base_height + self.height / 2,  # Shift so minimum is at base_height
            phase=self.phase
        )

    def _get_z_range(self) -> Tuple[float, float]:
        return (self.base_height, self.base_height + self.height)

    @property
    def max_structure_height(self) -> float:
        return self.base_height + self.height

    @property
    def min_structure_height(self) -> float:
        return self.base_height


class BlazedGrating(HeightFunctionStructure):
    """
    Blazed (sawtooth) grating structure.

    z(x,y) = z0 + h * (s mod L) / L
    """

    def __init__(
            self,
            center: Point2D | Point3D,
            width: float,
            length: float,
            period: float,
            height: float,
            grating_angle_deg: float = 0.0,
            base_height: float = 0.0,
            **kwargs
    ):
        super().__init__(center, width, length, **kwargs)
        self.period = period
        self.height = height
        self.grating_angle_deg = grating_angle_deg
        self.base_height = base_height

    def _create_height_function(self) -> Callable:
        return HeightFunctions.blazed_grating(
            period=self.period,
            height=self.height,
            angle_deg=self.grating_angle_deg,
            z0=self.base_height
        )

    def _get_z_range(self) -> Tuple[float, float]:
        return (self.base_height, self.base_height + self.height)


class BinaryGrating(HeightFunctionStructure):
    """
    Binary (step) grating structure.
    """

    def __init__(
            self,
            center: Point2D | Point3D,
            width: float,
            length: float,
            period: float,
            height: float,
            duty_cycle: float = 0.5,
            grating_angle_deg: float = 0.0,
            base_height: float = 0.0,
            **kwargs
    ):
        super().__init__(center, width, length, **kwargs)
        self.period = period
        self.height = height
        self.duty_cycle = duty_cycle
        self.grating_angle_deg = grating_angle_deg
        self.base_height = base_height

    def _create_height_function(self) -> Callable:
        return HeightFunctions.binary_grating(
            period=self.period,
            height=self.height,
            duty_cycle=self.duty_cycle,
            angle_deg=self.grating_angle_deg,
            z0=self.base_height
        )

    def _get_z_range(self) -> Tuple[float, float]:
        return (self.base_height, self.base_height + self.height)


class CrossedGrating(HeightFunctionStructure):
    """
    Crossed (2D) grating structure.
    """

    def __init__(
            self,
            center: Point2D | Point3D,
            width: float,
            length: float,
            period1: float,
            period2: float,
            height: float,
            angle1_deg: float = 0.0,
            angle2_deg: float = 90.0,
            base_height: float = 0.0,
            **kwargs
    ):
        super().__init__(center, width, length, **kwargs)
        self.period1 = period1
        self.period2 = period2
        self.height = height
        self.angle1_deg = angle1_deg
        self.angle2_deg = angle2_deg
        self.base_height = base_height

    def _create_height_function(self) -> Callable:
        return HeightFunctions.crossed_gratings(
            period1=self.period1,
            period2=self.period2,
            height=self.height,
            angle1_deg=self.angle1_deg,
            angle2_deg=self.angle2_deg,
            z0=self.base_height
        )

    def _get_z_range(self) -> Tuple[float, float]:
        return (self.base_height - self.height / 2, self.base_height + self.height / 2)


class CustomHeightFunctionStructure(HeightFunctionStructure):
    """
    Structure with custom height function.

    Example:
        def my_height_func(x, y):
            return 0.5 + 0.3 * np.sin(2*np.pi*x/2) * np.cos(2*np.pi*y/2)

        structure = CustomHeightFunctionStructure(
            center=Point3D(0, 0, 0),
            width=100, length=100,
            height_function=my_height_func,
            z_min=0.2, z_max=0.8,
            hatch_size=0.3, slice_size=0.1,
            velocity=1000, acceleration=10000
        )
    """

    def __init__(
            self,
            center: Point2D | Point3D,
            width: float,
            length: float,
            height_function: Callable,
            z_min: float,
            z_max: float,
            **kwargs
    ):
        super().__init__(center, width, length, **kwargs)
        self._height_function = height_function
        self._z_min = z_min
        self._z_max = z_max

    def _create_height_function(self) -> Callable:
        return self._height_function

    def _get_z_range(self) -> Tuple[float, float]:
        return (self._z_min, self._z_max)


# =============================================================================
# EXAMPLE USAGE
# =============================================================================

if __name__ == '__main__':
    pass

    # This would be run in the actual nanofactorysystem environment
    # print("Height Function Structures Module")
    # print("=" * 60)
    # print(
"""
Usage Example:

    from height_function_structures import SinusoidalGrating
    from nanofactorysystem.devices.coordinate_system import Point3D, CoordinateSystem

    # Create grating
    grating = SinusoidalGrating(
        center=Point3D(0, 0, -2),
        width=100,     # Âµm
        length=100,    # Âµm
        period=2.0,    # Âµm
        height=1.0,    # Âµm
        grating_angle_deg=30,
        hatch_size=0.3,
        slice_size=0.2,
        velocity=1000,
        acceleration=10000
    )

    # Iterate and execute layers
    coord_system = CoordinateSystem()
    for program in grating.iterate_layers(coord_system):
        # Execute program on hardware...
        pass
    """