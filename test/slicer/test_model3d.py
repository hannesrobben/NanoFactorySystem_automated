"""Run the hardware-free Model3D_Slicer checks (model3d_checks.py) as a test."""
import runpy
import tempfile
from pathlib import Path

import pytest

CHECKS = Path(__file__).with_name("model3d_checks.py")


def test_model3d_checks(tmp_path, monkeypatch):
    pytest.importorskip("trimesh")
    pytest.importorskip("shapely")
    pytest.importorskip("h5py")
    # The checks create their files with tempfile.mkdtemp(); keep them in tmp_path
    monkeypatch.setattr(tempfile, "mkdtemp", lambda *args, **kwargs: str(tmp_path))

    result = runpy.run_path(str(CHECKS), run_name="model3d_checks")

    assert result["PASS"], "no check was executed"
    assert result["FAIL"] == [], f"failed checks: {result['FAIL']}"
