##########################################################################
# Copyright (c) 2026 Hannes Robben                                       #
# <hannes.robben@phoenixd.uni-hannover.de>                               #
# This program is free software under the terms of the MIT license.      #
##########################################################################
"""Height map (e.g. a 16-bit PNG) → IFOV layer programs.

A height map is a 2D array of heights in µm above the socket. The structure
is a socket that covers the whole image plus, above it, one raster layer per
slice that contains the pixels which are still part of the structure at that
height. Every layer is one IFOV program (``IFOV_Lines``), written exactly like
the other IFOV structures (``Rectangle2D_IFOV``, ``BinaryGrating_IFOV``).

Geometry (structure coordinates, µm, relative to ``center``)::

            +y
     row 0  ┌──────────────┐        origin="upper" (default): the image is
            │              │        printed as it is shown in an image viewer
            │   image      │        (row 0 at the top = +y, column 0 left = −x)
            │              │
     row −1 └──────────────┘
          −x  col 0     col −1  +x

Pixel (r, c) covers x ∈ [−W/2 + c·px, −W/2 + (c+1)·px] with W = n_cols·px
(and the same in y), so the image center is the structure center.

Layers (z relative to ``center.Z``)::

    socket:     z = 0 … socket_height (like Rectangle3D: round(H/dz)+1 layers), full image
    structure:  uniform slicing (default): z_k = socket_height + k·dz,
                pixel printed in layer k if round(h/dz) ≥ k  (nearest-layer rounding, error ≤ dz/2);
                k starts at 1 on a socket, at 0 without one (bottom layer of every column with
                round(h/dz) ≥ 1, as Rectangle3D prints its bottom layer at z = 0)
                adaptive slicing: every distinct height of the map is hit exactly by a layer,
                the gaps between them are filled with layers of at most dz (see _adaptive_levels)
                z_levels: explicit layer heights above the socket (manual override)

Empty layers are skipped.
"""
import hashlib
import logging
import math
from pathlib import Path
from typing import Any, Iterator, Optional, Sequence

import numpy as np

from nanofactorysystem.aerobasic.programs.drawings.base import DrawableObject, IFOV_AeroBasicProgram, encode_json_value
from nanofactorysystem.aerobasic.programs.drawings.lines import HatchingDirection, IFOV_Lines, ifov_writing_speed_mm_s
from nanofactorysystem.devices.coordinate_system import CoordinateSystem, Point2D, Point3D

log = logging.getLogger(__name__)

# Tolerance in µm when heights are compared with layer heights
HEIGHT_TOLERANCE_UM = 1e-6


def read_height_png(path: str | Path, height_per_gray_value: float, *, gray_offset: int = 0,
                    require_16bit: bool = True) -> np.ndarray:
    """ Read a single-channel PNG and convert it into heights in µm.

    Parameters
    ----------
    path : str or Path
        PNG file, normally 16 bit (uint16) grayscale.
    height_per_gray_value : float
        Height in µm of one gray value step.
    gray_offset : int
        Gray value of height 0 (default 0). Pixels below it are set to 0.
    require_16bit : bool
        Refuse images that are not 16 bit (an 8-bit export would silently
        reduce the height resolution to 256 levels).

    Returns
    -------
    np.ndarray
        float64 array (rows, cols) of heights in µm above the socket.
    """

    import cv2

    path = Path(path)
    image = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if image is None:
        raise FileNotFoundError(f"Cannot read image {path}")
    if image.ndim != 2:
        raise ValueError(f"{path.name}: expected a single-channel (grayscale) image, got shape {image.shape}")
    if require_16bit and image.dtype != np.uint16:
        raise ValueError(f"{path.name}: expected a 16-bit image, got {image.dtype} "
                         f"(pass require_16bit=False to accept it)")
    gray = image.astype(np.int64) - int(gray_offset)
    return np.clip(gray, 0, None).astype(float) * float(height_per_gray_value)


def _runs(row: np.ndarray) -> np.ndarray:
    """ Start and end index (exclusive) of every run of True values in a 1D boolean array, shape (n, 2). """

    padded = np.concatenate(([False], row, [False])).astype(np.int8)
    edges = np.flatnonzero(np.diff(padded))
    return edges.reshape(-1, 2)


class HeightMap_IFOV(DrawableObject):
    """ Raster a height map layer by layer in IFOV mode, on a socket covering the whole image.

    Parameters
    ----------
    center : Point3D
        Structure center; ``center.Z`` is the z of the bottom layer (e.g. −1 µm
        into the substrate). Keep X and Y at 0, as for the other IFOV
        structures: the experiment places the structure, and the IFOV
        reference point adds ``center`` once more.
    height_map : np.ndarray, str or Path
        Heights in µm above the socket, shape (rows, cols), 0 = socket only;
        or the path of a 16-bit grayscale PNG (then ``height_per_gray_value``
        is required). A PNG is stored by its path and SHA-256, so the
        structure can be rebuilt from the experiment file / spec.
    pixel_pitch : float or (float, float)
        Pixel size in µm, ``(px, py)`` = size along x (columns) and y (rows).
    socket_height : float
        Height of the socket in µm (0: no socket).
    slice_size : float
        Layer height in µm of the structure.
    hatch_size : float, optional
        Distance between raster lines in µm. Default: the pixel pitch across
        the raster lines (py for lines along x, px for lines along y). Set it
        for large pixels: the image is then sampled at the line positions
        (nearest pixel); along a line the pixel resolution is kept.
    velocity : float
        Writing velocity in mm/s, stored for the metadata. IFOV writes with
        the fixed speed of the objective (``IFOV_WRITING_SPEED_MM_S``).
    power : float, optional
        Laser power in mW, set at the start of every layer program.
    objective : str
        Objective whose IFOV configuration the layer programs use.
    hatching_direction : HatchingDirection
        As in ``Rectangle2D_IFOV``: ``Y`` = lines along x, stepped along y
        (raster along the image rows, default); ``X`` = lines along y.
    alternating_hatch : bool
        Turn the raster direction by 90° from layer to layer.
    serpentine : bool
        Write every other raster line backwards (shorter jumps).
    adaptive_slicing : bool
        Slice so that every distinct height of the map is reached exactly
        (useful for multi-level DOEs); see :meth:`structure_levels`.
    z_levels : sequence of float, optional
        Explicit layer heights in µm above the socket; overrides the slicing.
    socket_slice_size : float, optional
        Layer height of the socket; default ``slice_size``.
    socket_hatch_size : float, optional
        Line distance in the socket; default ``hatch_size`` (the socket is
        usually most of the writing time: a 1 x 1 mm layer at 0.5 µm is 2 m
        of lines, about 7 min at the IFOV speed of the 63x objective).
    min_segment_length : float
        Raster segments shorter than this (µm) are dropped (default 0: keep all).
    origin : {"upper", "lower"}
        Image row 0 at +y (``"upper"``, as shown in an image viewer) or at −y.
    max_levels : int
        Upper limit of distinct heights for adaptive slicing.
    height_per_gray_value : float, optional
        µm per gray value of a PNG height map.
    gray_offset : int
        Gray value of height 0 of a PNG height map.
    png_sha256 : str, optional
        Expected SHA-256 of the PNG (set when the structure is rebuilt; a
        changed file is refused).
    """

    def __init__(
            self,
            center: Point3D,
            height_map: np.ndarray | str | Path,
            pixel_pitch: float | Sequence[float],
            socket_height: float = 0.0,
            *,
            slice_size: float,
            height_per_gray_value: Optional[float] = None,
            gray_offset: int = 0,
            png_sha256: Optional[str] = None,
            hatch_size: Optional[float] = None,
            velocity: float = 5.0,
            power: Optional[float] = None,
            objective: str = "Zeiss 63x",
            hatching_direction: HatchingDirection = HatchingDirection.Y,
            alternating_hatch: bool = False,
            serpentine: bool = True,
            adaptive_slicing: bool = False,
            z_levels: Optional[Sequence[float]] = None,
            socket_slice_size: Optional[float] = None,
            socket_hatch_size: Optional[float] = None,
            min_segment_length: float = 0.0,
            origin: str = "upper",
            max_levels: int = 256,
    ):
        super().__init__()
        self.png_path: Optional[Path] = None
        if isinstance(height_map, (str, Path)):
            if height_per_gray_value is None:
                raise ValueError("A PNG height map needs height_per_gray_value (µm per gray value).")
            self.png_path = Path(height_map).resolve()
            digest = hashlib.sha256(self.png_path.read_bytes()).hexdigest()
            if png_sha256 is not None and digest != png_sha256:
                raise ValueError(f"{self.png_path} has changed since the structure was stored "
                                 f"(SHA-256 {digest} instead of {png_sha256}).")
            png_sha256 = digest
            height_map = read_height_png(self.png_path, height_per_gray_value, gray_offset=gray_offset)
        self.height_per_gray_value = height_per_gray_value
        self.gray_offset = int(gray_offset)
        self.png_sha256 = png_sha256
        height_map = np.asarray(height_map, dtype=float)
        if height_map.ndim != 2 or height_map.size == 0:
            raise ValueError(f"height_map must be a non-empty 2D array, got shape {height_map.shape}")
        if np.any(~np.isfinite(height_map)) or np.any(height_map < 0):
            raise ValueError("height_map must contain finite heights ≥ 0")
        if np.isscalar(pixel_pitch):
            pixel_pitch = (float(pixel_pitch), float(pixel_pitch))
        px, py = map(float, pixel_pitch)
        if px <= 0 or py <= 0:
            raise ValueError(f"pixel_pitch must be positive, got {pixel_pitch}")
        if slice_size <= 0:
            raise ValueError("slice_size must be positive")
        if hatch_size is not None and hatch_size <= 0:
            raise ValueError("hatch_size must be positive")
        if socket_height < 0:
            raise ValueError("socket_height must be ≥ 0")
        if origin not in ("upper", "lower"):
            raise ValueError("origin must be 'upper' or 'lower'")

        self.center = center if isinstance(center, Point3D) else Point3D(center.X, center.Y, 0.0)
        self.height_map = height_map
        self.pixel_pitch = (px, py)
        self.socket_height = float(socket_height)
        self.slice_size = float(slice_size)
        self.hatch_size = hatch_size
        self.velocity = velocity
        self.power = power
        self.objective = objective
        self.hatching_direction = hatching_direction
        self.alternating_hatch = alternating_hatch
        self.serpentine = serpentine
        self.adaptive_slicing = adaptive_slicing
        self.z_levels = None if z_levels is None else [float(z) for z in z_levels]
        self.socket_slice_size = socket_slice_size
        self.socket_hatch_size = socket_hatch_size
        self.min_segment_length = float(min_segment_length)
        self.origin = origin
        self.max_levels = max_levels

        self._layers: Optional[list[tuple[str, float, np.ndarray]]] = None

    # ------------------------------------------------------------------ construction from a PNG

    @classmethod
    def from_png(cls, path: str | Path, pixel_pitch: float | Sequence[float], height_per_gray_value: float,
                 socket_height: float = 0.0, *, center: Point3D = Point3D(0, 0, 0), **kwargs) -> "HeightMap_IFOV":
        """ Build the structure from a 16-bit PNG (same as passing the path as ``height_map``).

        Parameters
        ----------
        path : str or Path
            Grayscale PNG.
        pixel_pitch : float or (float, float)
            Pixel size in µm, ``(px, py)``.
        height_per_gray_value : float
            µm per gray value; gray value 0 (or ``gray_offset``) is the socket top.
        socket_height : float
            Socket height in µm.
        center : Point3D
            Structure center (bottom of the socket at ``center.Z``).
        **kwargs
            Further arguments of :class:`HeightMap_IFOV` (``slice_size`` is required).
        """

        return cls(center, path, pixel_pitch, socket_height, height_per_gray_value=height_per_gray_value, **kwargs)

    # ------------------------------------------------------------------ geometry

    @property
    def center_point(self) -> Point3D:
        return self.center

    @property
    def n_rows(self) -> int:
        return self.height_map.shape[0]

    @property
    def n_cols(self) -> int:
        return self.height_map.shape[1]

    @property
    def width(self) -> float:
        """ Extent along x in µm. """
        return self.n_cols * self.pixel_pitch[0]

    @property
    def length(self) -> float:
        """ Extent along y in µm. """
        return self.n_rows * self.pixel_pitch[1]

    @property
    def max_height(self) -> float:
        return float(self.height_map.max())

    @property
    def structure_height(self) -> float:
        """ Total height (socket + highest pixel) in µm, without ``center.Z``. """
        return self.socket_height + self.max_height

    # ------------------------------------------------------------------ slicing

    def socket_levels(self) -> list[float]:
        """ z of the socket layers relative to ``center.Z`` (empty without socket). """

        if self.socket_height == 0:
            return []
        dz = self.socket_slice_size or self.slice_size
        n = max(1, round(self.socket_height / dz))
        return [i * self.socket_height / n for i in range(n + 1)]

    def _adaptive_levels(self) -> list[float]:
        heights = np.unique(np.round(self.height_map[self.height_map > HEIGHT_TOLERANCE_UM], 6))
        if len(heights) > self.max_levels:
            raise ValueError(f"Adaptive slicing: the map has {len(heights)} distinct heights (> max_levels="
                             f"{self.max_levels}). Quantize the design, raise max_levels, pass z_levels or use "
                             f"uniform slicing.")
        levels, previous = [], 0.0
        for height in heights:
            n = max(1, math.ceil((height - previous) / self.slice_size - 1e-9))
            levels += [previous + j * (height - previous) / n for j in range(1, n + 1)]
            previous = float(height)
        return levels

    def structure_levels(self) -> list[float]:
        """ Heights above the socket at which structure layers are written.

        Uniform slicing: ``k·slice_size`` for k = 1 … round(max/slice_size).
        Adaptive slicing: every distinct height of the map is a layer; between
        two consecutive heights (and from 0 to the lowest) the gap is divided
        into the fewest equal steps of at most ``slice_size``. Example with
        ``slice_size=0.2`` and heights {0.25, 0.5}: layers at 0.125, 0.25,
        0.375, 0.5 instead of 0.2, 0.4, (0.6).
        """

        if self.z_levels is not None:
            return sorted(z for z in self.z_levels if z > 0)
        if self.adaptive_slicing:
            return self._adaptive_levels()
        n = round(self.max_height / self.slice_size)
        return [k * self.slice_size for k in range(1, n + 1)]

    def _structure_mask(self, level: float, *, bottom: bool = False) -> np.ndarray:
        h = self.height_map
        if self.z_levels is None and not self.adaptive_slicing:
            quantized = np.rint(h / self.slice_size)
            return quantized >= 1 if bottom else quantized >= round(level / self.slice_size)
        if bottom:
            return h > HEIGHT_TOLERANCE_UM
        return h >= level - HEIGHT_TOLERANCE_UM

    def layers(self) -> list[tuple[str, float, np.ndarray]]:
        """ All non-empty layers as ``(kind, z relative to center.Z, mask)``; kind is "socket" or "structure". """

        if self._layers is not None:
            return self._layers
        layers = []
        full = np.ones(self.height_map.shape, dtype=bool)
        for z in self.socket_levels():
            layers.append(("socket", z, full))
        levels = self.structure_levels()
        if self.socket_height == 0 and levels:
            # Without a socket every column starts with a bottom layer at z = 0 (as Rectangle3D)
            layers.append(("structure", 0.0, self._structure_mask(0.0, bottom=True)))
        for level in levels:
            layers.append(("structure", self.socket_height + level, self._structure_mask(level)))
        self._layers = [layer for layer in layers if layer[2].any()]
        return self._layers

    # ------------------------------------------------------------------ rastering

    def _hatch_positions(self, extent: float, pitch: float, hatch_size: Optional[float]) -> np.ndarray:
        hatch = hatch_size if hatch_size is not None else pitch
        n = max(1, round(extent / hatch))
        return -extent / 2 + (np.arange(n) + 0.5) * extent / n

    def raster_segments(self, mask: np.ndarray, direction: HatchingDirection,
                        hatch_size: Optional[float] = None) -> list[tuple[Point2D, Point2D]]:
        """ Raster lines of one layer as (start, end) points in µm relative to the structure center.

        ``hatch_size`` overrides the line distance (default: ``self.hatch_size``, else the pixel pitch).
        """

        px, py = self.pixel_pitch
        hatch_size = hatch_size if hatch_size is not None else self.hatch_size
        if direction == HatchingDirection.Y:  # lines along x, stepped along y
            positions = self._hatch_positions(self.length, py, hatch_size)
            if self.origin == "upper":
                index = np.floor((self.length / 2 - positions) / py).astype(int)
            else:
                index = np.floor((positions + self.length / 2) / py).astype(int)
            index = np.clip(index, 0, self.n_rows - 1)
            get_line = lambda i: mask[i, :]
            along_pitch, along_extent = px, self.width
            make_point = lambda s, p: Point2D(X=s, Y=p)
        elif direction == HatchingDirection.X:  # lines along y, stepped along x
            positions = self._hatch_positions(self.width, px, hatch_size)
            index = np.clip(np.floor((positions + self.width / 2) / px).astype(int), 0, self.n_cols - 1)
            if self.origin == "upper":  # row 0 at +y: walk the column from the bottom (last row) upwards
                get_line = lambda i: mask[::-1, i]
            else:
                get_line = lambda i: mask[:, i]
            along_pitch, along_extent = py, self.length
            make_point = lambda s, p: Point2D(X=p, Y=s)
        else:
            raise ValueError(f"Unknown hatching direction {direction}")

        segments = []
        forward = True
        for position, i in zip(positions, index):
            runs = _runs(get_line(i))
            if len(runs) == 0:
                continue
            starts = -along_extent / 2 + runs[:, 0] * along_pitch
            ends = -along_extent / 2 + runs[:, 1] * along_pitch
            keep = (ends - starts) >= self.min_segment_length
            starts, ends = starts[keep], ends[keep]
            if len(starts) == 0:
                continue
            line = [(make_point(float(s), float(position)), make_point(float(e), float(position)))
                    for s, e in zip(starts, ends)]
            if self.serpentine and not forward:
                line = [(end, start) for start, end in reversed(line)]
            segments += line
            forward = not forward
        return segments

    def _layer_hatch(self, kind: str) -> Optional[float]:
        return self.socket_hatch_size if kind == "socket" and self.socket_hatch_size is not None else None

    def _directions(self) -> Iterator[HatchingDirection]:
        direction = self.hatching_direction
        while True:
            yield direction
            if self.alternating_hatch:
                direction = direction.flip()

    def iterate_layers(self, coordinate_system: CoordinateSystem) -> Iterator[IFOV_AeroBasicProgram]:
        directions = self._directions()
        for index, (kind, z, mask) in enumerate(self.layers()):
            direction = next(directions)
            segments = self.raster_segments(mask, direction, self._layer_hatch(kind))
            if not segments:
                continue
            ifov_lines = IFOV_Lines(
                reference_point=Point3D(self.center.X, self.center.Y, self.center.Z + z),
                lines=segments,
                velocity=self.velocity,
                power=self.power,
            )
            for program in ifov_lines.iterate_layers(coordinate_system, objective=self.objective):
                program.lines.insert(0, f"' HeightMap_IFOV layer {index} ({kind}), z = {z:.4f} um, "
                                        f"{len(segments)} lines, hatching {direction.name}")
                yield program

    # ------------------------------------------------------------------ information

    def statistics(self) -> dict[str, Any]:
        """ Number of layers and raster lines, total writing length (no programs are generated). """

        directions = self._directions()
        per_layer = []
        for kind, z, mask in self.layers():
            segments = self.raster_segments(mask, next(directions), self._layer_hatch(kind))
            length = sum(math.dist((a.X, a.Y), (b.X, b.Y)) for a, b in segments)
            per_layer.append({"kind": kind, "z_um": z, "lines": len(segments), "length_um": length})
        return {
            "size_um": (self.width, self.length, self.structure_height),
            "pixels": (self.n_cols, self.n_rows),
            "layers": len(per_layer),
            "socket_layers": sum(1 for layer in per_layer if layer["kind"] == "socket"),
            "lines": sum(layer["lines"] for layer in per_layer),
            "max_lines_per_layer": max((layer["lines"] for layer in per_layer), default=0),
            "length_mm": sum(layer["length_um"] for layer in per_layer) / 1000,
            "writing_time_min": sum(layer["length_um"] for layer in per_layer) / 1000
                                / ifov_writing_speed_mm_s(self.objective) / 60,
            "per_layer": per_layer,
        }

    def to_json(self) -> dict[str, Any]:
        """ JSON description that :func:`structure_from_json` can rebuild.

        A PNG height map is stored by its absolute path and SHA-256; an array
        is stored as array (large arrays make the experiment file large: use
        a PNG for real designs).
        """

        h = self.height_map
        arguments = {
            "center": self.center,
            "height_map": str(self.png_path) if self.png_path is not None else h,
            "pixel_pitch": list(self.pixel_pitch),
            "socket_height": self.socket_height,
            "slice_size": self.slice_size,
            "height_per_gray_value": self.height_per_gray_value,
            "gray_offset": self.gray_offset,
            "png_sha256": self.png_sha256,
            "hatch_size": self.hatch_size,
            "velocity": self.velocity,
            "power": self.power,
            "objective": self.objective,
            "hatching_direction": self.hatching_direction,
            "alternating_hatch": self.alternating_hatch,
            "serpentine": self.serpentine,
            "adaptive_slicing": self.adaptive_slicing,
            "z_levels": self.z_levels,
            "socket_slice_size": self.socket_slice_size,
            "socket_hatch_size": self.socket_hatch_size,
            "min_segment_length": self.min_segment_length,
            "origin": self.origin,
            "max_levels": self.max_levels,
        }
        return {
            "__class__": self.__class__.__name__,
            "__module__": self.__class__.__module__,
            "center_point": self.center_point.as_tuple(),
            "__init__": {k: encode_json_value(v) for k, v in arguments.items()},
            "height_map_info": {"shape": list(h.shape), "min_um": float(h.min()), "max_um": float(h.max())},
            "layer_z_um": [z for _, z, _ in self.layers()],
        }

    def __repr__(self) -> str:
        return (f"HeightMap_IFOV({self.n_cols}x{self.n_rows} px, pitch {self.pixel_pitch} um, "
                f"socket {self.socket_height} um, max {self.max_height:.3f} um, slice {self.slice_size} um)")
