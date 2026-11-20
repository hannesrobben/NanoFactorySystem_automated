# Older experiment scripts

Moved here in T113 so that `mains/Experiments/` holds only the documented default experiment
(`default_experiment.py`) and the experiments built on it (e.g. `chain_rectangle_doe_lens.py`).

| Folder / file | Content | Tested |
|---|---|---|
| `Big_substrate_20x/`, `DHM_tomography/`, `Kailas/`, `parameter_study/`, `refractive_index/` | Experiment scripts ported to `ExperimentSpec` (T51) | `test/integration/test_ported_scripts.py` |
| `focal_points/z_line_focal_points.py` | z-lines with camera images for focus training data (T36) | `test/integration/test_focal_points.py` |
| `experiment_template.py` | Short template of T51 (superseded by `../default_experiment.py`) | `test/integration/test_dry_run_spec.py`, `test_ported_scripts.py` |
| `default_exp_file.py` | Older template with the former `binary_testprint` flow | `test/integration/test_dry_run_default_experiment.py` |
| `historical/` | Scripts of earlier experiments, not ported, not tested (see its README) | – |

Import them as `from Experiments.old_experiment.<folder>.<script> import ...` (working directory `mains/`).

Project files `experiment_spec.json` written before T113 name the module of a structure factory as
`Experiments.<folder>.<script>` (e.g. `Experiments.Kailas.parametric_4q`). Loading such a file falls back to the
stored source file path; if that path does not exist on the PC either, import the script from its new place
before `ExperimentSpec.load(...)`, which registers its factories.
