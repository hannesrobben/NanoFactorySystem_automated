##########################################################################
# Copyright (c) 2026 Hannes Robben                                       #
# <hannes.robben@phoenixd.uni-hannover.de>                               #
# This program is free software under the terms of the MIT license.      #
##########################################################################
"""Template of a substrate main file (T52): one substrate and the experiments printed on it.

Copy this file per substrate and edit SUBSTRATE and experiments(). Before anything is printed,
the experiment areas (grid, margin, corner markers and QR code) are checked against each other,
against experiments already on the substrate, and against the resin drop; the planned layout is
shown. The experiments then run one after another and are entered into the substrate index
(``<data root>/<label>/substrate.json``); experiments without a path are stored in the substrate
folder below the default data location.

Run it with ``mains/`` as the working directory (``cd mains && python substrate_main.py``).
A dry run on simulated hardware: ``main(backend="dummy", plane=..., data_root=...)``.
"""
import dataclasses
from pathlib import Path
from typing import Optional

from Experiments.Kailas import Quadrants_line_power_gap, parametric_4q
from nanofactorysystem.devices.coordinate_system import Point2D
from nanofactorysystem.experiment_spec import messagebox_confirm
from nanofactorysystem.substrate_plan import SubstrateExperiment, SubstrateSpec, run_substrate

OBJECTIVE = "Zeiss 63x"
SUBSTRATE = SubstrateSpec(
    user="Hannes",
    objective=OBJECTIVE,
    # Edges of the resin drop in µm: right, left, near, far
    resin_edges=[[5720, 22330], [-3333, 22420], [1660, 17212], [1200, 27190]],
    # Hand-written label on the substrate; None creates the next free label of the user
    label=None,
    material={"substrate": "boro-silicate glass", "thickness_um": 700.0, "resin": "SZ2080",
              "resin_thickness_um": 75.0},
    notes="",
)


def experiments() -> list[SubstrateExperiment]:
    """ The experiments on this substrate in print order. """

    power_quadrants = parametric_4q.experiment_spec(objective=OBJECTIVE, absolute_center=Point2D(0, 21000))
    line_gaps = Quadrants_line_power_gap.experiment_spec(objective=OBJECTIVE, absolute_center=Point2D(2000, 21000))
    return [
        SubstrateExperiment(dataclasses.replace(power_quadrants, name="power_quadrants")),
        # path=... stores an experiment outside the substrate folder
        SubstrateExperiment(dataclasses.replace(line_gaps, name="line_power_gap")),
    ]


def main(*, backend=None, plane=None, data_root: Optional[Path] = None) -> list[Path]:
    """ Check the layout and print the experiments of this substrate.

    On the lab PC every step and every further experiment is confirmed in a message box.

    Parameters
    ----------
    backend : {"real", "dummy"}, optional
        ``"dummy"`` for a dry run on simulated hardware (no questions, no plots).
    plane : ZFunction, optional
        Known substrate plane for dry runs.
    data_root : Path, optional
        Data root instead of the user's default location.

    Returns
    -------
    list of Path
        The experiment folders.
    """

    substrate = dataclasses.replace(SUBSTRATE, data_root=data_root) if data_root is not None else SUBSTRATE
    interactive = backend is None
    return run_substrate(substrate, experiments(), backend=backend, plane=plane,
                         confirm=messagebox_confirm if interactive else None,
                         confirm_between=messagebox_confirm if interactive else None, show_plot=interactive)


if __name__ == "__main__":
    main()
