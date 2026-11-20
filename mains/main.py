##########################################################################
# Copyright (c) 2026 Hannes Robben                                       #
# <hannes.robben@phoenixd.uni-hannover.de>                               #
# This program is free software under the terms of the MIT license.      #
##########################################################################
"""Main entry point of the Laser Nanofactory: one place for every task (T110).

Choose a task in the SETTINGS block below (or on the command line) and run this file with
``mains/`` as working directory::

    cd mains
    python main.py                          # the TASK of the SETTINGS block, on the lab hardware
    python main.py --task substrate         # another task
    python main.py --task demo --dry-run    # every task once on simulated hardware (no lab PC needed)

Tasks
-----
``experiment``  One experiment described by an ``ExperimentSpec``
                (``Experiments/default_experiment.py``: every setting explained).
``slicer``      The slicer example: a height map sliced and printed in IFOV mode.
``layout``      Check and plot where the experiments of SUBSTRATE_EXPERIMENTS lie on the resin
                drop, without hardware. Do this before ``substrate``.
``substrate``   Several experiments on one substrate: layout check, substrate index
                (``<data root>/<label>/substrate.json``), then one experiment after another.
``spec_file``   Run a stored experiment again from its project file ``experiment_spec.json``.
``restart``     Resume an aborted experiment from its ``experiment.h5`` (only missing layers).
``overview``    List the substrates and experiments in the data root.
``analyse``     Read an experiment file: summary, structures, captures; store an analysis
                result; unpack everything into PNG/CSV/TXT/JSON.
``materials``   Material registry (refractive indices) and voxel database (voxel sizes).
``demo``        Dry run only: all of the above one after another, as a check of the setup.

Where the data goes
-------------------
Every experiment is ONE file ``experiment.h5`` in its folder, plus JSON copies
(``experiment_dictionary.json``, ``structures.json``, ``print_progress.json``,
``experiment_summary.json``, ``experiment_spec.json``) and ``console.log``. Experiments on a
substrate go to ``<data root>/<substrate label>/<label>-A_<date>/``; the data root is
``dataRoot`` of the user in ``~/nanofactory.json`` (default ``~/Documents/Femtika_Experiment/<user>``,
never inside Seafile/OneDrive/Dropbox).
"""
import argparse
import dataclasses
import datetime
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from Experiments import default_experiment
from nanofactorysystem.devices.coordinate_system import Point2D
from nanofactorysystem.experiment_spec import ExperimentSpec, messagebox_confirm, run_experiment

REPOSITORY = Path(__file__).resolve().parents[1]

# =================================================================================================
# SETTINGS: change these values for your session
# =================================================================================================
TASK = "experiment"            # see the list of tasks in the docstring above
DRY_RUN = False                # True: simulated hardware, output in a temporary folder

USER = "Hannes"                # user key "user:<name>" in ~/nanofactory.json
OBJECTIVE = "Zeiss 63x"        # "Zeiss 20x" or "Zeiss 63x"

# Edges of the resin drop in absolute stage coordinates (µm): right, left, near, far.
# Measure them with the camera; four points define the ellipse of the printable area.
RESIN_EDGES = [[5720, 22330], [-3333, 22420], [1660, 17212], [1200, 27190]]

# Root folder for single experiments (task "experiment"/"slicer"/"spec_file"):
# the experiment is written to <OUTPUT_ROOT>/<spec.name>. None: the substrate folder below the
# data root (then SUBSTRATE_LABEL is used).
OUTPUT_ROOT: Optional[Path] = Path(r"C:\Users\Nanofactory\Desktop\Hannes\Experiment data")

# Substrate label, e.g. "HR-26-001". None: a new substrate with the next free label of the user.
SUBSTRATE_LABEL: Optional[str] = None

# Task "spec_file": the project file of an earlier experiment and the name of the new run.
SPEC_FILE: Optional[Path] = None          # e.g. Path(r"...\HR-26-001-A_20261119-1015\experiment_spec.json")
SPEC_RUN_NAME = "repeat_run"

# Task "restart": folder of the aborted experiment (the one containing experiment.h5).
RESTART_FOLDER: Optional[Path] = None

# Task "analyse": folder of the experiment to read (or its experiment.h5).
ANALYSE_FOLDER: Optional[Path] = None


def experiment_spec() -> ExperimentSpec:
    """ The experiment of task ``experiment``: the default experiment with every setting.

    Replace this by the spec of your own experiment script, e.g.
    ``from Experiments.old_experiment.Kailas import parametric_4q`` and
    ``parametric_4q.experiment_spec(objective=OBJECTIVE, absolute_center=Point2D(0, 21000))``.
    """

    return default_experiment.experiment_spec(objective=OBJECTIVE, center=Point2D(1310, 21000))


def substrate_spec():
    """ The substrate of tasks ``layout`` and ``substrate`` (substrate record version 2).

    Returns
    -------
    SubstrateSpec
    """

    from nanofactorysystem.substrate_plan import SubstrateSpec
    return SubstrateSpec(
        user=USER,
        objective=OBJECTIVE,              # all experiments of a substrate use the same objective
        resin_edges=RESIN_EDGES,
        label=SUBSTRATE_LABEL,            # None: next free label (initials of the user, year, number)
        material={"substrate": "boro-silicate glass", "thickness_um": 700.0, "resin": "SZ2080",
                  "resin_thickness_um": 75.0},  # or just the registry name of the resin: "SZ2080"
        substrate_material="",            # registry name of the substrate; default: material["substrate"]
        substrate_type="cover_slip",      # "cover_slip", "slide", "wafer", "other" or ""
        dimensions={"shape": "round", "diameter_mm": 30.0, "thickness_um": 170.0},
        resin_batch="",                   # batch of the resin bottle
        resin_thickness_um=None,          # default: material["resin_thickness_um"]
        application="drop",               # "drop" or "dip_in" (dip-in has no drop boundary)
        notes="Created by mains/main.py",
        data_root=None,                   # default: dataRoot of the user
        allow_synced_root=False,          # True accepts a data root in Seafile/OneDrive/Dropbox
    )


def substrate_experiments() -> list:
    """ The experiments of task ``substrate``, in print order; their areas must not overlap.

    Returns
    -------
    list of SubstrateExperiment
    """

    from nanofactorysystem.substrate_plan import SubstrateExperiment
    return [
        SubstrateExperiment(default_experiment.experiment_spec(OBJECTIVE, Point2D(1310, 21000), name="drawing")),
        # path=Path(...) stores an experiment outside the substrate folder
        SubstrateExperiment(default_experiment.slicer_spec(OBJECTIVE, Point2D(1310, 23000), name="slicer")),
    ]


# =================================================================================================
# Session: lab hardware or simulated hardware
# =================================================================================================
@dataclass
class Session:
    """ What the tasks need from the environment.

    Attributes
    ----------
    backend : DummyBackend or None
        None: the lab hardware.
    plane : ZFunction or None
        Known substrate plane (dry run); None: the plane is measured.
    output_root : Path or None
        Root folder of single experiments.
    data_root : Path or None
        Data root of the substrates; None: dataRoot of the user.
    confirm : callable or None
        ``confirm(question) -> bool`` before each step; None: no questions.
    show_plot : bool
        Show plot windows.
    material_registry : MaterialRegistry, Path or None
        None: the default database (``system.voxelDatabase``) if it exists.
    """

    backend: object = None
    plane: object = None
    output_root: Optional[Path] = OUTPUT_ROOT
    data_root: Optional[Path] = None
    confirm: Optional[Callable[[str], bool]] = None
    show_plot: bool = True
    material_registry: object = None
    last_experiment: Optional[Path] = None

    @property
    def dry(self) -> bool:
        """ True on simulated hardware. """

        return self.backend is not None

    def run(self, spec: ExperimentSpec, **arguments) -> Path:
        """ Run one experiment below ``output_root`` (or in the substrate folder).

        ``arguments`` override the keyword arguments of ``run_experiment`` taken from the session
        (e.g. another ``confirm``).
        """

        location = {"path": self.output_root} if self.output_root is not None else \
            {"substrate": SUBSTRATE_LABEL, "data_root": self.data_root}
        options = dict(backend=self.backend, plane=self.plane, confirm=self.confirm, show_plot=self.show_plot,
                       material_registry=self.material_registry, **location) | arguments
        folder = run_experiment(spec, user=USER, resin_edges=RESIN_EDGES, **options)
        self.last_experiment = Path(folder)
        return self.last_experiment


def dry_run_registry(folder: Path):
    """ A material registry and voxel database for dry runs, filled with the seed and example voxel data.

    The registry of the lab PC is never touched by a dry run.

    Returns
    -------
    MaterialRegistry
    """

    from nanofactorysystem.voxel import MaterialRegistry
    registry = MaterialRegistry(folder / "voxels.sqlite")
    if "SZ2080" not in registry.materials():
        registry.import_csv(REPOSITORY / "config" / "material_seed.csv")
        # Invented voxel sizes, only to show the interpolation (real ones come from line measurements)
        for power, velocity, width, height in [(0.5, 1000, 0.30, 0.9), (0.7, 1000, 0.40, 1.2),
                                               (0.5, 5000, 0.22, 0.7), (0.7, 5000, 0.31, 1.0)]:
            registry.database.add_measurement("SZ2080", OBJECTIVE, "IFOV_off", power, velocity, width_um=width,
                                              height_um=height, n_lines=5, method="SEM",
                                              notes="example data of the dry run")
    return registry


# =================================================================================================
# Tasks
# =================================================================================================
def task_experiment(session: Session) -> Path:
    """ One experiment from :func:`experiment_spec`. """

    folder = session.run(experiment_spec())
    print(f"Experiment written to {folder}")
    return folder


def task_slicer(session: Session) -> Path:
    """ The slicer example (height map -> layers -> IFOV programs). """

    folder = session.run(default_experiment.slicer_spec(OBJECTIVE, Point2D(1310, 23000)))
    print(f"Slicer experiment written to {folder}")
    return folder


def task_layout(session: Session):
    """ Check the substrate layout and plot it, without hardware.

    Raises
    ------
    LayoutError
        If experiments overlap or leave the resin drop; the message lists every problem.
    """

    from nanofactorysystem.substrate_plan import check_layout, plot_substrate
    substrate = substrate_spec()
    areas = check_layout(substrate, substrate_experiments())
    for area in areas:
        print(f"  {area.name:12s} x {area.lower[0]:8.0f} .. {area.upper[0]:8.0f} µm, "
              f"y {area.lower[1]:8.0f} .. {area.upper[1]:8.0f} µm")
    figure = plot_substrate(substrate, areas, show=session.show_plot)
    if session.dry:
        figure.savefig(session.output_root / "substrate_layout.png")
    print("Layout OK: no overlap, every experiment inside the resin drop.")
    return areas


def task_substrate(session: Session) -> list[Path]:
    """ Several experiments on one substrate; each is entered into the substrate index. """

    from nanofactorysystem.substrate_plan import run_substrate
    substrate = substrate_spec()
    if session.data_root is not None:
        substrate = dataclasses.replace(substrate, data_root=session.data_root)
    folders = run_substrate(substrate, substrate_experiments(), backend=session.backend, plane=session.plane,
                            confirm=session.confirm, confirm_between=session.confirm, show_plot=session.show_plot,
                            material_registry=session.material_registry)
    for folder in folders:
        print(f"Experiment written to {folder}")
    if folders:
        session.last_experiment = folders[-1]
    return folders


def task_spec_file(session: Session) -> Path:
    """ Load a stored project file and run the experiment again under a new name. """

    path = SPEC_FILE
    if path is None:
        if not session.dry:
            raise ValueError("Set SPEC_FILE to the experiment_spec.json of an earlier experiment.")
        # Dry run: store the default experiment as project file first, to show the round trip
        path = experiment_spec().save(session.output_root / "project" / "experiment_spec.json")
        print(f"Project file written to {path}")
    spec = ExperimentSpec.load(path)
    print(f"Loaded {spec.name!r} with {len(spec.structures)} structures from {path}")
    folder = session.run(dataclasses.replace(spec, name=SPEC_RUN_NAME))
    print(f"Experiment written to {folder}")
    return folder


def task_restart(session: Session) -> Path:
    """ Resume an aborted experiment; only the layers that were not printed are printed. """

    from nanofactorysystem.experiment import Experiment
    folder = RESTART_FOLDER
    if folder is None:
        if not session.dry:
            raise ValueError("Set RESTART_FOLDER to the folder of the aborted experiment.")
        # Dry run: build an experiment but stop before printing ("aborted"), then resume it
        spec = dataclasses.replace(experiment_spec(), name="restart_demo")
        folder = session.run(spec, confirm=lambda question: not question.startswith("FINAL"))
        print(f"Experiment built but not printed: {folder}")
    parameters = Experiment.parameters_from_dictionary(folder)
    with Experiment(**parameters, backend=session.backend) as experiment:
        experiment.restart_experiment()
    print(f"Experiment resumed and finished: {folder}")
    return Path(folder)


def task_overview(session: Session) -> list[dict]:
    """ List the substrates of the data root and the state of their experiments. """

    from nanofactorysystem.storage.substrate_store import (SubstrateStore, default_root, find_experiments,
                                                           substrate_overview)
    root = session.data_root or default_root(USER)
    store = SubstrateStore(root)
    print(f"Data root {root}: substrates {store.labels()}")
    for label in store.labels():
        record = store.get(label)
        print(f"Substrate {label} ({record.substrate_type or 'type ?'}, {len(record.resin_drops)} resin drop(s))")
        for item in substrate_overview(root, label):
            print(f"  {item.name:18s} {item.state:8s} {item.status:9s} {item.objective:10s} {item.folder or ''}")
    finished = find_experiments(root, status="finished")
    print(f"{len(finished)} finished experiment(s) in {root}")
    return finished


def task_analyse(session: Session) -> Optional[Path]:
    """ Read an experiment file, store an analysis result and unpack it (analysis/ tools). """

    folder = ANALYSE_FOLDER or session.last_experiment
    if folder is None:
        raise ValueError("Set ANALYSE_FOLDER to an experiment folder.")
    sys.path.insert(0, str(REPOSITORY / "analysis"))
    from experiment_analysis import ExperimentFile, unpack_experiment

    experiment = ExperimentFile(folder)
    print(experiment.summary_table())
    print(f"Structures: {[s.name for s in experiment.structures()]}")
    captures = experiment.captures(kind="camera")
    plane = experiment.plane()  # z(x, y) = a*x + b*y + c in µm
    print(f"{len(captures)} camera captures; substrate plane [a, b, c] = "
          f"{None if plane is None else [round(float(p), 6) for p in plane.parameters]}")
    if captures and not experiment.is_busy:  # a printing process holds the file: read only
        image = experiment.image(captures[-1].capture_id)
        experiment.save_result("mean_grey", float(image.mean()), capture=captures[-1].capture_id)
        print(f"Stored /analysis result 'mean_grey' = {image.mean():.1f} for capture {captures[-1].capture_id}")
    target = unpack_experiment(folder, Path(folder) / "unpacked", overwrite=True)
    print(f"Unpacked into {target}")
    return target


def task_materials(session: Session) -> None:
    """ Show the material registry and a voxel size lookup. """

    from nanofactorysystem.voxel import MaterialRegistry, MissingPropertyError
    registry = session.material_registry if session.dry else MaterialRegistry.open_existing()
    if registry is None:
        print("No material registry yet (system.voxelDatabase). Create it once with "
              "MaterialRegistry(path).import_csv('config/material_seed.csv').")
        return
    print(f"Materials: {registry.materials()}")
    resin = registry.material("SZ2080")
    for state in ("uncured", "cured_in_resin", "cured_developed"):
        try:
            index = resin.require_refractive_index(674.994, state)
            print(f"  n(SZ2080, 674.994 nm, {state}) = {index.value} ({index.source})")
        except MissingPropertyError as error:  # never a silent default for a physical value
            print(f"  {error}")
    voxel = registry.database.voxel_size("SZ2080", OBJECTIVE, "IFOV_off", power_mW=0.6, velocity_um_s=2000)
    print(f"Voxel size SZ2080 / {OBJECTIVE} / IFOV_off at 0.6 mW, 2000 µm/s: {voxel}")


TASKS = {"experiment": task_experiment, "slicer": task_slicer, "layout": task_layout,
         "substrate": task_substrate, "spec_file": task_spec_file, "restart": task_restart,
         "overview": task_overview, "analyse": task_analyse, "materials": task_materials}
DEMO_ORDER = ["layout", "materials", "experiment", "analyse", "spec_file", "restart", "slicer", "substrate",
              "overview"]


def main(task: str = TASK, *, dry: bool = DRY_RUN, workdir: Optional[Path] = None):
    """ Run a task on the lab hardware or as dry run.

    Parameters
    ----------
    task : str
        A key of :data:`TASKS`, or ``"demo"`` (dry run only).
    dry : bool
        Simulated hardware; experiments go to ``workdir``.
    workdir : Path, optional
        Folder of the dry run; default: a new temporary folder.

    Returns
    -------
    object
        The result of the task (for ``demo`` a dict of all results).
    """

    if task != "demo" and task not in TASKS:
        raise ValueError(f"Unknown task {task!r}; choose one of {sorted(TASKS) + ['demo']}")
    if not dry:
        if task == "demo":
            raise ValueError("Task 'demo' runs every task and is meant for a dry run (--dry-run).")
        return TASKS[task](Session(confirm=messagebox_confirm))

    import matplotlib
    matplotlib.use("Agg")  # no plot windows in a dry run
    from nanofactorysystem.backends.dummy.dry_run import dry_run
    with dry_run(USER, workdir=workdir) as simulated:
        session = Session(backend=simulated.backend, plane=simulated.plane, output_root=simulated.workdir / "out",
                          data_root=simulated.workdir / "data_root", show_plot=False,
                          material_registry=dry_run_registry(simulated.workdir))
        session.output_root.mkdir(parents=True, exist_ok=True)
        print(f"DRY RUN on simulated hardware, output in {simulated.workdir}")
        try:
            if task != "demo":
                return TASKS[task](session)
            results = {}
            for name in DEMO_ORDER:
                print(f"\n===== Task {name} =====")
                results[name] = TASKS[name](session)
            return results
        finally:
            session.material_registry.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Laser Nanofactory main entry point")
    parser.add_argument("--task", default=TASK, choices=sorted(TASKS) + ["demo"])
    parser.add_argument("--dry-run", action="store_true", default=DRY_RUN, help="simulated hardware")
    parser.add_argument("--workdir", type=Path, default=None, help="output folder of a dry run")
    options = parser.parse_args()
    started = datetime.datetime.now()
    main(options.task, dry=options.dry_run, workdir=options.workdir)
    print(f"Total time: {datetime.datetime.now() - started}")
