import os
import datetime

from nanofactorysystem.devices.coordinate_system import Point2D
from Experiments.historical.Model_3D_experiment import (
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


# General ToDos

if __name__ == "__main__":
    main()
