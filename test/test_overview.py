"""Overview mosaic of an experiment (T28)."""
import numpy as np
import pytest

from nanofactorysystem.overview import field_of_view_um, grid_positions, stitch

PITCH = np.array([[0.2, 0.0], [0.0, -0.2]])  # um per pixel, y mirrored as in the configuration


def scene(x_um, y_um):
    """ A smooth pattern on the substrate (grey value per position in um). """

    return 128 + 100 * np.sin(x_um / 7.0) * np.cos(y_um / 5.0)


def camera_image(stage_um, width=80, height=60):
    """ Image the camera takes at a stage position: its center shows the stage position. """

    cols, rows = np.meshgrid(np.arange(width) - width / 2 + 0.5, np.arange(height) - height / 2 + 0.5)
    x = stage_um[0] + PITCH[0, 0] * cols + PITCH[0, 1] * rows
    y = stage_um[1] + PITCH[1, 0] * cols + PITCH[1, 1] * rows
    return np.round(scene(x, y)).astype(np.uint8)


def test_field_of_view_and_grid():
    assert field_of_view_um(PITCH, 1280, 1024) == pytest.approx((256.0, 204.8))
    positions = grid_positions((0, 0), (500, 300), (256.0, 204.8), overlap=0.2)
    xs, ys = sorted({p[0] for p in positions}), sorted({p[1] for p in positions})
    assert len(xs) * len(ys) == len(positions)
    # The images cover the area, neighbours overlap by 20 %
    assert xs[0] - 128 <= 0 and xs[-1] + 128 >= 500 and ys[0] - 102.4 <= 0 and ys[-1] + 102.4 >= 300
    assert np.allclose(np.diff(xs), 256 * 0.8) and np.allclose(np.diff(ys), 204.8 * 0.8)
    assert grid_positions((0, 0), (10, 10), (256.0, 204.8)) == [(5.0, 5.0)]
    with pytest.raises(ValueError, match="overlap"):
        grid_positions((0, 0), (10, 10), (1, 1), overlap=1.0)


def test_stitched_image_shows_the_scene_at_the_right_place():
    fov = field_of_view_um(PITCH, 80, 60)
    positions = grid_positions((100, 200), (130, 220), fov, overlap=0.25)
    assert len(positions) > 4
    mosaic = stitch([camera_image(p) for p in positions], positions, PITCH, pixel_um=0.2)

    rows, cols = mosaic.image.shape
    j, i = np.meshgrid(np.arange(rows), np.arange(cols), indexing="ij")
    x = mosaic.origin_um[0] + mosaic.pixel_matrix_um[0, 0] * i + mosaic.pixel_matrix_um[0, 1] * j
    y = mosaic.origin_um[1] + mosaic.pixel_matrix_um[1, 0] * i + mosaic.pixel_matrix_um[1, 1] * j
    expected = scene(x, y)
    assert np.abs(mosaic.image.astype(float) - expected).max() <= 2.0
    assert np.allclose(mosaic.pixel_matrix_um, PITCH)


def test_stitched_image_is_scaled_to_the_pixel_size():
    positions = grid_positions((0, 0), (40, 30), field_of_view_um(PITCH, 80, 60), overlap=0.2)
    mosaic = stitch([camera_image(p) for p in positions], positions, PITCH, pixel_um=1.0)
    assert np.allclose(np.abs(mosaic.pixel_matrix_um), np.diag([1.0, 1.0]))
    # 3 x 3 images of 16 x 12 um with 20 % overlap cover 41.6 x 31.2 um
    assert mosaic.image.shape == pytest.approx((31.2, 41.6), abs=1.5)
