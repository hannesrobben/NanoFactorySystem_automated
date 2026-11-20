# NanoFactorySystem

Python 3 package to use the Laser Nanofactory system from Femtika as 3D printer.

## Installation

To build and install the package, run the command

```
python -m pip install .
```

To clean all intermediate files and directories, run
```
python clean.py
```


## Usage examples

Start with `mains/main.py`, the entry point for every task (single experiment, slicer, substrate
with several experiments, layout check, rerun of a stored spec, restart, overview, analysis,
materials). Its experiment is `mains/Experiments/default_experiment.py`, which shows every setting
with an explanation. Without the lab hardware, run everything on simulated hardware:

```
cd mains
python main.py --task demo --dry-run
```

How a print is described with substrate, experiment and structure specs, including a complete STL
experiment and chaining several experiments on one substrate:
[docs/guides/SUBSTRATE_AND_EXPERIMENT_SPECS.md](docs/guides/SUBSTRATE_AND_EXPERIMENT_SPECS.md).
