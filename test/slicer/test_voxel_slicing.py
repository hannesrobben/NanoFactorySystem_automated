"""Voxel-aware slicing and hatching (T54): the printed envelope matches the design."""
import numpy as np
import pytest

trimesh = pytest.importorskip("trimesh")
pytest.importorskip("shapely")

from nanofactorysystem.aerobasic.slicer import (JobParameters, LaserParameters, SlicingParameters,  # noqa: E402
                                                 slice_geometry)
from nanofactorysystem.aerobasic.slicer import hatching  # noqa: E402
from nanofactorysystem.aerobasic.slicer.voxel import SpacingMode, compensate  # noqa: E402
from nanofactorysystem.voxel import DatabaseVoxelModel, FixedVoxelModel, NoVoxelData, VoxelDatabase  # noqa: E402

WIDTH, HEIGHT = 0.5, 1.2  # voxel size in um
LASER = LaserParameters(power_mw=1.0, scan_speed_um_s=1000.0)


def box(size=(20.0, 20.0, 5.0)):
    mesh = trimesh.creation.box(extents=size)
    mesh.apply_translation([0, 0, size[2] / 2])  # base at z = 0
    return mesh


def cylinder(radius=8.0, height=4.0):
    mesh = trimesh.creation.cylinder(radius=radius, height=height, sections=128)
    mesh.apply_translation([0, 0, height / 2])
    return mesh


def params(**slicing):
    return JobParameters(slicing=SlicingParameters(**{"layer_height_um": 0.5, "hatch_spacing_um": 0.4} | slicing),
                         laser=LASER)


def layer_points(job):
    """ z and the (N, 2) toolpath vertices of every layer. """

    return [(g.z_um, np.vstack([e.points[:, :2] for e in g.elements])) for g in job.groups if g.z_um is not None]


def envelope(job):
    """ Toolpath plus voxel: z range and the lateral points of all layers. """

    layers = layer_points(job)
    z = np.array([z for z, _ in layers])
    points = np.vstack([p for _, p in layers])
    return z.min() - HEIGHT / 2, z.max() + HEIGHT / 2, points


def test_box_envelope_matches_the_design():
    job = slice_geometry(box(), params(), voxel_model=FixedVoxelModel(WIDTH, HEIGHT))

    bottom, top, points = envelope(job)
    assert bottom == pytest.approx(0.0, abs=1e-9) and top == pytest.approx(5.0, abs=1e-9)
    slicing = job.params.slicing
    # Spacing derived from the voxel size (default VOXEL_OVERLAP, overlap 0.3)
    assert slicing.hatch_spacing_um == pytest.approx(WIDTH * 0.7)
    z = np.array([z for z, _ in layer_points(job)])
    assert np.all(np.diff(z) <= HEIGHT * 0.7 + 1e-9)
    # Laterally: toolpath + half the voxel width stays inside the design, at most one line spacing short of it
    reach = np.abs(points).max(axis=0) + WIDTH / 2
    assert np.all(reach <= 10.0 + 1e-6) and np.all(reach >= 10.0 - slicing.hatch_spacing_um)
    assert job.meta["voxel"]["width_um"] == WIDTH and job.meta["voxel"]["model"] == {
        "type": "fixed", "width_um": WIDTH, "height_um": HEIGHT}


def test_cylinder_envelope_matches_the_design():
    job = slice_geometry(cylinder(), params(), voxel_model=FixedVoxelModel(WIDTH, HEIGHT))

    bottom, top, points = envelope(job)
    assert bottom == pytest.approx(0.0, abs=1e-9) and top == pytest.approx(4.0, abs=1e-9)
    radius = np.hypot(points[:, 0], points[:, 1]).max() + WIDTH / 2
    assert 8.0 - job.params.slicing.hatch_spacing_um <= radius <= 8.0 + 1e-6


def test_without_data_nothing_changes():
    reference = slice_geometry(box(), params())
    for model in (None, NoVoxelData()):
        job = slice_geometry(box(), params(), voxel_model=model)
        assert job.params == reference.params
        assert [g.z_um for g in job.groups] == [g.z_um for g in reference.groups]
        for group, expected in zip(job.groups, reference.groups):
            assert all(np.array_equal(a.points, b.points) for a, b in zip(group.elements, expected.elements))
    assert "voxel" not in reference.meta
    assert slice_geometry(box(), params(), voxel_model=NoVoxelData()).meta["voxel"]["width_um"] is None


def test_static_hatching_keeps_the_spacing_and_warns_about_gaps(caplog):
    wide = compensate(params(spacing_mode="static_hatching", hatch_spacing_um=0.8, layer_height_um=1.5),
                      FixedVoxelModel(WIDTH, HEIGHT))
    assert wide.params.slicing.hatch_spacing_um == 0.8 and wide.params.slicing.layer_height_um == 1.5
    assert wide.params.slicing.contour_offset_um == WIDTH / 2 and wide.params.slicing.voxel_height_um == HEIGHT
    assert len(wide.report["warnings"]) == 2 and "gaps between neighbouring lines" in caplog.text

    # Very low spacing (dense lines) is allowed without warning
    dense = compensate(params(spacing_mode="static_hatching", hatch_spacing_um=0.05, layer_height_um=0.1),
                       FixedVoxelModel(WIDTH, HEIGHT))
    assert dense.params.slicing.hatch_spacing_um == 0.05 and dense.report["warnings"] == []
    assert SpacingMode.parse("STATIC_HATCHING") == SpacingMode.STATIC_HATCHING


def test_explicit_contour_offset_and_partial_data():
    result = compensate(params(contour_offset_um=0.1), FixedVoxelModel(None, HEIGHT))
    slicing = result.params.slicing
    assert slicing.contour_offset_um == 0.1 and slicing.hatch_spacing_um == 0.4  # no width: lateral unchanged
    assert slicing.layer_height_um == pytest.approx(HEIGHT * 0.7) and slicing.voxel_height_um == HEIGHT
    assert result.params.voxel_size_um == (0.1, 0.1, HEIGHT)


def test_part_thinner_than_a_voxel_gets_one_slice(caplog):
    job = slice_geometry(box((10.0, 10.0, 1.0)), params(), voxel_model=FixedVoxelModel(WIDTH, HEIGHT))
    assert [g.z_um for g in job.groups] == [pytest.approx(0.5)]
    assert "one slice at mid-height" in caplog.text


def test_strategies_receive_the_voxel_context(monkeypatch):
    received = []

    def probe(contours, layer_index, params, *, voxel=None):
        received.append(voxel)
        return hatching.hatch_alternating(contours, layer_index, params, voxel=voxel)

    monkeypatch.setitem(hatching._REGISTRY, "probe", probe)
    model = FixedVoxelModel(WIDTH, HEIGHT)
    slice_geometry(box(), params(hatch_strategy="probe"), voxel_model=model)
    assert received and all(v.model is model and v.width_um == WIDTH and v.power_mw == 1.0 for v in received)

    received.clear()
    slice_geometry(box(), params(hatch_strategy="probe"))
    assert received and all(v is None for v in received)


def test_database_model(tmp_path):
    with VoxelDatabase(tmp_path / "voxels.sqlite") as database:
        for power, velocity, width in [(1.0, 1000, 0.4), (2.0, 1000, 0.6), (1.0, 2000, 0.3), (2.0, 2000, 0.5)]:
            database.add_measurement("SZ2080", "Zeiss 63x", "IFOV_on", power, velocity, width_um=width,
                                     height_um=3 * width, method="SEM")
    model = DatabaseVoxelModel("SZ2080", "Zeiss 63x", "IFOV_on", database=tmp_path / "voxels.sqlite")

    size = model.voxel_size(1.0, 1000)
    assert size.width_um == pytest.approx(0.4) and size.width_method == "exact"
    assert model.voxel_size(5.0, 1000) is None  # outside the measured range: no extrapolation
    assert model.describe()["material"] == "SZ2080"
    job = slice_geometry(box(), params(), voxel_model=model)
    assert job.meta["voxel"]["width_um"] == pytest.approx(0.4) and job.meta["voxel"]["width_method"] == "exact"


def test_model3d_slicer_records_the_voxel_values():
    from nanofactorysystem.aerobasic.programs.drawings.model3d import Model3D_Slicer
    from nanofactorysystem.devices.coordinate_system import Point3D

    with pytest.raises(ValueError, match="laser power"):
        Model3D_Slicer(Point3D(0, 0, 0), box(), velocity=1000, voxel_model=FixedVoxelModel(WIDTH, HEIGHT))

    structure = Model3D_Slicer(Point3D(0, 0, 0), box(), velocity=1000, power=1.0, hatch_size=0.4, slice_size=0.5,
                               spacing_mode="static_hatching", voxel_model=FixedVoxelModel(WIDTH, HEIGHT))
    data = structure.to_json()
    assert data["voxel"]["mode"] == "static_hatching" and data["voxel"]["width_um"] == WIDTH
    assert data["params"]["slicing"]["hatch_spacing_um"] == 0.4
    assert data["params"]["slicing"]["contour_offset_um"] == WIDTH / 2
    assert data["params"]["laser"]["power_mw"] == 1.0


def test_job_file_keeps_the_voxel_parameters(tmp_path):
    pytest.importorskip("h5py")
    from nanofactorysystem.aerobasic.slicer import read_params, save_job

    job = slice_geometry(box(), params(spacing_mode="static_hatching"), voxel_model=FixedVoxelModel(WIDTH, HEIGHT))
    save_job(job, tmp_path / "job.h5")
    assert read_params(tmp_path / "job.h5") == job.params


@pytest.mark.parametrize("objective, speed_mm_s", [("Zeiss 63x", 5), ("Zeiss 20x", 10)])
def test_voxel_lookup_uses_the_ifov_writing_speed(objective, speed_mm_s, tmp_path):
    from nanofactorysystem.aerobasic.programs.drawings.model3d import Model3D_Slicer
    from nanofactorysystem.backends.dummy.attenuator import write_calibration_file
    from nanofactorysystem.backends.dummy.world import SimulatedWorld
    from nanofactorysystem.devices.coordinate_system import CoordinateSystem, Point3D, Unit
    from nanofactorysystem.devices.power_calibration import PowerCalibration, power_calibration

    queried = []

    class Recording(FixedVoxelModel):
        def voxel_size(self, power_mw, velocity_um_s):
            queried.append(velocity_um_s)
            return super().voxel_size(power_mw, velocity_um_s)

    # velocity=1000 does not change the IFOV writing speed (fixed per objective, T63)
    structure = Model3D_Slicer(Point3D(0, 0, 0), box(), velocity=1000, power=1.0, objective=objective,
                               hatch_size=1.0, slice_size=1.0, voxel_model=Recording(WIDTH, HEIGHT))
    calibration = write_calibration_file(tmp_path / "calibration.dat", SimulatedWorld())
    with power_calibration(PowerCalibration.from_file(calibration)):
        program = "\n".join(map(str, next(structure.iterate_layers(
            CoordinateSystem(offset_x=0.0, offset_y=0.0, z_function=0.0, unit=Unit.um))).lines))

    assert queried == [speed_mm_s * 1000.0]
    assert structure.to_json()["voxel"]["velocity_um_s"] == speed_mm_s * 1000.0
    assert f"F{speed_mm_s}" in program.replace(" ", "")
    assert structure.to_json()["velocity"] == 1000
