##########################################################################
# Copyright (c) 2026 Hannes Robben                                       #
# <hannes.robben@phoenixd.uni-hannover.de>                               #
# This program is free software under the terms of the MIT license.      #
##########################################################################
"""Reading experiment folders written before the experiment file existed (design §9, D7).

Such a folder has ``experiment_dictionary.json``, ``structures.json`` (after
building), ``print_progress.json`` (after printing started) and a log file.
"""
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .records import StructureRecord

UUID_PATTERN = re.compile(r"Experiment ([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})")


@dataclass
class LegacyExperiment:
    """ What can be recovered from an old experiment folder.

    Parameters
    ----------
    uuid : str, optional
        Experiment UUID from the QR-code structure or the log file; None if
        it cannot be recovered.
    structures : list of StructureRecord
        Built structures with layer files relative to the folder when the
        files exist there.
    attempted : dict
        Structure name → layer ids that were printed (or failed) according to
        ``print_progress.json`` (the old format, or schema
        ``nanofactory.print_progress/2``).
    finished : set of str
        Structures that were completed.
    """

    uuid: Optional[str]
    structures: list[StructureRecord] = field(default_factory=list)
    attempted: dict[str, set[int]] = field(default_factory=dict)
    finished: set[str] = field(default_factory=set)


def is_legacy_folder(folder: Path) -> bool:
    """ Return True for a folder with ``experiment_dictionary.json`` but without an experiment file. """

    folder = Path(folder)
    return (folder / "experiment_dictionary.json").is_file() and not (folder / "experiment.h5").exists()


def _layer_id(file: str) -> int:
    return int(str(file).split(".")[-2])


def _relocate(folder: Path, file: str, name: str) -> str:
    """ Map a stored (possibly absolute, possibly outdated) program path into ``folder``. """

    path = Path(file)
    if not path.is_absolute():
        return path.as_posix()
    candidates = [path, folder / "structures" / name / "programs" / path.name, folder / "structures" / name / path.name]
    for candidate in candidates:
        if candidate.exists():
            try:
                return candidate.resolve().relative_to(folder.resolve()).as_posix()
            except ValueError:
                return str(candidate)
    return str(path)


def _structure_type(name: str) -> tuple[str, str]:
    """ Structure type and corner position guessed from the name (old files do not store the type). """

    match = re.fullmatch(r"corner_(tl|tr|bl|br)", name)
    if match:
        return "CORNER", match.group(1).upper()
    if name == "qrcode":
        return "QRCODE", ""
    return "NORMAL", ""


def read_legacy(folder: Path, layer_order: int, setup: str) -> LegacyExperiment:
    """ Read an old experiment folder.

    Parameters
    ----------
    folder : Path
        Experiment folder.
    layer_order : int
        +1 if layers were printed with ascending ids (drop direction UP), -1 otherwise.
    setup : str
        IFOV setup of the experiment.

    Returns
    -------
    LegacyExperiment
    """

    folder = Path(folder)
    configs = []
    if (folder / "structures.json").is_file():
        configs = json.loads((folder / "structures.json").read_text())

    # UUID: text of the QR code, else the first "Experiment <uuid>" log line
    uuid = next((c["structure"]["__init__"].get("text") for c in configs
                 if c.get("structure", {}).get("__class__") == "QRCode"), None)
    if uuid is None:
        for log in sorted(folder.glob("*.log")):
            match = UUID_PATTERN.search(log.read_text(errors="replace"))
            if match:
                uuid = match.group(1)
                break

    structures = []
    for index, config in enumerate(configs):
        name = config["name"]
        structure_type, corner = _structure_type(name)
        structures.append(StructureRecord(
            index=index, name=name, type=structure_type, grid_index=-1, corner_position=corner,
            axes=config.get("axes", ""), setup=setup,
            center_um=(config["center_x"], config["center_y"], config.get("center_z", float("nan"))),
            reference_um=(config["center_x"], config["center_y"]), power_mw=float(config["power"]),
            structure_class=config.get("structure", {}).get("__class__", ""), config=config.get("structure", {}),
            layer_files=[_relocate(folder, f, name) for f in config["layer_files"]],
            program_file=_relocate(folder, config["program_file"], name) if config.get("program_file") else "",
            layer_order=layer_order, dhm_image_count=int(config.get("number of dhm images", 0))))

    # Progress: finished structures and the layers of the interrupted one
    legacy = LegacyExperiment(uuid=uuid, structures=structures)
    progress_file = folder / "print_progress.json"
    if progress_file.is_file():
        progress = json.loads(progress_file.read_text())
        if str(progress.get("schema", "")).startswith("nanofactory.print_progress/"):
            # Newer copy exported from an experiment file (e.g. when only the JSON copies are left)
            for entry in progress["structures"]:
                legacy.attempted[entry["name"]] = {layer["layer_id"] for layer in entry["layers"]}
                if entry["status"] in ("printed", "failed"):
                    legacy.finished.add(entry["name"])
            return legacy
        by_name = {s.name: s for s in structures}
        for done in progress.get("finished_structures", []):
            legacy.finished.add(done["name"])
            if done["name"] in by_name:
                legacy.attempted[done["name"]] = {_layer_id(f) for f in by_name[done["name"]].layer_files}
        current = progress.get("current_structure") or {}
        if current.get("name") in by_name and current.get("finished layer") is not None:
            last, order = int(current["finished layer"]), int(current.get("order") or layer_order)
            ids = [_layer_id(f) for f in by_name[current["name"]].layer_files]
            legacy.attempted[current["name"]] = {i for i in ids if (i - last) * order <= 0}
    return legacy
