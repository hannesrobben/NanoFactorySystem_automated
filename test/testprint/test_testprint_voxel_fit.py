"""Fitted voxel models w(P), l(P) (T150)."""
import json
import math

import numpy as np
import pytest

from nanofactorysystem.experiment_spec import SpecSerialisationError
from nanofactorysystem.testprint.voxel_fit import ModelKind, VoxelFitModel, model_kinds, register_model_kind
from nanofactorysystem.voxel.materials import MissingPropertyError

THRESHOLD = dict(w_scale_um=0.4, l_scale_um=1.2, p_th_mw=0.3, n_eff=2.0)


def threshold_model(**overrides):
    arguments = dict(kind="threshold_ln", params=THRESHOLD, valid_power_mw=(0.33, 1.0), velocity_um_s=5000.0,
                     source="synthetic")
    arguments.update(overrides)
    return VoxelFitModel(**arguments)


def test_threshold_ln_reproduces_known_points():
    model = threshold_model()
    for power in (0.33, 0.5, 1.0):
        expected = math.sqrt(2.0 * math.log(power / 0.3))
        assert model.width_um(power) == pytest.approx(0.4 * expected)
        assert model.length_um(power) == pytest.approx(1.2 * expected)
    # same as d_scale * sqrt(ln((P/P_th)^n))
    assert model.width_um(0.6) == pytest.approx(0.4 * math.sqrt(math.log((0.6 / 0.3) ** 2)))


def test_power_law_and_tabulated_reproduce_known_points():
    law = VoxelFitModel("power_law", dict(p_th_mw=0.3, w_a=0.8, w_b=0.5, l_a=2.4, l_b=0.5), (0.31, 1.0), 5000.0)
    assert law.width_um(0.7) == pytest.approx(0.8 * 0.4 ** 0.5)
    assert law.length_um(0.7) == pytest.approx(2.4 * 0.4 ** 0.5)
    table = VoxelFitModel("tabulated", dict(power_mw=[0.4, 0.6, 1.0], width_um=[0.2, 0.3, 0.5],
                                            length_um=[0.6, 0.9, 1.5]), (0.4, 1.0), 5000.0)
    assert table.width_um(0.6) == pytest.approx(0.3)
    assert table.width_um(0.8) == pytest.approx(0.4)
    assert table.length_um(0.5) == pytest.approx(0.75)


@pytest.mark.parametrize("power", [0.2, 0.32, 1.01])
def test_no_extrapolation(power):
    model = threshold_model()
    with pytest.raises(ValueError, match="no extrapolation"):
        model.width_um(power)
    with pytest.raises(ValueError, match="no extrapolation"):
        model.voxel_size(power, 5000.0)


def test_other_velocity_raises():
    with pytest.raises(ValueError, match="fitted at 5000"):
        threshold_model().voxel_size(0.5, 10000.0)


def test_slicer_protocol():
    size = threshold_model().voxel_size(0.5, 5000.0)
    assert size.width_um == pytest.approx(threshold_model().width_um(0.5))
    assert size.height_um == pytest.approx(threshold_model().length_um(0.5))
    assert size.width_method == "fit-threshold_ln"
    assert threshold_model().describe()["kind"] == "threshold_ln"


@pytest.mark.parametrize("model", [
    threshold_model(),
    VoxelFitModel("power_law", dict(p_th_mw=0.3, w_a=0.8, w_b=0.5, l_a=2.4, l_b=0.5), (0.31, 1.0), 5000.0),
    VoxelFitModel("tabulated", dict(power_mw=[0.4, 1.0], width_um=[0.2, 0.5], length_um=[0.6, 1.5]), (0.4, 1.0),
                  5000.0, residuals={"w_rms_um": 0.01}),
])
def test_json_round_trip(model, tmp_path):
    again = VoxelFitModel.from_json(json.loads(json.dumps(model.to_json())))
    assert again == model
    assert VoxelFitModel.load(model.save(tmp_path / "model.json")) == model
    assert again.width_um(0.5) == model.width_um(0.5)


def test_invalid_models():
    with pytest.raises(ValueError, match="Unknown voxel model kind"):
        threshold_model(kind="cubic")
    with pytest.raises(MissingPropertyError, match="n_eff"):
        threshold_model(params={k: v for k, v in THRESHOLD.items() if k != "n_eff"})
    with pytest.raises(ValueError, match="above p_th_mw"):
        threshold_model(valid_power_mw=(0.3, 1.0))
    with pytest.raises(ValueError, match="0 < low < high"):
        threshold_model(valid_power_mw=(1.0, 0.5))
    with pytest.raises(ValueError, match="inside the tabulated"):
        VoxelFitModel("tabulated", dict(power_mw=[0.4, 1.0], width_um=[0.2, 0.5], length_um=[0.6, 1.5]),
                      (0.3, 1.0), 5000.0)
    with pytest.raises(SpecSerialisationError, match="schema"):
        VoxelFitModel.from_json({"schema": "nanofactory.voxel_fit_model/9"})
    with pytest.raises(MissingPropertyError):
        VoxelFitModel.from_json({"schema": "nanofactory.voxel_fit_model/1", "kind": "threshold_ln"})


def test_new_kinds_register_without_changing_the_class():
    register_model_kind(ModelKind("constant_test", ("w_um", "l_um"), lambda p, _: p["w_um"], lambda p, _: p["l_um"]))
    assert "constant_test" in model_kinds()
    model = VoxelFitModel("constant_test", {"w_um": 0.3, "l_um": 0.9}, (0.1, 1.0), 5000.0)
    assert model.width_um(0.5) == 0.3 and model.length_um(0.5) == 0.9


def test_model3d_slicer_accepts_the_fit_model():
    pytest.importorskip("trimesh")
    pytest.importorskip("shapely")
    from nanofactorysystem.aerobasic.programs.drawings.model3d import Model3D_Slicer
    from nanofactorysystem.devices.coordinate_system import Point3D

    model = threshold_model()
    structure = Model3D_Slicer(Point3D(0, 0, 0), np.ones((40, 40)), velocity=5.0, power=0.5, pixel_size=0.1,
                               run_preprocess=False, voxel_model=model)
    voxel = structure.toolpath_job.meta["voxel"]
    assert voxel["width_um"] == pytest.approx(model.width_um(0.5))
    assert voxel["height_um"] == pytest.approx(model.length_um(0.5))
    assert voxel["model"]["kind"] == "threshold_ln"
