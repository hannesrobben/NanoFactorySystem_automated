"""
Height Function Structures
==========================
Grating_63 and DOE structure classes for 2PP fabrication.

Uses standalone modules:
- apertures.py
- laser_segments.py
- hatch_generator.py
- height_functions.py
- tile_manager.py

Author: Hannes Robben
Date: 2025
"""
import datetime
from abc import abstractmethod
from typing import Callable, Iterator, List, Tuple, Optional, Dict, Any, Union
import warnings

# Import from nanofactorysystem
from nanofactorysystem.aerobasic import GalvoLaserOverrideMode, SingleAxis, WaitMode
from nanofactorysystem.aerobasic.programs.drawings.base import DrawableObject, DrawableAeroBasicProgram
from nanofactorysystem.devices.coordinate_system import CoordinateSystem, Point2D, Point3D

# Import from standalone modules
from nanofactorysystem.aerobasic.programs.drawings.height_function_structures.height_functions import HeightFunctions
from ..laser_segments import LaserSegments, LaserSegmentsConfig, SortingStrategy
from ..tile_manager import TileManager

# Import slicer
from .slicer import TileAwareSlicer, SlicerConfig, TileSliceResult
from ... import AeroBasicProgram


# =============================================================================
# BASE CLASS
# =============================================================================

class HeightFunctionStructure(DrawableObject):
    """
    Base class for height-function-based structures.
    
    Subclasses must implement:
    - _create_height_function() -> Callable
    - _get_z_range() -> Tuple[float, float]
    """

    def __init__(
            self,
            center: Union[Point2D, Point3D],
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
            hatch_angle_increment: float = 90.0,
            fov_size: Tuple[float, float] = (150.0, 150.0),
            usable_fov_fraction: float = 0.85,
            grid_resolution: int = 500
    ):
        super().__init__()

        self.center = center
        self.width = width
        self.length = length
        self.hatch_size = hatch_size
        self.slice_size = slice_size
        self.velocity = velocity
        self.acceleration = acceleration
        self.aperture = aperture
        self.hatch_angle_deg = hatch_angle_deg
        self.alternating_hatch = alternating_hatch
        self.hatch_angle_increment = hatch_angle_increment
        self.fov_size = fov_size
        self.usable_fov_fraction = usable_fov_fraction
        self.grid_resolution = grid_resolution

        if grid_resolution > 2000:
            warnings.warn(
                f"grid_resolution={grid_resolution} is very high. Consider 500-1000.",
                UserWarning
            )

        self._tile_manager: Optional[TileManager] = None
        self._slice_cache: Optional[List[TileSliceResult]] = None
        self._layer_to_tile_mapping: Optional[Dict[int, Dict]] = None

    @property
    def center_point(self) -> Point2D:
        if isinstance(self.center, Point3D):
            return Point2D(self.center.X, self.center.Y)
        return self.center

    @property
    def base_z(self) -> float:
        if isinstance(self.center, Point3D):
            return self.center.Z
        return 0.0

    @property
    def tile_manager(self) -> TileManager:
        if self._tile_manager is not None:
            return self._tile_manager

        self._tile_manager = TileManager(
            structure_size=(self.width, self.length),
            fov=self.fov_size,
            usable_fraction=self.usable_fov_fraction,
            center=self.center_point
        )
        self._tile_manager.calc_parameters()
        self._tile_manager.generate_tiles()

        return self._tile_manager

    @property
    def needs_stitching(self) -> bool:
        return self.tile_manager.needs_stitching()

    @property
    def n_tiles(self) -> int:
        return self.tile_manager.get_n_tiles_total()

    @abstractmethod
    def _create_height_function(self) -> Callable:
        pass

    @abstractmethod
    def _get_z_range(self) -> Tuple[float, float]:
        pass

    def _create_slicer_config(self) -> SlicerConfig:
        return SlicerConfig(
            slice_size=self.slice_size,
            hatch_size=self.hatch_size,
            hatch_angle_deg=self.hatch_angle_deg,
            alternating_hatch=self.alternating_hatch,
            hatch_angle_increment=self.hatch_angle_increment,
            velocity=self.velocity,
            acceleration=self.acceleration,
            grid_resolution=self.grid_resolution
        )

    def _slice_structure(self) -> List[TileSliceResult]:
        if self._slice_cache is not None:
            return self._slice_cache

        slicer = TileAwareSlicer(self._create_slicer_config())
        z_min, z_max = self._get_z_range()

        results = []
        for tile_info in self.tile_manager.get_tile_dict():
            tile_center = tuple(tile_info['center_tile'])

            # Create tile-specific functions
            base_func = self._create_height_function()
            structure_cx, structure_cy = self.center.X, self.center.Y
            offset_x = tile_center[0] - structure_cx
            offset_y = tile_center[1] - structure_cy

            def height_func(X, Y, ox=offset_x, oy=offset_y, bf=base_func):
                return bf(X + ox, Y + oy)

            if self.aperture is not None:
                def aperture_func(X, Y, ox=offset_x, oy=offset_y, ap=self.aperture):
                    return ap(X + ox, Y + oy)
            else:
                aperture_func = None

            result = slicer.slice_tile(
                tile_info=tile_info,
                height_func=height_func,
                z_min=z_min,
                z_max=z_max,
                base_z=self.base_z,
                aperture=aperture_func
            )
            results.append(result)

        self._slice_cache = results
        return results

    def create_move_tile_program(self, x, y, F=None):
        """
        x and y are in mm and velocity F is in mm/s
        """
        pgm = AeroBasicProgram()
        pgm.GALVO_LASER_OVERRIDE(GalvoLaserOverrideMode.OFF)
        pgm.MOVEINC(axis=SingleAxis.X, distance=x/1000, speed=F if F is not None else 10)
        pgm.MOVEINC(axis=SingleAxis.Y, distance=y/1000, speed=F if F is not None else 10)
        pgm.WAIT(WaitMode.MOVE_DONE)
        pgm.ABSOLUTE()

        return pgm


    def iterate_layers(
            self,
            coordinate_system: CoordinateSystem,
            strategy: str = "TILE_FIRST"
    ) -> Iterator[DrawableAeroBasicProgram]:
        """
        Generate programs for all layers.
        
        Args:
            coordinate_system: Coordinate system for transformations
            strategy: "TILE_FIRST" or "LAYER_FIRST"
        """
        investigation=True
        if investigation: start1 = datetime.datetime.now()
        tile_results = self._slice_structure()
        if investigation:
            end1 = datetime.datetime.now()
            print(f"TIME for calculating slice of structure:\t{(end1-start1).seconds}")


        if not tile_results:
            return

        if investigation: start2 = datetime.datetime.now()
        laser_config = LaserSegmentsConfig(
            velocity=self.velocity,
            acceleration=self.acceleration,
            sorting_strategy=SortingStrategy.SERPENTINE,
            use_acceleration_distance=True
        )
        if investigation:
            end2 = datetime.datetime.now()
            print(f"TIME for calculating laser segment config:\t{(end2-start2).seconds}")

        if strategy == "TILE_FIRST":
            iteration_order = self._generate_tile_first_order(tile_results)
        else:
            iteration_order = self._generate_layer_first_order(tile_results)
        # Initialising Mapping
        self._layer_to_tile_mapping = {}
        layer_counter = 0
        prev_tile_index = None

        if investigation: start3 = datetime.datetime.now()
        for tile_result, slice_result, layer_idx in iteration_order:
            if slice_result.is_empty:
                continue

            tile_x, tile_y = tile_result.tile_center
            self._layer_to_tile_mapping[layer_counter] = {
                'tile_index': tile_result.tile_index,
                'tile_center': (tile_x, tile_y),
                'layer_idx_in_tile': layer_idx
            }
            layer_program = DrawableAeroBasicProgram(coordinate_system)
            tile_x, tile_y = tile_result.tile_center

            layer_program.comment(
                f"\n; Tile {tile_result.tile_index}, Layer {layer_idx}, "
                f"Z={slice_result.z_absolute:.3f}, {strategy}, "
                f"X offset {tile_x}, y offset {tile_y}, "
            )

            # is_new_tile = (tile_result.tile_index != prev_tile_index)
            #
            # if is_new_tile:
            #     # create In-Between-Tile Movement
            #     tile_movement_program = self.create_move_tile_program(tile_x, tile_y, F=self.velocity)
            #     layer_program.add_programm(tile_movement_program)
            #     prev_tile_index = tile_result.tile_index

            layer_program.LINEAR(Z=slice_result.z_absolute)

            laser_segments = LaserSegments(
                segments=slice_result.segments,
                config=laser_config
            )

            for segment_program in laser_segments.iterate_layers(coordinate_system):
                layer_program.add_programm(segment_program)

            layer_program.GALVO_LASER_OVERRIDE(GalvoLaserOverrideMode.OFF)

            yield layer_program
            layer_counter += 1

        if investigation:
            end3 = datetime.datetime.now()
            print(f"TIME for iteration over all layers (writing programs):\t{(end3 - start3).seconds}")

    def _generate_tile_first_order(self, tile_results):
        for tile_result in tile_results:
            for layer_idx, slice_result in enumerate(tile_result.slices):
                yield (tile_result, slice_result, layer_idx)

    def _generate_layer_first_order(self, tile_results):
        if not tile_results:
            return
        max_layers = max(len(tr.slices) for tr in tile_results)
        for layer_idx in range(max_layers):
            for tile_result in tile_results:
                if layer_idx < len(tile_result.slices):
                    yield (tile_result, tile_result.slices[layer_idx], layer_idx)

    def get_tile_center_for_layer(self, layer_id: int) -> Tuple[float, float]:
        """Return the tile_center for the given layer_id."""
        if self._layer_to_tile_mapping is None:
            raise RuntimeError("iterate_layers() muss erst aufgerufen werden")

        if layer_id not in self._layer_to_tile_mapping:
            raise ValueError(f"Layer {layer_id} existiert nicht")

        return self._layer_to_tile_mapping[layer_id]['tile_center']

    def get_tile_info_for_layer(self, layer_id: int) -> Dict:
        """Return the complete tile info for the given layer_id."""
        if self._layer_to_tile_mapping is None:
            raise RuntimeError("iterate_layers() muss erst aufgerufen werden")

        return self._layer_to_tile_mapping.get(layer_id)

    def to_json(self) -> Dict[str, Any]:
        return {
            "__class__": self.__class__.__name__,
            "center_point": self.center_point.as_tuple(),
            "__init__": self._init_args(),
            "number tiles": self.n_tiles,
            "tiles": self.tile_manager.to_json()
        }

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(size={self.width}×{self.length}, tiles={self.n_tiles})"


# =============================================================================
# CONCRETE IMPLEMENTATIONS
# =============================================================================

class SinusoidalGrating(HeightFunctionStructure):
    """Sinusoidal grating structure."""

    def __init__(self, center, width, length, period, height,
                 grating_angle_deg=0.0, phase_deg=0.0, base_height=0.0, **kwargs):
        super().__init__(center, width, length, **kwargs)
        self.period = period
        self.height = height
        self.grating_angle_deg = grating_angle_deg
        self.phase_deg = phase_deg
        self.base_height = base_height

    def _create_height_function(self):
        return HeightFunctions.sinusoidal(
            period=self.period, height=self.height,
            angle_deg=self.grating_angle_deg, z0=self.base_height,
            phase_deg=self.phase_deg
        )

    def _get_z_range(self):
        return (self.base_height, self.base_height + self.height)


class BinaryGrating(HeightFunctionStructure):
    """Binary (step) grating structure."""

    def __init__(self, center, width, length, period, height,
                 duty_cycle=0.5, grating_angle_deg=0.0, phase_deg=0.0,
                 base_height=0.0, **kwargs):
        super().__init__(center, width, length, **kwargs)
        self.period = period
        self.height = height
        self.duty_cycle = duty_cycle / period if duty_cycle > 1.0 else duty_cycle
        self._duty_cycle_input = duty_cycle
        self.grating_angle_deg = grating_angle_deg
        self.phase_deg = phase_deg
        self.base_height = base_height

    def _create_height_function(self):
        return HeightFunctions.binary_grating(
            period=self.period, height=self.height,
            duty_cycle=self.duty_cycle, angle_deg=self.grating_angle_deg,
            z0=self.base_height, phase_deg=self.phase_deg
        )

    def _get_z_range(self):
        return (self.base_height, self.base_height + self.height)


class BlazedGrating(HeightFunctionStructure):
    """Blazed (sawtooth) grating structure."""

    def __init__(self, center, width, length, period, height,
                 grating_angle_deg=0.0, phase_deg=0.0, base_height=0.0, **kwargs):
        super().__init__(center, width, length, **kwargs)
        self.period = period
        self.height = height
        self.grating_angle_deg = grating_angle_deg
        self.phase_deg = phase_deg
        self.base_height = base_height

    def _create_height_function(self):
        return HeightFunctions.blazed_grating(
            period=self.period, height=self.height,
            angle_deg=self.grating_angle_deg, z0=self.base_height,
            phase_deg=self.phase_deg
        )

    def _get_z_range(self):
        return (self.base_height, self.base_height + self.height)


class TriangularGrating(HeightFunctionStructure):
    """Symmetric triangular grating structure."""

    def __init__(self, center, width, length, period, height,
                 grating_angle_deg=0.0, phase_deg=0.0, base_height=0.0, **kwargs):
        super().__init__(center, width, length, **kwargs)
        self.period = period
        self.height = height
        self.grating_angle_deg = grating_angle_deg
        self.phase_deg = phase_deg
        self.base_height = base_height

    def _create_height_function(self):
        return HeightFunctions.triangular_grating(
            period=self.period, height=self.height,
            angle_deg=self.grating_angle_deg, z0=self.base_height,
            phase_deg=self.phase_deg
        )

    def _get_z_range(self):
        return (self.base_height, self.base_height + self.height)


class CrossedGrating(HeightFunctionStructure):
    """Crossed (2D) grating structure."""

    def __init__(self, center, width, length, period1, period2, height,
                 angle1_deg=0.0, angle2_deg=90.0, base_height=0.0, **kwargs):
        super().__init__(center, width, length, **kwargs)
        self.period1 = period1
        self.period2 = period2
        self.height = height
        self.angle1_deg = angle1_deg
        self.angle2_deg = angle2_deg
        self.base_height = base_height

    def _create_height_function(self):
        return HeightFunctions.crossed_gratings(
            period1=self.period1, period2=self.period2, height=self.height,
            angle1_deg=self.angle1_deg, angle2_deg=self.angle2_deg,
            z0=self.base_height
        )

    def _get_z_range(self):
        return (self.base_height, self.base_height + self.height)


class FresnelLens(HeightFunctionStructure):
    """Fresnel lens structure."""

    def __init__(self, center, width, length, focal_length, wavelength, height,
                 base_height=0.0, **kwargs):
        super().__init__(center, width, length, **kwargs)
        self.focal_length = focal_length
        self.wavelength = wavelength
        self.height = height
        self.base_height = base_height

    def _create_height_function(self):
        return HeightFunctions.fresnel_lens(
            focal_length=self.focal_length, wavelength=self.wavelength,
            height=self.height, cx=0, cy=0
        )

    def _get_z_range(self):
        return (self.base_height, self.base_height + self.height)


class CustomHeightFunctionStructure(HeightFunctionStructure):
    """Structure with user-defined height function."""

    def __init__(self, center, width, length, height_function, z_min, z_max, **kwargs):
        super().__init__(center, width, length, **kwargs)
        self._height_function = height_function
        self._z_min = z_min
        self._z_max = z_max

    def _create_height_function(self):
        return self._height_function

    def _get_z_range(self):
        return (self._z_min, self._z_max)
