# Analysis tools for experiment files

Every experiment is stored in one HDF5 file, `experiment.h5` (design: `docs/design/EXPERIMENT_STORAGE.md`).
This folder holds tools to work with these files outside the printing process. It is not part of the
installed package; it needs `nanofactorysystem` (`pip install .` in the repository root) and Pillow
(installed with matplotlib).

| File | Purpose |
|---|---|
| `unpack_experiment.py` | Unpack an experiment file into common formats (set the variables at the top, or use the command line) |
| `analysis_template.py` | Template for an analysis: read data, compute, store the result in the file |
| `experiment_analysis/` | The Python package behind both (`unpack_experiment`, `ExperimentFile`) |

## Unpacking

```bash
cd analysis
python unpack_experiment.py "D:/.../HR-26-001-A_20261018-1015/experiment.h5" "C:/Users/me/Desktop/HR-26-001-A"
python unpack_experiment.py <experiment.h5 or folder> <output folder> --zip --zdc --overwrite --csv en
python -m experiment_analysis info <experiment.h5>     # identification and summary table
python -m experiment_analysis tree <experiment.h5>     # groups and datasets of the file
```

The output folder contains only files that Windows opens without extra software:

| In the file | In the output folder |
|---|---|
| every group | a folder; its attributes in `attributes.json` |
| texts (layer programs, logs) | `.txt` |
| camera images, holograms (8/16 bit) | `.png` (lossless); a hologram series is a folder with one PNG per image |
| number arrays and tables | `.csv`; large 2-D arrays (DHM products) also `_preview.png` |
| stored files (layout plot, plane-fit containers) | `.png`, `.zdc` as stored |
| captures (with `--zdc`) | `capture.zdc` (SciDataContainer, as written before the experiment file) |

At the top: `README.txt` (what is where), `summary.txt`, `experiment_info.json`, the JSON copies
(`experiment_dictionary.json`, `structures.json`, `print_progress.json`, `experiment_summary.json`) and
`tables/*.csv` (summary, structures, captures with stage positions, layer progress, sessions).

- CSV style: `de` (default) uses `;` and a decimal comma, so German Excel opens the files by double click;
  `--csv en` writes `,` and a decimal point (Python, Origin, English Excel).
- `--zip` also writes `<output folder>.zip`.
- An existing, non-empty output folder is refused unless `--overwrite` is given; the output folder must not
  contain the experiment file.
- While the experiment is being printed (lock file `experiment.lock` of a running process), a copy of the
  file is unpacked, so the printing process is never disturbed.

## Live access and storing results

```python
import sys; sys.path.insert(0, r"<repository>/analysis")
from experiment_analysis import ExperimentFile

exp = ExperimentFile(r"D:/.../HR-26-001-A_20261018-1015")   # folder or experiment.h5
exp.info()                       # labels, UUIDs, status, busy
print(exp.summary_table())
for c in exp.captures(structure="grating_0", kind="camera", phase="after"):
    image = exp.image(c.capture_id)                          # numpy array
    exp.save_result("mean_grey", float(image.mean()), capture=c.capture_id)
exp.save_result("profile", {"x_um": x, "height_nm": h}, structure="grating_0", attrs={"rms_nm": 3.2})
data, attrs = exp.load_result("profile", structure="grating_0")
exp.results()                    # all stored results
exp.wait_for_change(timeout_s=60) # wait for the next write of the printing process
```

Reading: `record()`, `structures()`, `captures(...)`, `capture()`/`image()`, `product()` (DHM products),
`program()`, `plane()` (z function of the substrate), `overview()`, `logs()`, `summary()`; generic
`keys()`, `read(path)`, `attributes(path)`, `tree()`.

Rules (they keep the printing process safe):
- Every call opens and closes the file. Reads use no HDF5 file lock and are repeated if they hit a write
  in progress, so reading works at any time, also during printing.
- Results go to `/analysis/experiment/<name>`, `/analysis/structures/<structure>/<name>` or
  `/analysis/captures/<capture id>/<name>`. Groups written by the printing process are never changed;
  the only exception is `add_dhm_product()`, the interface for DHM products of the design (§5.6).
- Writing takes the lock file for the duration of the write. While an experiment process holds it
  (printing or restart), `save_result()` raises `ExperimentBusyError`, or waits up to `wait_s` seconds.
  Results can be stored as soon as the printing session has ended.
