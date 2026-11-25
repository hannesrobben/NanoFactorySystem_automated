"""Cell primitives of test fields: aligned z grid and substrate anchoring (T138)."""
import math

import numpy as np
import pytest

pytest.importorskip("trimesh")
pytest.importorskip("shapely")

from nanofactorysystem.aerobasic.slicer import SlicingParameters  # noqa: E402
from nanofactorysystem.testprint import cells  # noqa: E402

SLICING = SlicingParameters(layer_height_um=0.3, hatch_spacing_um=0.5, hatch_strategy="linear_x")


def elements(groups):
    return [e for g in groups for e in g.elements]


def check_common(groups, cell_id, power):
    assert groups and all(g.z_um is not None for g in groups)
    assert [g.z_um for g in groups] == sorted(g.z_um for g in groups)
    for element in elements(groups):
        assert element.power_mw == power
        assert element.meta["cell"] == cell_id
        assert np.allclose(element.points[:, 2], element.points[0, 2])


def test_line_passes_and_direction():
    groups = cells.line("c1", length_um=4.0, power_mw=1.0, direction="y", z_um=0.5, passes=3, offset_um=(1, 2))
    check_common(groups, "c1", 1.0)
    assert len(groups) == 1 and groups[0].z_um == 0.5 and len(groups[0].elements) == 3
    assert cells.groups_bounds(groups) == pytest.approx((1.0, 0.0, 1.0, 4.0))


def test_line_set_is_centred_with_the_pitch():
    groups = cells.line_set("c2", n=5, pitch_um=1.5, length_um=6.0, power_mw=2.0)
    check_common(groups, "c2", 2.0)
    ys = sorted(e.points[0, 1] for e in elements(groups))
    assert ys == pytest.approx([-3.0, -1.5, 0.0, 1.5, 3.0])
    assert cells.groups_bounds(groups) == pytest.approx((-3.0, -3.0, 3.0, 3.0))


def test_polyline_and_dot():
    groups = cells.polyline("L", points=[(0, 2), (0, 0), (2, 0)], power_mw=0.7)
    check_common(groups, "L", 0.7)
    assert elements(groups)[0].n_vertices == 3 and elements(groups)[0].role == "contour"
    dot = cells.dot("id", x_um=1.0, y_um=1.0, power_mw=0.7, size_um=0.4)
    assert cells.groups_bounds(dot) == pytest.approx((0.8, 1.0, 1.2, 1.0))


def test_suspended_line_reaches_into_the_supports():
    groups = cells.suspended_line("b", span_um=4.0, z_um=2.5, power_mw=1.0, extend_um=1.0)
    assert groups[0].z_um == 2.5 and cells.groups_bounds(groups)[2] - cells.groups_bounds(groups)[0] == 6.0


def test_woodpile_layers_alternate_and_shift():
    groups = cells.woodpile("w", n_layers=4, rod_pitch_um=1.5, rod_length_um=6.0, dz_um=0.6, power_mw=1.0)
    check_common(groups, "w", 1.0)
    assert [g.z_um for g in groups] == [0.0, 0.6, 1.2, 1.8]
    assert [len(g.elements) for g in groups] == [5, 5, 4, 4]
    first = groups[0].elements[0].points
    assert first[0, 1] == first[1, 1]                       # layer 0: rods along x
    second = groups[1].elements[0].points
    assert second[0, 0] == second[1, 0]                     # layer 1: rods along y
    assert groups[2].elements[0].points[0, 1] == pytest.approx(-3.0 + 0.75)  # shifted by half a pitch


@pytest.mark.parametrize("primitive, kwargs", [
    (cells.line, dict(length_um=0.0, power_mw=1.0)),
    (cells.line, dict(length_um=1.0, power_mw=0.0)),
    (cells.line, dict(length_um=1.0, power_mw=1.0, passes=0)),
    (cells.line, dict(length_um=1.0, power_mw=1.0, direction="z")),
    (cells.line_set, dict(n=0, pitch_um=1.0, length_um=1.0, power_mw=1.0)),
    (cells.polyline, dict(points=[(0, 0)], power_mw=1.0)),
    (cells.woodpile, dict(n_layers=2, rod_pitch_um=2.0, rod_length_um=1.0, dz_um=0.5, power_mw=1.0)),
    (cells.suspended_line, dict(span_um=2.0, z_um=1.0, power_mw=1.0, extend_um=-1)),
])
def test_invalid_input_names_the_cell(primitive, kwargs):
    with pytest.raises(ValueError, match="cell bad"):
        primitive("bad", **kwargs)


def test_height_maps_are_centred_and_have_a_zero_margin():
    pad = cells.pad_map(6.0, 4.0, 1.0, pixel_um=0.1)
    assert pad.max() == 1.0 and pad[0, :].max() == 0 and pad[:, 0].max() == 0
    assert np.allclose(pad, pad[::-1, ::-1])
    ramp = cells.pad_map(6.0, 6.0, 1.0, ramp_um=1.6, pixel_um=0.1)
    row = ramp[ramp.shape[0] // 2]
    assert row.max() == 1.0 and 0 < row[np.nonzero(row)[0][-1]] < 0.2  # falls to ~0 at the +x end
    wedge = cells.wedge_map(8.0, 6.0, 3.0, pixel_um=0.1)
    assert wedge.max() == pytest.approx(3.0) and math.degrees(math.atan(3 / 8)) == pytest.approx(20.56, abs=0.01)
    cap = cells.cap_map(8.0, 2.0, pixel_um=0.1)
    assert cap.max() == pytest.approx(2.0, abs=1e-3) and np.allclose(cap, cap.T)
    pillar = cells.pillar_on_base_map(6.0, 6.0, 1.4, 1.5, 4.0, pixel_um=0.1)
    assert set(np.unique(pillar)) == {0.0, 1.4, 5.4}


def test_sliced_pad_lies_on_the_aligned_grid():
    pad = cells.pad_map(6.0, 6.0, 1.0)
    groups = cells.sliced("p1", height_map_um=pad, pixel_um=cells.DEFAULT_PIXEL_UM, slicing=SLICING, power_mw=1.5)
    check_common(groups, "p1", 1.5)
    assert [g.z_um for g in groups] == [0.0, 0.3, 0.6, 0.9]
    x0, y0, x1, y1 = cells.groups_bounds(groups)
    assert x0 == pytest.approx(-3.0, abs=0.1) and x1 == pytest.approx(3.0, abs=0.1)
    assert y0 == pytest.approx(-2.75, abs=0.3) and y1 == pytest.approx(2.75, abs=0.3)  # hatch lines inside
    assert all(e.meta["part"] == "volume" for e in elements(groups))


def test_cells_with_the_same_slice_distance_share_their_layers():
    pad = cells.sliced("a", height_map_um=cells.pad_map(4, 4, 1.0), pixel_um=cells.DEFAULT_PIXEL_UM,
                       slicing=SLICING, power_mw=1.0)
    wedge = cells.sliced("b", height_map_um=cells.wedge_map(8, 6, 3.0), pixel_um=cells.DEFAULT_PIXEL_UM,
                         slicing=SLICING, power_mw=1.0, offset_um=(10, 0))
    assert {g.z_um for g in pad} <= {g.z_um for g in wedge}
    assert all(round(z / 0.3, 6) == round(z / 0.3) for z in {g.z_um for g in wedge})


def test_anchor_repeats_the_first_slice_down_to_the_depth():
    pad = cells.pad_map(4.0, 4.0, 1.0)
    plain = cells.sliced("a", height_map_um=pad, pixel_um=cells.DEFAULT_PIXEL_UM, slicing=SLICING, power_mw=1.0)
    anchored = cells.sliced("a", height_map_um=pad, pixel_um=cells.DEFAULT_PIXEL_UM, slicing=SLICING, power_mw=1.0,
                            anchor_depth_um=1.5)
    zs = [g.z_um for g in anchored]
    assert zs == [-1.5, -1.2, -0.9, -0.6, -0.3, 0.0, 0.3, 0.6, 0.9]
    first = plain[0]
    for group in anchored[:5]:
        assert all(e.meta["part"] == "anchor" for e in group.elements)
        assert len(group.elements) == len(first.elements)
        assert np.allclose(group.elements[0].points[:, :2], first.elements[0].points[:, :2])
    # 1.4 µm at 0.3 µm: 5 copies reach -1.5 µm (at least the depth)
    deeper = cells.sliced("a", height_map_um=pad, pixel_um=cells.DEFAULT_PIXEL_UM, slicing=SLICING, power_mw=1.0,
                          anchor_depth_um=1.4)
    assert deeper[0].z_um == -1.5


def test_min_z_drops_the_part_inside_the_base():
    pillar = cells.pillar_map(1.5, 5.4, extent_um=2.0)
    groups = cells.sliced("p", height_map_um=pillar, pixel_um=cells.DEFAULT_PIXEL_UM, slicing=SLICING,
                          power_mw=1.0, min_z_um=1.4)
    assert groups[0].z_um == 1.5 and groups[-1].z_um == 5.1
    with pytest.raises(ValueError, match="cannot be anchored"):
        cells.sliced("p", height_map_um=pillar, pixel_um=cells.DEFAULT_PIXEL_UM, slicing=SLICING, power_mw=1.0,
                     min_z_um=1.4, anchor_depth_um=1.0)


def test_sliced_is_deterministic():
    pad = cells.cap_map(8.0, 2.0)
    one = cells.sliced("c", height_map_um=pad, pixel_um=cells.DEFAULT_PIXEL_UM, slicing=SLICING, power_mw=1.0,
                       anchor_depth_um=0.6)
    two = cells.sliced("c", height_map_um=pad, pixel_um=cells.DEFAULT_PIXEL_UM, slicing=SLICING, power_mw=1.0,
                       anchor_depth_um=0.6)
    assert [(g.z_um, [e.points.tolist() for e in g.elements]) for g in one] == \
           [(g.z_um, [e.points.tolist() for e in g.elements]) for g in two]


def test_sliced_invalid_input():
    with pytest.raises(ValueError, match="cell v: height map has no height"):
        cells.sliced("v", height_map_um=np.zeros((5, 5)), pixel_um=0.1, slicing=SLICING, power_mw=1.0)
    with pytest.raises(ValueError, match="cell v: anchor_depth_um"):
        cells.sliced("v", height_map_um=cells.pad_map(2, 2, 1), pixel_um=0.05, slicing=SLICING, power_mw=1.0,
                     anchor_depth_um=-1)
