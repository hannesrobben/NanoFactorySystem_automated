"""Dry runs of experiments described by an ExperimentSpec, for both program sources (T51)."""
import numpy as np
import pytest

from nanofactorysystem.aerobasic.programs.drawings.lines import Rectangle3D, Stair
from nanofactorysystem.devices.coordinate_system import DropDirection, Point2D, Point3D
from nanofactorysystem.experiment import ProgramSource
from nanofactorysystem.experiment_spec import ExperimentSpec, StructureSpec, run_experiment
from nanofactorysystem.plane_fitting import PlaneFitMode
from nanofactorysystem.storage import ExperimentStore

RESIN_EDGES = [[5720, 22330], [-3333, 22420], [1660, 17212], [1200, 27190]]
CENTER = Point2D(1310, 19500)


def check_dry_run(world, backend, folder):
    runs = world.calllog.filter(device="program")
    assert runs and all(r.result["not_simulated"] == 0 for r in runs)
    assert backend.transport.unhandled == []
    record = ExperimentStore.open(folder).read()
    assert record.status == "finished" and all(s.status == "printed" for s in record.structures)
    return record


@pytest.mark.slow
def test_drawing_spec_dry_run(test_config, dummy_backend, no_sleep, tmp_path):
    import matplotlib
    matplotlib.use("Agg")
    spec = ExperimentSpec(
        name="drawing_test", objective="Zeiss 20x", center=CENTER, grid=(1, 3), skip_corner=True,
        structures=[
            StructureSpec("stair", Stair(Point3D(0, 0, -1), n_steps=2, step_height=1.0, step_length=10,
                                         step_width=20, socket_height=1.0, hatch_size=2.0, slice_size=1.0,
                                         velocity=1000, acceleration=500)),
            StructureSpec("rect", Rectangle3D(Point3D(0, 0, -1), 20, 20, 2, hatch_size=2.0, slice_size=1.0,
                                              velocity=1000, acceleration=500), axes="XYZ", power_mw=1.0,
                          repeat=1),
        ])

    folder = run_experiment(spec, user="Test", resin_edges=RESIN_EDGES, path=tmp_path / "out",
                            backend=dummy_backend, plane=dummy_backend.world.sample.plane())

    assert folder == tmp_path / "out" / "drawing_test"
    record = check_dry_run(dummy_backend.world, dummy_backend, folder)
    assert [s.name for s in record.structures] == ["stair", "rect", "rect_rep1"]
    assert record.parameters["program_source"] == "DRAWING"
    assert record.parameters["plane_fit_mode"] == "CORNERS" and record.parameters["drop_direction"] == "UP"
    assert record.parameters["structure_size_um"] == 500.0  # defaults of the objective
    assert record.system["sys_args"]["controller"]["zMax"] == 24550.0
    assert record.structure("rect").power_mw == 1.0 and not record.captures  # camera off by default


@pytest.mark.slow
def test_slicer_spec_dry_run(test_config, dummy_backend, no_sleep, tmp_path):
    import matplotlib
    matplotlib.use("Agg")
    pytest.importorskip("shapely")
    height_map = np.zeros((20, 20))
    height_map[5:15, 5:15] = 2.0  # a 10 x 10 um block, 2 um high (pixel size 1 um)
    spec = ExperimentSpec(
        name="slicer_test", objective="Zeiss 63x", center=CENTER, grid=(1, 1), skip_corner=True,
        program_source=ProgramSource.SLICER, setup="IFOV_on", plane_fit_mode=PlaneFitMode.GRID,
        structures=[StructureSpec("block", height_data=height_map,
                                  slicer={"velocity": 5, "hatch_size": 1.0, "slice_size": 1.0, "pixel_size": 1.0,
                                          "unit": "um"})])

    folder = run_experiment(spec, user="Test", resin_edges=RESIN_EDGES, path=tmp_path / "out",
                            backend=dummy_backend, plane=dummy_backend.world.sample.plane())

    record = check_dry_run(dummy_backend.world, dummy_backend, folder)
    block = record.structure("block")
    assert block.type == "IFOV" and block.structure_class.endswith("Model3D_Slicer") and block.n_layers >= 2
    assert record.parameters["program_source"] == "SLICER" and record.parameters["drop_direction"] == "DOWN"
    # IFOV programs switch the laser in IFOV mode; the dummy does not model those exposures, so the
    # programs are checked instead: IFOV on and galvo writing moves in every layer
    store = ExperimentStore.open(folder)
    for layer_id in range(block.n_layers):
        program = store.read_program("block", layer_id)
        assert "IFOV ON" in program and "LINEAR A" in program


@pytest.mark.slow
def test_slicer_spec_with_voxel_data_dry_run(test_config, dummy_backend, no_sleep, tmp_path):
    import matplotlib
    matplotlib.use("Agg")
    pytest.importorskip("shapely")
    from nanofactorysystem.storage.summary import summary
    from nanofactorysystem.voxel import VoxelDatabase

    database = tmp_path / "voxels.sqlite"
    with VoxelDatabase(database) as voxels:  # measured at the structure's power and velocity (5 mm/s)
        voxels.add_measurement("SZ2080", "Zeiss 63x", "IFOV_on", 0.3, 5000, width_um=1.0, height_um=1.5, method="SEM")
    height_map = np.zeros((20, 20))
    height_map[5:15, 5:15] = 3.0
    spec = ExperimentSpec(
        name="voxel_test", objective="Zeiss 63x", center=CENTER, grid=(1, 1), skip_corner=True,
        program_source=ProgramSource.SLICER, setup="IFOV_on", voxel_material="SZ2080", voxel_database=database,
        structures=[StructureSpec("block", height_data=height_map, power_mw=0.3,
                                  slicer={"velocity": 5, "hatch_size": 0.1, "slice_size": 0.1, "pixel_size": 1.0,
                                          "unit": "um"})])

    folder = run_experiment(spec, user="Test", resin_edges=RESIN_EDGES, path=tmp_path / "out",
                            backend=dummy_backend, plane=dummy_backend.world.sample.plane())

    record = check_dry_run(dummy_backend.world, dummy_backend, folder)
    voxel = record.structure("block").config["voxel"]
    assert voxel["width_um"] == 1.0 and voxel["height_um"] == 1.5 and voxel["mode"] == "voxel_overlap"
    assert voxel["model"]["material"] == "SZ2080" and voxel["model"]["setup"] == "IFOV_on"
    row = summary(record)["structures"][0]
    # Spacing derived from the voxel (overlap 0.3) instead of the 0.1 um given
    assert (row["voxel_width_um"], row["voxel_height_um"]) == (1.0, 1.5)
    assert row["hatch_um"] == pytest.approx(0.7) and row["slice_um"] == pytest.approx(1.05)
    assert row["power_mw"] == 0.3


def test_spec_validation():
    with pytest.raises(ValueError, match="IFOV_on"):
        ExperimentSpec("x", "Zeiss 63x", CENTER, (1, 1), program_source="slicer").resolved()
    with pytest.raises(ValueError, match="do not fit"):
        ExperimentSpec("x", "Zeiss 20x", CENTER, (1, 1),
                       structures=[StructureSpec("a", repeat=1)]).resolved()
    with pytest.raises(ValueError, match="objective"):
        ExperimentSpec("x", "Nikon 5x", CENTER, (1, 1)).resolved()
    with pytest.raises(ValueError, match="needs a structure"):
        StructureSpec("a").drawable(ProgramSource.DRAWING, "Zeiss 20x")
    spec = ExperimentSpec("x", "Zeiss 63x", CENTER, (2, 2), fov_um=100.0, drop_direction=DropDirection.UP).resolved()
    assert (spec.structure_size_um, spec.margin_um, spec.drop_direction) == (100.0, 50.0, DropDirection.UP)


@pytest.mark.slow
@pytest.mark.parametrize("example", ["drawing_spec", "slicer_spec"])
def test_template_examples_dry_run(example, test_config, dummy_backend, no_sleep, tmp_path):
    import importlib.util
    from pathlib import Path

    import matplotlib
    matplotlib.use("Agg")
    pytest.importorskip("shapely")
    script = Path(__file__).parents[2] / "mains" / "Experiments" / "experiment_template.py"
    spec_loader = importlib.util.spec_from_file_location("experiment_template", script)
    template = importlib.util.module_from_spec(spec_loader)
    spec_loader.loader.exec_module(template)

    spec = getattr(template, example)()
    # Smaller than on the lab PC, to keep the test fast: one structure, no corners, coarse slicing
    spec.structures = spec.structures[:1]
    spec.structures[0].repeat = 0
    spec.skip_corner = True
    if spec.structures[0].slicer:
        spec.structures[0].slicer.update({"hatch_size": 1.0, "slice_size": 1.0})
    else:
        spec.structures[0].structure = Rectangle3D(Point3D(0, 0, -1), 20, 20, 2, hatch_size=2.0, slice_size=1.0,
                                                   velocity=1000, acceleration=500)
    folder = template.main(spec, user="Test", path=tmp_path / "out", backend=dummy_backend,
                           plane=dummy_backend.world.sample.plane())

    check_dry_run(dummy_backend.world, dummy_backend, folder)
