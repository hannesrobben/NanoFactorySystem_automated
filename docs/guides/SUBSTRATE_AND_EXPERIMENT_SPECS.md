# Substrates, experiments and structures as specs

This guide explains how a print is described today: a substrate main script holds a list of experiments,
each experiment is an `ExperimentSpec`, and each grid cell of an experiment is a `StructureSpec`. It ends
with a complete STL experiment and with chaining several experiments on one substrate.

Source: English version of `Information_Mehrere_Experimente.txt` (T98), checked against the code of
2026-11-17. Relevant modules: `nanofactorysystem/experiment_spec.py`, `nanofactorysystem/substrate_plan.py`,
`nanofactorysystem/storage/substrate_store.py`, `mains/substrate_main.py`.

## 1. The levels

```
substrate main script         ← one substrate: user, objective, drop, list of experiments
 └─ SubstrateExperiment       ← one experiment on the substrate (+ optional own folder)
     └─ ExperimentSpec        ← everything that makes up ONE experiment (grid, plane fit, setup, …)
         └─ StructureSpec     ← ONE structure = one grid cell (what is printed, power, axes)
             └─ DrawableObject / STL / height map   ← the actual geometry
```

Earlier, all of this lived as variables inside a `print_file()` function: the `if objective == ...`
blocks, `Experiment(...)` with about 30 arguments, and `add_structure(...)` by hand. Now an experiment is
described as a data object. `run_experiment()` always processes it in the same order: plot, plane fit,
OPL scan (only with the DHM), structures, build, print.

## 2. `ExperimentSpec` in detail

Defined in `nanofactorysystem/experiment_spec.py`. Fields left at `None` get the value of the objective
from `OBJECTIVE_DEFAULTS` in the same module. This table replaces the old `if objective == "Zeiss 63x":`
blocks.

| Group | Fields | Meaning |
|---|---|---|
| Required | `name`, `objective`, `center`, `grid` | Folder name, objective, centre of the grid (µm), (rows, columns) |
| Structures | `structures`, `program_source` | List of `StructureSpec` in print order; `DRAWING` (Python structure classes) or `SLICER` (STL / height map) |
| Setup | `setup` | `"IFOV_off"` (default) / `"IFOV_on"`. `SLICER` needs `"IFOV_on"` |
| Objective values (`None` → default) | `fov_um`, `drop_direction`, `z_max_um`, `margin_um`, `padding_um`, `corner` | See the table below |
| Grid | `structure_size_um` (`None` → FOV), `skip_corner`, `n_mid_points` | Size of one grid cell; leave out corners + QR code |
| Plane fit | `plane_fit_mode` (`GRID` / `CORNERS` / `BORDER`), `tilt_warning_um` | Measurement points; warning when a structure sits on a tilt |
| Measurements | `dhm_usage`, `opl_start_um`, `camera_capture`, `overview_capture`, `overview_single_images` | DHM / OPL, camera images after the print, mosaic before and after the print |
| Motion / power | `default_power_mw`, `low_speed_um_s`, `high_speed_um_s` | Default power, travel speeds |
| Voxel | `voxel_material`, `voxel_database` | With a material, the slicer compensates with measured voxel sizes |
| Run time | `sys_args`, `layer_overhead_s` | Sections for focus, layer, sample and attenuator (like the old `sys_args` dict); overhead per layer for the time estimate |
| Metadata | `materials`, `description`, `tags` | Free metadata stored with the experiment |

Objective defaults (`OBJECTIVE_DEFAULTS`):

| Objective | `fov_um` | `drop_direction` | `z_max_um` | `margin_um` | `padding_um` | Corners (width × length, hatch) |
|---|---|---|---|---|---|---|
| Zeiss 20x | 500 | UP | 24550 | 200 | 100 | 50 × 300 µm, 0.5 µm |
| Zeiss 63x | 150 | DOWN | 25480 | 50 | 100 | 30 × 120 µm, 0.3 µm |

`spec.resolved()` returns a copy with all defaults filled in, so you see what is actually used. It also
checks that the structures fit into the grid and that `SLICER` is combined with `IFOV_on`.

## 3. Where the structures are defined

In the `structures` list of the spec. Each entry is a `StructureSpec` and occupies one grid cell:

| Field | Meaning |
|---|---|
| `name` | Name of the structure (folder, summary) |
| `structure` | A finished `DrawableObject`, e.g. `Rectangle3D(...)` or `Stair(...)` (`DRAWING`) |
| `factory` | `factory(experiment) -> DrawableObject`, for structures that need values of the running experiment, e.g. the calibration range of the attenuator. `power_z_pitch_lines.cell()` works this way |
| `height_data` + `slicer` | STL path / height map + keyword arguments for `Model3D_Slicer` (`SLICER`) |
| `power_mw`, `layer_power` | Power of the structure, or power per layer |
| `axes` | `"ABZ"` (galvo) / `"XYZ"` (stages) |
| `repeat` | How often the structure is repeated in the following cells |
| `structure_type` | Default `NORMAL` (`DRAWING`) or `IFOV` (`SLICER`); `StructureSpec.empty()` leaves a cell empty |

Where the list is built:
- in an experiment script under `mains/Experiments/...`, in its function
  `experiment_spec(objective, absolute_center, ...)`. The parameters are usually constants at the top of
  the file, e.g. `POWERS` and `PITCHES` in `power_z_pitch_lines.py`;
- or directly in the substrate main script, if the experiment is small and only needed there.

## 4. An STL experiment as a spec

The former `mains/Experiments/historical/Model_3D_experiment.py` passed `Model3D_Slicer(...)` directly to
`add_structure`. In the new form the same experiment looks like this (values from the old 63x branch;
replace the STL path with your own file):

```python
from pathlib import Path
from nanofactorysystem.devices.coordinate_system import Point2D, Point3D
from nanofactorysystem.experiment import ProgramSource
from nanofactorysystem.experiment_spec import ExperimentSpec, StructureSpec
from nanofactorysystem.plane_fitting import PlaneFitMode

STL = Path(r"<path to>\mdl_lens.stl")

def stl_lens_spec(objective="Zeiss 63x", absolute_center=Point2D(500, 22500),
                  slice_um=0.2, hatch_um=0.2, power_mw=0.5) -> ExperimentSpec:
    return ExperimentSpec(
        name="stl_lens",
        objective=objective,
        center=absolute_center,
        grid=(1, 1),
        structure_size_um=250,                # as before (a structure larger than the FOV is stitched)
        program_source=ProgramSource.SLICER,
        setup="IFOV_on",
        plane_fit_mode=PlaneFitMode.CORNERS,  # corresponds to the old plane_fit_mode=1
        camera_capture=True,
        structures=[StructureSpec(
            f"model3d_s{slice_um}_h{hatch_um}_p{power_mw}",
            height_data=STL,
            power_mw=power_mw,
            axes="XYZ",
            slicer={                          # everything that used to go into Model3D_Slicer(...)
                "center": Point3D(0, 0, -0.5),
                "unit": "um",
                "velocity": 10_000,
                "hatch_size": hatch_um,
                "slice_size": slice_um,
                "hatch_strategy": "alternating",
                "optimize": True,
            },
        )],
    )
```

The spec sets `center`, `objective` and `source` itself. What you put into `slicer={...}` takes
precedence. A parameter sweep is simple: several `StructureSpec` with different `slice_um` / `power_mw`,
plus a larger `grid`.

Mixing also works. In a `DRAWING` experiment you can add an STL as a normal structure:
`StructureSpec("lens", structure=Model3D_Slicer(center=Point3D(0, 0, -0.5), source=STL, velocity=10_000, ...), structure_type=StructureType.IFOV, axes="XYZ")`.
Then you must set `setup="IFOV_on"`. Voxel compensation via `voxel_material` does not apply automatically
in this case.

## 5. Chaining several experiments on one substrate

Copy `mains/substrate_main.py` once per substrate, e.g. as `mains/substrate_hr26_001.py`, and edit two
places, `SUBSTRATE` and `experiments()`:

```python
from Experiments.Kailas import power_z_pitch_lines, parametric_4q
from stl_lens import stl_lens_spec     # or wherever you keep the function above

OBJECTIVE = "Zeiss 63x"
SUBSTRATE = SubstrateSpec(
    user="Hannes",
    objective=OBJECTIVE,                 # applies to ALL experiments on the substrate
    resin_edges=[[1500, 17400], [1400, 27000], [-3600, 22400], [5500, 21700]],
    label=None,                          # None = next free label, e.g. HR-26-001
    material={"substrate": "boro-silicate glass", "resin": "SZ2080"},
    notes="Lines + STL lens",
)

def experiments():
    lines = power_z_pitch_lines.experiment_spec(objective=OBJECTIVE, absolute_center=Point2D(0, 21000),
                                                dhm_usage=False)
    lens = stl_lens_spec(objective=OBJECTIVE, absolute_center=Point2D(2000, 23000))
    return [
        SubstrateExperiment(lines),
        SubstrateExperiment(lens),
        # SubstrateExperiment(spec, path=r"C:\...") → own folder instead of the substrate folder
    ]
```

`SubstrateSpec` has further optional fields for the substrate record (`data_root`, `allow_synced_root`,
`substrate_material`, `substrate_type`, `dimensions`, `resin_batch`, `resin_thickness_um`,
`application`); see `nanofactorysystem/substrate_plan.py`.

What happens at the start (`cd mains`, then `python substrate_hr26_001.py`):
- Before any print, `run_substrate()` checks the whole layout: no overlap between the experiments
  (including corners and QR code), no overlap with experiments already in the index of this substrate,
  and everything inside the drop ellipse. If something does not fit, it stops with `LayoutError` before
  anything moves. Then it shows the layout plot.
- The experiments run one after the other. Each does its own plane fit with its own corners and its own
  QR code. On the lab PC a message box asks before each further experiment.
- The data go to `<dataRoot>\<Label>\<Label>-A_<date>\`, `...-B_...` and so on; `substrate.json` keeps
  the index. `dataRoot` is `~/Documents/Femtika_Experiment/<user>` or the value from `nanofactory.json`.
  It must not be inside a synchronised folder (Seafile / OneDrive / Dropbox) unless `allow_synced_root`
  is set.
- To print further experiments on the same substrate later, set `label="HR-26-001"`. The areas already
  printed are then included in the overlap check.

Dry run first (no hardware; it mainly checks the layout):

```bash
cd mains
python -c "import substrate_hr26_001 as s; from nanofactorysystem.devices.coordinate_system import StaticOffset; s.main(backend='dummy', plane=StaticOffset(25000), data_root=r'C:\temp\dry')"
```

`import` does not work with hyphens in the file name, so name the file e.g. `substrate_hr26_001.py`
rather than `substrate_HR-26-001.py`.
