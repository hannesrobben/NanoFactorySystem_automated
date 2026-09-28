import os
import datetime

from nanofactorysystem.devices.coordinate_system import Point2D
from Experiments.Model_3D_experiment import (
    print_2pp as print_program,
)

def main():
    edges = [
        [1500,	17400],
        [1400,	27000],
        [-3600,	22400],
        [5500,	21700]
    ]
    # old experiment 100-20200 (double corner) - other corners in negative x and negative y direction

    # center = Point2D(X=-1000,  #
    #                  Y=22000)  #
    center = Point2D(X=500, Y=22500)

    # ToDo: Make sure center is within the edges
    # assert center.Y in [ymin, ymax]
    # assert center.X in [xmin, xmax]

    root_path = os.path.join(os.getcwd(), ".output/")
    model_path = r"C:\Users\Nanofactory\Desktop\Hannes\mdl_lens.stl"
    t1 = datetime.datetime.now()

    print_program(
        absolute_center=center,
        resin_dimension=edges,
        ask_continue_box=True,
        path=r"C:\Users\Nanofactory\Desktop\Hannes\Experiment data\Kailas_Exp",  # please change here
        objective="Zeiss 63x",
        user="Hannes",
        substrate={
            "Name": "3D Model Test",
            "Number of drops": 1,
            "Used drop": "Middle",
            "Beschreibung": "Test for the self developed slicer",
        },
        dhm_usage=False,
        setup="IFOV_on",
        model_path=model_path,
    )
    t2 = datetime.datetime.now()
    time = t2 - t1
    print(f"Total time: {time}")
    # ToDo: Get a timelogger or a overview on how long it will take


# General ToDos
# ToDo 1: identification for substrate to track the printing of different experiments on one substrate
# ToDo 2: Build a custom experiment database based on different identification factors (e.g. substrate, date, objective etc)
# ToDo 3: Plane Fitting: change to a "just border" mode and the currently used mode (Between each FOV of a print)

if __name__ == "__main__":
    main()
