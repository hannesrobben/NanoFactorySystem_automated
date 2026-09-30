"""Restart an aborted experiment on the lab PC.

Set ``exp_path`` to the experiment folder (the one containing experiment.h5, or
experiment_dictionary.json and structures.json in folders written before the experiment file
existed) and run this script. Parameters and progress are read from the experiment file; an
old folder is imported into a new experiment file first. The experiment keeps its UUID, and
every layer that was not printed in an earlier run is printed, also after several aborts.
"""
from nanofactorysystem.experiment import Experiment


def restart(path, backend=None):
    """ Resume printing the experiment stored in ``path``. """
    with Experiment(**Experiment.parameters_from_dictionary(path), backend=backend) as experiment:
        experiment.restart_experiment()


exp_path = r"C:\Users\Nanofactory\Desktop\Hannes\Experiment data\test2_program\TEST_aerotech_1"

if __name__ == "__main__":
    restart(exp_path)

