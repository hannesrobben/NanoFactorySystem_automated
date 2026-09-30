"""Unit tests for the experiment summary (storage/summary.py)."""
from nanofactorysystem.storage import ExperimentRecord, StructureRecord
from nanofactorysystem.storage.summary import COLUMNS, format_table, print_parameters, summary


def structure(name, type_="NORMAL", cls="lines.Rectangle3D", arguments=None, status="printed", setup="IFOV_off"):
    return StructureRecord(
        index=0, name=name, type=type_, grid_index=0, corner_position="", axes="ABZ", setup=setup,
        center_um=(100.0, 200.0, 20000.0), reference_um=(100.0, 200.0), power_mw=0.7,
        structure_class=f"nanofactorysystem.aerobasic.programs.drawings.{cls}",
        config={"__class__": cls.rsplit(".", 1)[-1], "__init__": arguments or {}},
        layer_files=["a.000.txt", "a.001.txt"], program_file="a.txt", layer_order=1, dhm_image_count=10,
        status=status)


def test_print_parameters_from_constructor_arguments():
    rect = structure("rect", arguments={"slice_size": 0.5, "hatch_size": 0.25, "velocity": 1000})
    assert print_parameters(rect) == {"slice_um": 0.5, "hatch_um": 0.25, "velocity": 1000.0,
                                      "velocity_unit": "um/s", "power_mw": 0.7, "voxel_width_um": None,
                                      "voxel_height_um": None}
    corner = structure("corner", arguments={"slice_size": 0.75, "hatch_size": 0.5, "F": 5000.0})
    assert print_parameters(corner)["velocity"] == 5000.0
    # IFOV structures set their own power (D5) and take the velocity in mm/s
    ifov = structure("grating", cls="lines.IFOV_Lines", arguments={"power": 3.5, "velocity": 10})
    assert print_parameters(ifov)["power_mw"] == 3.5 and print_parameters(ifov)["velocity_unit"] == "mm/s"
    assert print_parameters(structure("empty"))["slice_um"] is None


def test_print_parameters_of_slicer_structures():
    # Model3D_Slicer stores the job parameters (after voxel compensation, T54) and the voxel values used
    slicer = structure("block", cls="model3d.Model3D_Slicer")
    slicer.config = {"type": "Model3D_Slicer", "velocity": 5, "power": 0.3,
                     "params": {"slicing": {"layer_height_um": 1.05, "hatch_spacing_um": 0.7}},
                     "voxel": {"width_um": 1.0, "height_um": 1.5}}
    assert print_parameters(slicer) == {"slice_um": 1.05, "hatch_um": 0.7, "velocity": 5.0, "velocity_unit": "mm/s",
                                        "power_mw": 0.3, "voxel_width_um": 1.0, "voxel_height_um": 1.5}
    slicer.config = {"type": "Model3D_Slicer", "velocity": 5, "power": None,
                     "params": {"slicing": {"layer_height_um": 0.1, "hatch_spacing_um": 0.1}}, "voxel": None}
    parameters = print_parameters(slicer)
    assert parameters["power_mw"] == 0.7 and parameters["voxel_width_um"] is None  # experiment power, no data


def test_summary_rows_exclude_markers_and_count_layers():
    record = ExperimentRecord(
        uuid="u1", label="HR-26-001-A", parameters={"setup": "IFOV_on", "drop_direction": "UP", "plane_fit_mode": 1,
                                                    "dhm_usage": True},
        objective={"key": "Zeiss 63x"}, status="printing",
        structures=[structure("corner_tl", "CORNER"), structure("qrcode", "QRCODE"),
                    structure("rect", status="failed", setup="IFOV_on"), structure("stair", status="pending")],
        progress={"rect": [{"status": "ok"}, {"status": "failed"}]})

    data = summary(record)

    assert data["experiment_uuid"] == "u1" and data["objective"] == "Zeiss 63x" and data["dhm_usage"] is True
    assert [row["name"] for row in data["structures"]] == ["rect", "stair"]
    rect = data["structures"][0]
    assert list(rect) == list(COLUMNS)
    assert (rect["printed_layers"], rect["n_layers"], rect["status"], rect["ifov"], rect["dhm"]) == (
        1, 2, "failed", True, True)
    table = format_table(data)
    assert "HR-26-001-A" in table and "rect" in table and "corner_tl" not in table
    assert "(no user structures)" in format_table({**data, "structures": []})
