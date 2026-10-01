# Historical experiment scripts

These scripts ran earlier experiments and are kept as a record of their parameters. They are not ported to
`ExperimentSpec` (T51), are not tested, and may no longer run against the current code (e.g. they still set
`sample.orientation`, which was removed in T43, or use the older `print_file`/`binary_testprint` flow directly).

The scripts in use are in the parent folder and describe their experiment with `experiment_spec()`
(`nanofactorysystem/experiment_spec.py`); `experiment_template.py` is the template for new experiments.

To reuse one of these experiments, port it the same way: move it back to `mains/Experiments/`, build an
`ExperimentSpec` in `experiment_spec()`, keep the entry function's signature, and add it to
`PORTED` in `test/integration/test_ported_scripts.py`.

| Folder / file | Content |
|---|---|
| `Grating_20x/` | Gratings, stitching and plane fitting with the 20x objective |
| `Grating_63/` | Binary gratings, angle, stitching and parameter tests with the 63x objective |
| `IFOV_63/` | First IFOV test (63x) |
| `Kailas/` | IFOV gratings and lenses, plane fitting, padding, voxel dose |
| `dhm/` | Prints for the DHM paper (SEM, alignment, refractive index, axial voxel size) |
| `other/` | Older parameter and DHM test prints, QR code investigation |
| `stacked/` | Stacked lenses |
| `Model_3D_experiment.py` | Printing a 3D model through the slicer (used by `mains/main_3D_model.py`) |
