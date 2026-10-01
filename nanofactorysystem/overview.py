##########################################################################
# Copyright (c) 2026 Hannes Robben                                       #
# <hannes.robben@phoenixd.uni-hannover.de>                               #
# This program is free software under the terms of the MIT license.      #
##########################################################################
"""Overview image of an experiment: a stitched camera mosaic (T28).

The camera takes images on a grid of stage positions that covers the
experiment area (with corner markers: the rectangle including corners and QR
code, the defined boundaries of the experiment; without them only the
structure grid). The images are placed with the camera calibration
(``Transform.P2D``, µm per pixel) at their stage positions and stitched with
``tools.stitch.Canvas`` (maintainer decisions 2026-09-30/2026-10-01).
"""
import math
from dataclasses import dataclass, field

import cv2 as cv
import numpy as np

from .tools.stitch import Canvas


def field_of_view_um(pixel_matrix, width_px: int, height_px: int) -> tuple[float, float]:
    """ Field of view (x, y) in µm of a camera image of the given size.

    Parameters
    ----------
    pixel_matrix : 2×2 array
        Camera calibration in µm per pixel (``Transform.P2D``).
    width_px, height_px : int
        Image size.
    """

    matrix = np.abs(np.asarray(pixel_matrix, dtype=float))
    return tuple(float(v) for v in matrix @ np.array([width_px, height_px], dtype=float))


def grid_positions(lower, upper, fov_um, overlap: float = 0.2) -> list[tuple[float, float]]:
    """ Image centers (x, y) in µm that cover the rectangle ``lower``–``upper``.

    Neighbouring images overlap by ``overlap`` (fraction of the field of
    view); the grid is centered on the rectangle, row by row from the lower
    left corner.
    """

    if not 0.0 <= overlap < 1.0:
        raise ValueError(f"overlap must be in [0, 1), got {overlap}")
    axes = []
    for low, high, fov in zip(lower, upper, fov_um):
        extent = float(high) - float(low)
        step = fov * (1 - overlap)
        n = max(1, math.ceil(max(extent - fov, 0.0) / step - 1e-9) + 1)
        center = (float(low) + float(high)) / 2
        axes.append([center + (i - (n - 1) / 2) * step for i in range(n)])
    return [(x, y) for y in axes[1] for x in axes[0]]


@dataclass
class Mosaic:
    """ Stitched overview image and where it lies.

    Parameters
    ----------
    image : ndarray
        Stitched grey image (uint8).
    pixel_matrix_um : ndarray
        µm per pixel of the stitched image (2×2).
    origin_um : tuple of float
        Stage position (x, y) in µm at the center of pixel (0, 0).
    positions_um : list of (x, y)
        Stage positions of the single images.
    """

    image: np.ndarray
    pixel_matrix_um: np.ndarray
    origin_um: tuple[float, float]
    positions_um: list = field(default_factory=list)


def _grey(image: np.ndarray) -> np.ndarray:
    image = np.asarray(image)
    if image.ndim == 3:
        image = image.mean(axis=2)
    return np.clip(image, 0, 255).astype(np.uint8)


def stitch(images, positions_um, pixel_matrix, pixel_um: float = 1.0) -> Mosaic:
    """ Stitch camera images taken at the given stage positions.

    Parameters
    ----------
    images : sequence of ndarray
        Camera images (H×W, or H×W×3).
    positions_um : sequence of (x, y)
        Stage position of every image in µm; the image center shows it.
    pixel_matrix : 2×2 array
        Camera calibration in µm per pixel (``Transform.P2D``).
    pixel_um : float
        Pixel size of the stitched image in µm; the images are scaled down
        to it (a full-resolution canvas of a large experiment would need
        hundreds of MB).

    Returns
    -------
    Mosaic
    """

    pixel_matrix = np.asarray(pixel_matrix, dtype=float)
    native_um = math.sqrt(abs(np.linalg.det(pixel_matrix)))
    scale = min(1.0, native_um / float(pixel_um))
    matrix = pixel_matrix / scale  # µm per pixel of the stitched image
    inverse = np.linalg.inv(matrix)
    scaled = []
    for image in images:
        image = _grey(image)
        if scale < 1.0:
            size = (max(1, round(image.shape[1] * scale)), max(1, round(image.shape[0] * scale)))
            image = cv.resize(image, size, interpolation=cv.INTER_AREA)
        scaled.append(image)
    reference = np.asarray(positions_um[0], dtype=float)
    # Top-left pixel of every image: center at the stage position, measured in canvas pixels
    corners = []
    for image, position in zip(scaled, positions_um):
        center = inverse @ (np.asarray(position, dtype=float) - reference)
        corners.append((center[0] - image.shape[1] / 2, center[1] - image.shape[0] / 2))
    x0 = min(c[0] for c in corners)
    y0 = min(c[1] for c in corners)
    width = max(c[0] - x0 + image.shape[1] for c, image in zip(corners, scaled))
    height = max(c[1] - y0 + image.shape[0] for c, image in zip(corners, scaled))
    canvas = Canvas(math.ceil(width), math.ceil(height))
    for (cx, cy), image in zip(corners, scaled):
        canvas.add(image, int(round(cx - x0)), int(round(cy - y0)))
    origin = reference + matrix @ np.array([x0 + 0.5, y0 + 0.5])
    return Mosaic(canvas.get(), matrix, (float(origin[0]), float(origin[1])),
                  [tuple(map(float, p)) for p in positions_um])
