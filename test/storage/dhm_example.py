"""Example experiment file with DHM service results (docs/design/EXPERIMENT_STORAGE.md §15, schema 1.3).

``write_dhm_example(folder)`` builds a small ``experiment.h5`` with every item of §15: a reserved and a
stored service capture (``ProductSet`` with frame records and raw reference), the DHM session record and
parameter set (T79), a stitched ``LayerProduct``
group of two member captures, a failed capture, an orphan reference, a background calibration and a legacy
capture. The values are synthetic; the product headers start from the contract examples of DHMConnect
(vendored in ``data/contracts``, see its ``MANIFEST.json``), so they are valid ``ProductSet`` 1.0 and
``LayerProduct`` 1.0 messages. The file is the fixture that OffAxisHolo (K12), MIRA (MI-62) and DHMConnect
vendor; regenerate it with::

    python test/storage/dhm_example.py <target folder>
"""
import copy
import json
import sys
from pathlib import Path

import numpy as np

from nanofactorysystem.storage import CaptureRecord, ExperimentRecord, ExperimentStore, StructureRecord

EXPERIMENT_UUID = "6b1f3c1e-2d4a-4f7e-9c0a-1b2c3d4e5f60"
CONFIG_HASH = "af2c68e689d640b9bbfd8f9e0cdaa6923aab578f591682466bbd4bdf5ec8a38f"
PARAMETER_SET_ID = "zeiss63x-insitu-v1"
SHAPE = (16, 16)
PIXEL_UM = [0.1738, 0.1738]
CONTRACTS = Path(__file__).parent / "data" / "contracts"


def _example(name: str) -> dict:
    return json.loads((CONTRACTS / f"{name}.example.json").read_text(encoding="utf-8"))


def _record() -> ExperimentRecord:
    return ExperimentRecord(
        uuid=EXPERIMENT_UUID, label="HR-26-099_EX01",
        parameters={"center_um": np.array([1000.0, 1000.0]), "grid": np.array([1, 1]), "setup": "IFOV_on",
                    "drop_direction": "DOWN", "skip_corner": True, "default_power_mw": 0.5},
        user={"key": "example", "name": "Example"}, objective={"key": "Zeiss 63x", "magnification": 63.0},
        system={"sys_args": {}, "backend": "dummy"}, software={"package_version": "0.7.0", "git_commit": ""})


def _structure() -> StructureRecord:
    return StructureRecord(
        index=0, name="pillar_03", type="NORMAL", grid_index=0, corner_position="", axes="XYZ", setup="IFOV_on",
        center_um=(1000.0, 1000.0, 20000.0), reference_um=(1000.0, 1000.0), power_mw=0.5,
        structure_class="example.Pillar", config={}, layer_files=[], program_file="", layer_order=1,
        dhm_image_count=1)


def _capture(layer_id: int, index: int, offset_um=(0.0, 0.0)) -> CaptureRecord:
    return CaptureRecord(kind="dhm", structure="pillar_03", phase="layer", layer_id=layer_id, image_index=index,
                         image_count=2, offset_um=offset_um, commanded_um=(1000.0 + offset_um[0],
                                                                           1000.0 + offset_um[1], None, 0.0, 0.0),
                         actual_um={"X": 1000.0 + offset_um[0], "Y": 1000.0 + offset_um[1], "Z": 20000.0,
                                    "A": 0.0, "B": 0.0},
                         time="2026-11-26T12:00:00.000Z")


def _buffers(seed: int, field: bool = False) -> list:
    rng = np.random.default_rng(seed)
    phase = rng.normal(0.0, 0.1, SHAPE).astype(np.float32)
    intensity = np.ones(SHAPE, np.float32)
    valid = np.ones(SHAPE, np.uint8)
    buffers = [("phase_rad", phase), ("intensity_rel", intensity), ("valid", valid)]
    if field:
        buffers.append(("field", (np.sqrt(intensity) * np.exp(1j * phase)).astype(np.complex64)))
    return buffers


def _descriptors(buffers: list) -> list:
    return [{"name": name, "dtype": str(data.dtype), "shape": list(data.shape), "byte_order": "little"}
            for name, data in buffers]


def product_set_header(capture_id: str, job_id: str, buffers: list, tile_index: int = 0) -> dict:
    """ A ``ProductSet`` 1.0 header (contract example with this capture's ids) with one used and one rejected frame. """

    header = copy.deepcopy(_example("ProductSet"))
    frames = [
        {"index": 0, "used": True, "reject_reason": None,
         "metrics": {"saturated_count": 0, "sideband_fraction": 0.081, "piston_rad": 0.12, "phase_noise_rad": None},
         "acquisition": {"frame_id": 1201, "exposure_us": 16800, "camera_time_s": 1021.334,
                         "host_utc": "2026-11-26T12:00:00.201Z"}},
        {"index": 1, "used": False, "reject_reason": "gated: sideband_fraction",
         "metrics": {"saturated_count": 3, "sideband_fraction": 0.02, "piston_rad": 0.40, "phase_noise_rad": 0.09},
         "acquisition": {"frame_id": 1202, "exposure_us": 16800, "camera_time_s": 1021.367,
                         "host_utc": "2026-11-26T12:00:00.234Z"}},
    ]
    recon = header["reconstruction"]
    recon.update({"created_utc": "2026-11-26T12:00:01.000Z", "pixel_um": PIXEL_UM, "z_um": -2.4,
                  "propagation_index": 1.508, "wavelength_um": 0.674994, "parameter_set_id": PARAMETER_SET_ID,
                  "config_hash": CONFIG_HASH, "frames": frames, "buffers": _descriptors(buffers)})
    recon["quality"].update({"n_frames_total": 2, "n_frames_used": 1, "background_id": "bg-0001",
                             "background_created_utc": "2026-11-26T11:55:00Z", "background_age_s": 300.0})
    header["capture"].update({"experiment_uuid": EXPERIMENT_UUID, "structure_id": "pillar_03", "layer_index": 4,
                              "capture_id": capture_id, "image_index": tile_index, "group_id": "grp-0001",
                              "tile_index": tile_index,
                              "position_commanded_um": {"x": 1000.0 + 2.0 * tile_index, "y": 1000.0, "z": 20000.0},
                              "position_actual_um": {"x": 1000.0 + 2.0 * tile_index, "y": 1000.0, "z": 20000.0},
                              "occupied_um": [[[999.0, 999.5], [999.0, 1002.5], [1001.0, 1002.5], [1001.0, 999.5]]]})
    header.update({"product_id": f"ps-{capture_id}", "context_id": "ctx-example", "job_id": job_id,
                   "background_id": "bg-0001", "parameter_set_id": PARAMETER_SET_ID, "config_hash": CONFIG_HASH,
                   "raw_ref": {"host": "dhm-pc",
                               "path": f"D:/raw/{EXPERIMENT_UUID}/captures/{capture_id}_{job_id}.h5",
                               "sha256": "0" * 64, "n_frames": 2, "keep_raw": "all"},
                   "created_utc": "2026-11-26T12:00:01.000Z"})
    return header


def layer_product_header(group_id: str, job_id: str, member_ids: list, buffers: list) -> dict:
    """ A ``LayerProduct`` 1.0 header (contract example with this group's ids), one tile per member. """

    header = copy.deepcopy(_example("LayerProduct"))
    template = header["tiles"][0]
    tiles = []
    for i, pid in enumerate(member_ids):
        tile = copy.deepcopy(template)
        tile.update({"product_id": pid, "tile_index": i,
                     "planned_um": {"x": 1000.0 + 2.0 * i, "y": 1000.0, "z": 20000.0},
                     "actual_um": {"x": 1000.0 + 2.0 * i, "y": 1000.0, "z": 20000.0}})
        tiles.append(tile)
    header.update({"product_id": f"lp-{group_id}", "context_id": "ctx-example", "job_id": job_id,
                   "group_id": group_id, "experiment_uuid": EXPERIMENT_UUID, "structure_id": "pillar_03",
                   "layer_index": 4, "tiles": tiles, "member_ids": member_ids,
                   "parameter_set_id": PARAMETER_SET_ID, "config_hash": CONFIG_HASH, "background_ids": ["bg-0001"],
                   "buffers": _descriptors(buffers), "created_utc": "2026-11-26T12:00:05.000Z"})
    header["grid"].update({"origin_um": [998.6, 998.6], "pixel_um": PIXEL_UM, "shape": list(SHAPE)})
    header["quality"].update({"n_tiles": len(tiles), "n_flagged": 0})
    return header


def group_spec() -> dict:
    """ The ``GroupSpec`` 1.0 of the example layer (contract example with the two member positions). """

    spec = copy.deepcopy(_example("GroupSpec"))
    spec["structure"].update({"structure_id": "pillar_03",
                              "occupied_um": [[[999.0, 999.5], [999.0, 1002.5], [1001.0, 1002.5], [1001.0, 999.5]]]})
    spec["layer_index"] = 4
    # tiles of 16 x 16 px (2.8 µm): border band and overlap scaled down from the contract example
    spec["stitching"].update({"border_band_um": 0.3, "min_overlap_um": 0.5})
    spec["positions"] = [{"tile_index": i, "planned_um": {"x": 1000.0 + 2.0 * i, "y": 1000.0, "z": 20000.0},
                          "role": "ring", "n_frames": 2} for i in range(2)]
    return spec


def write_dhm_example(folder) -> Path:
    """ Write the example experiment into ``folder`` (created) and return the path of ``experiment.h5``. """

    store = ExperimentStore.create(Path(folder), _record())
    store.begin_session("new")
    try:
        store.add_structure(_structure())
        # DHM configuration of the session and the parameter set once per hash (T79, section 15.4)
        store.write_dhm_session({"adapter": "service", "service_version": "0.1.0", "protocol_version": "1.0",
                                 "software_versions": {"dhmconnect": "0.1.0", "offaxisholo": "0.4.0"},
                                 "parameter_set_id": PARAMETER_SET_ID, "config_hash": CONFIG_HASH,
                                 "pixel_um": PIXEL_UM, "pixel_source": "parameter_set",
                                 "camera": {"model": "Basler acA1300", "bit_depth": 8}, "objective": "Zeiss 63x"})
        store.write_parameter_set(CONFIG_HASH, PARAMETER_SET_ID,
                                  {"parameter_set_id": PARAMETER_SET_ID, "wavelength_um": 0.674994,
                                   "objective": {"magnification": 63.0, "pixel_um": PIXEL_UM}})
        recipe = {"mode": "products", "frames": 2, "selection_policy": "all", "keep_raw": "all"}
        context = {"experiment_uuid": EXPERIMENT_UUID, "structure": "pillar_03", "layer": 4, "z_hint_um": -2.4}
        # A stitched layer: two member captures of one group (N1, N2)
        members = []
        for i in range(2):
            capture_id = store.reserve_capture(_capture(4, i, (2.0 * i, 0.0)), recipe=recipe,
                                               context={**context, "image_index": i}, group_id="grp-0001",
                                               config_hash=CONFIG_HASH, parameter_set_id=PARAMETER_SET_ID)
            job_id = f"job-{100 + i}"
            store.update_capture_job(capture_id, job_state="sent", job_id=job_id)
            buffers = _buffers(i)
            store.add_dhm_result(capture_id, product_set_header(capture_id, job_id, buffers, i), buffers)
            store.update_capture_job(capture_id, job_state="acknowledged")
            members.append(capture_id)
        buffers = _buffers(10, field=True)
        header = layer_product_header("grp-0001", "job-110", [f"ps-{m}" for m in members], buffers)
        store.add_layer_product("grp-0001", header, buffers, kind="layer", structure="pillar_03", phase="layer",
                                layer_id=4, members=members, job_id="job-110", job_state="acknowledged",
                                group_spec=group_spec(), recipe=recipe)
        # A capture still waiting for its result and a failed one
        store.reserve_capture(_capture(5, 0), recipe=recipe, context=context, config_hash=CONFIG_HASH,
                              parameter_set_id=PARAMETER_SET_ID)
        failed = store.reserve_capture(_capture(5, 1), recipe=recipe, context=context)
        store.update_capture_job(failed, job_state="failed", job_id="job-121", error="busy")
        # Orphan reference (SI4) and a background calibration
        store.add_dhm_orphan("job-099", {"result_id": "ps-x", "message_type": "ProductSet", "structure": "pillar_03",
                                         "layer_id": 3, "time": "2026-11-26T11:59:00Z", "host": "dhm-pc",
                                         "path": "D:/results/ps-x.h5", "sha256": "1" * 64, "size_bytes": 4096,
                                         "reason": "unknown capture after restart"})
        store.write_dhm_calibration("background", "bg-0001", parameters={"frames": 10},
                                    result={"background_id": "bg-0001", "n_frames": 10}, job_id="job-090")
        # A legacy capture (hologram series stored here, no service attributes)
        legacy = _capture(-1, 0)
        legacy.phase = "after"
        store.add_capture(legacy, np.zeros((2,) + SHAPE, np.uint8), device={"dhm": "legacy"},
                          capture_times_s=[0.1, 0.1])
    finally:
        store.end_session("finished")
    return store.path


if __name__ == "__main__":
    print(write_dhm_example(sys.argv[1] if len(sys.argv) > 1 else "dhm_example"))
