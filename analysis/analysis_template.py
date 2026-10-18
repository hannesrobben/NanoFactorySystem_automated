##########################################################################
# Copyright (c) 2026 Hannes Robben                                       #
# <hannes.robben@phoenixd.uni-hannover.de>                               #
# This program is free software under the terms of the MIT license.      #
##########################################################################
"""Template for an analysis of one experiment: read data, compute, store the result in the file.

Copy this file per analysis. It works while the experiment is printed as
well (reading); storing results waits until the printing session has ended
(``WAIT_S``) or raises ``ExperimentBusyError``.
"""
import sys
from pathlib import Path

import numpy as np

# ----------------------------------------------------------------------------- settings
EXPERIMENT = r"C:\Users\<user>\Documents\Femtika_Experiment\<user>\<substrate>\<experiment folder>"
WAIT_S = 0.0        # how long storing a result waits for a running print session
# --------------------------------------------------------------------------------------

sys.path.insert(0, str(Path(__file__).resolve().parent))

from experiment_analysis import ExperimentFile  # noqa: E402


def main(experiment=EXPERIMENT, wait_s=WAIT_S):
    exp = ExperimentFile(experiment)
    print(exp.info())
    print(exp.summary_table())

    # Example: mean grey value of every camera image after printing, per capture and per structure
    for structure in exp.structures():
        values = []
        for capture in exp.captures(structure=structure.name, kind="camera", phase="after"):
            mean = float(np.mean(exp.image(capture.capture_id)))
            values.append(mean)
            exp.save_result("mean_grey", mean, capture=capture.capture_id, wait_s=wait_s)
        if values:
            exp.save_result("mean_grey", np.asarray(values), structure=structure.name, wait_s=wait_s,
                            attrs={"unit": "grey value", "method": "np.mean of each camera image (phase after)"})

    print(exp.results())
    return exp


if __name__ == "__main__":
    main()
