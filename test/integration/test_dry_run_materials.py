"""Material snapshots in the experiment file of a dry run (T75)."""
import pytest

from nanofactorysystem.aerobasic.programs.drawings.lines import Rectangle3D
from nanofactorysystem.devices.coordinate_system import Point2D, Point3D
from nanofactorysystem.experiment_spec import ExperimentSpec, StructureSpec, run_experiment
from nanofactorysystem.storage import ExperimentStore
from nanofactorysystem.storage.substrate_store import SubstrateStore
from nanofactorysystem.substrate_plan import SubstrateExperiment, SubstrateSpec, run_substrate
from nanofactorysystem.voxel import MaterialRegistry, MaterialSnapshot

RESIN_EDGES = [[5720, 22330], [-3333, 22420], [1660, 17212], [1200, 27190]]


def spec(name="materials", **kwargs):
    structure = Rectangle3D(Point3D(0, 0, -1), 20, 20, 2, hatch_size=2.0, slice_size=1.0, velocity=1000,
                            acceleration=500)
    return ExperimentSpec(name=name, objective="Zeiss 20x", center=Point2D(1310, 19500), grid=(1, 1),
                          skip_corner=True, structures=[StructureSpec("rect", structure)], **kwargs)


@pytest.fixture
def registry(tmp_path):
    with MaterialRegistry(tmp_path / "materials.sqlite") as reg:
        reg.add_material("ResinX", supplier="Lab")
        reg.add_property("ResinX", "refractive_index", 1.48, "1", wavelength_nm=633, state="uncured")
        reg.add_property("ResinX", "refractive_index", 1.52, "1", wavelength_nm=633, state="cured")
        reg.add_property("ResinX", "photoinitiator", "Irgacure 369")
        reg.add_material("cover slip glass", kind="substrate")
        yield reg


@pytest.mark.slow
def test_substrate_resin_by_registry_name(test_config, dummy_backend, no_sleep, tmp_path, registry):
    import matplotlib
    matplotlib.use("Agg")
    substrate = SubstrateSpec(user="Test", objective="Zeiss 20x", resin_edges=RESIN_EDGES, label="TU-26-009",
                              material="ResinX", data_root=tmp_path / "root")

    folders = run_substrate(substrate, [SubstrateExperiment(spec(materials={"substrate": "cover slip glass"}))],
                            backend=dummy_backend, plane=dummy_backend.world.sample.plane(),
                            material_registry=registry)

    assert SubstrateStore(tmp_path / "root").get("TU-26-009").material == {"resin": "ResinX"}
    record = ExperimentStore.open(folders[0]).read()
    resin = MaterialSnapshot.from_dict(record.materials["resin"])
    assert resin.known and resin.name_source == "substrate"
    assert resin.registry_file == str(registry.database.path)
    assert resin.refractive_index(633, "cured") == 1.52 and resin.refractive_index(633, "uncured") == 1.48
    assert resin.material.property("photoinitiator").value == "Irgacure 369"
    assert record.materials["substrate"]["name"] == "cover slip glass" and record.materials["substrate"]["known"]
    # M4: the names reach the sample section the tools read
    assert record.system["sys_args"]["sample"]["material"] == "ResinX"
    assert record.system["sys_args"]["sample"]["substrate"] == "cover slip glass"
    assert record.schema_version == "1.3"


@pytest.mark.slow
def test_without_registry_only_names_are_stored(test_config, dummy_backend, no_sleep, tmp_path):
    import matplotlib
    matplotlib.use("Agg")

    folder = run_experiment(spec(), user="Test", resin_edges=RESIN_EDGES, path=tmp_path / "out",
                            backend=dummy_backend, plane=dummy_backend.world.sample.plane())

    materials = ExperimentStore.open(folder).read().materials
    # The template's sys_args name SZ2080 on boro-silicate glass; no registry file exists (conftest)
    assert {role: (m["name"], m["known"], m["name_source"]) for role, m in materials.items()} == {
        "resin": ("SZ2080", False, "sys_args"), "substrate": ("boro-silicate glass", False, "sys_args")}
