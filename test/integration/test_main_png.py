"""The PNG height map entry script mains/main_PNG.py (T116)."""
import importlib.util
import json
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

from nanofactorysystem.devices.coordinate_system import Point2D
from nanofactorysystem.experiment import StructureType
from nanofactorysystem.resin_drop import ellipse_through
from nanofactorysystem.storage import ExperimentStore

MAINS = Path(__file__).parents[2] / "mains"


@pytest.fixture
def main_png(monkeypatch, tmp_path):
    """ mains/main_PNG.py with a 40 x 20 px 16-bit PNG (a 2 µm block in the middle). """

    monkeypatch.syspath_prepend(str(MAINS))  # the script imports main.py from mains/
    monkeypatch.delitem(sys.modules, "main", raising=False)
    spec = importlib.util.spec_from_file_location("main_PNG", MAINS / "main_PNG.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    image = np.zeros((20, 40), dtype=np.uint16)
    image[5:15, 10:30] = 2000  # 2 µm at 0.001 µm per gray value
    png = tmp_path / "block.png"
    assert cv2.imwrite(str(png), image)
    monkeypatch.setattr(module, "PNG", png)
    monkeypatch.setattr(module, "PIXEL_SIZE_UM", 1.0)
    monkeypatch.setattr(module, "HEIGHT_PER_GRAY_UM", 0.001)
    monkeypatch.setattr(module, "SLICE_UM", 0.5)
    return module


def test_structure_from_the_image_settings(main_png):
    height_map = main_png.structure()
    assert (height_map.n_cols, height_map.n_rows) == (40, 20)
    assert (height_map.width, height_map.length) == (40.0, 20.0)
    assert height_map.max_height == pytest.approx(2.0)
    assert height_map.center.Z == -main_png.SUBSTRATE_DEPTH_UM
    assert height_map.objective == main_png.settings.OBJECTIVE
    assert height_map.png_sha256 is not None


def test_spec_is_one_ifov_structure_in_the_drop_center(main_png, monkeypatch):
    monkeypatch.setattr(main_png, "CENTER", None)  # the SETTINGS block may hold a lab value (T122)
    spec = main_png.experiment_spec(main_png.structure())
    drop = ellipse_through(main_png.settings.RESIN_EDGES)
    assert spec.name == "png_block"
    assert spec.center == Point2D(round(drop.cx), round(drop.cy))
    assert spec.setup == "IFOV_on" and spec.grid == (1, 1) and not spec.dhm_usage
    assert spec.structure_size_um == 40.0 + main_png.MARGIN_AROUND_UM
    [structure] = spec.structures
    assert structure.name == "block" and structure.structure_type == StructureType.IFOV
    assert structure.power_mw == main_png.POWER_MW


def test_explicit_center(main_png, monkeypatch):
    monkeypatch.setattr(main_png, "CENTER", Point2D(100, 200))
    assert main_png.experiment_spec(main_png.structure()).center == Point2D(100, 200)


def test_preview_only_needs_no_hardware(main_png):
    stats = main_png.run(preview_only=True, dry=True)
    assert stats["layers"] > stats["socket_layers"] > 0
    assert stats["lines"] > 0


def test_script_imports_main_from_any_working_directory(tmp_path):
    # The script puts mains/ on sys.path itself (ModuleNotFoundError: No module named 'main' before)
    import subprocess
    result = subprocess.run([sys.executable, str(MAINS / "main_PNG.py"), "--help"], cwd=tmp_path,
                            capture_output=True, text=True, timeout=300)
    assert result.returncode == 0, result.stderr
    assert "--dry-run" in result.stdout


@pytest.mark.slow
def test_dry_run_into_a_substrate(main_png, tmp_path, monkeypatch):
    monkeypatch.setattr(main_png, "SUBSTRATE_LABEL", "TU-26-PNG")
    folder = main_png.run(dry=True, workdir=tmp_path / "dry")
    assert (folder / "experiment.h5").is_file()
    record = ExperimentStore(folder).read()
    assert [s.name for s in record.structures if s.name == "block"] == ["block"]
    assert record.substrate_label == "TU-26-PNG" and folder.parent.name == "TU-26-PNG"
    assert folder.parent.parent == tmp_path / "dry" / "data_root"
    layout = json.loads((folder.parent / "substrate_layout.json").read_text())
    assert [(e["name"], e["state"]) for e in layout["experiments"]] == [("png_block", "done")]
    assert (folder.parent / "substrate_layout.png").is_file()


@pytest.mark.slow
def test_dry_run_without_substrate(main_png, tmp_path, monkeypatch):
    monkeypatch.setattr(main_png, "SUBSTRATE_LABEL", None)
    folder = main_png.run(dry=True, workdir=tmp_path / "dry")
    assert folder.parent == tmp_path / "dry" / "out"
    assert ExperimentStore(folder).read().substrate_label == ""
