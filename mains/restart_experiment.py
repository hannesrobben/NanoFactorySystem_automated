"""Restart an aborted experiment on the lab PC.

Set ``exp_path`` to the experiment folder (the one containing experiment_dictionary.json,
structures.json and print_progress.json) and run this script. The experiment parameters are
read from experiment_dictionary.json; the remaining layers are printed.
"""
from nanofactorysystem.experiment import Experiment


def restart(path, backend=None):
    """ Resume printing the experiment stored in ``path``. """
    with Experiment(**Experiment.parameters_from_dictionary(path), backend=backend) as experiment:
        experiment.restart_experiment()


# todo
#       create dictionary for restarting experiment  - alles was am anfang dem Experiment übergeben wird
#       übergabe von restart sollte eigentlich nur die ordner struktur sein
#       zusätzlich muss außerdem noch die substrat informationen im hauptordner gegeben werden
#       !!! Experiment bekommt immer eine neue UUID - das sollte nicht sein!

exp_path = r"C:\Users\Nanofactory\Desktop\Hannes\Experiment data\test2_program\TEST_aerotech_1"

if __name__ == "__main__":
    restart(exp_path)

# todo nochmal kontrollieren, wenn er bereits eine oder zwis schichten gedruckt hat - sieht so aus, dass es nicht an der richtigen stelle wieder startet!
# wahrscheinlich liegt es daran, wenn das abbricht nachdem man bereits einmal wieder aufgestartete hat, dann wird die anzahl der layer geändert
