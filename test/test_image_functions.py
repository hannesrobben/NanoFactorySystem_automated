"""Unit tests of nanofactorysystem.image.functions."""
import numpy as np

from nanofactorysystem.image.functions import contour_mask, get_contours


def test_contour_mask_fills_contour():
    """ The mask of a detected square is True inside and False outside (OpenCV accepts the mask array). """

    img = np.zeros((40, 50), dtype=np.uint8)
    img[10:20, 15:30] = 255
    contours = get_contours(img, 128)
    assert len(contours) == 1

    mask = contour_mask(img.shape, contours[0])

    assert mask.dtype == bool
    assert mask.shape == img.shape
    assert mask[10:20, 15:30].all()
    assert mask.sum() == 10 * 15
