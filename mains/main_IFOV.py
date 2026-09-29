import os
import datetime
from nanofactorysystem.devices.coordinate_system import Point2D
# from Experiments.parameter_study.parameter_testprint_power_speed import testprint as print_program
# from Experiments.dhm.dhm_img_4_SEM import dhm_paper as print_program
# from Experiments.dhm.dhm_paper import dhm_paper as print_program
# from Experiments.dhm.dhm_paper_aligning_DHM_camera import dhm_paper as print_program
# from Experiments.dhm.dhm_paper_power_refractiveIndex import dhm_paper as print_program
# from Experiments.dhm.dhm_paper_voxel_axial import dhm_paper as print_program
# from Experiments.stacked.stacked_lenses_test import stacked_lens_testprint as print_program
# from Experiments.Grating_63.grating_test_claude import gratings_testprint as print_program
# from Experiments.Grating_63.grid_point_test import binary_testprint as print_program
# from Experiments.Grating_63.FOV_Stitch_test import binary_testprint as print_program
# from Experiments.Grating_20x.plane_fitting_20x import binary_testprint as print_program
# from Experiments.Grating_20x.zumLaufBringen_20x_grating import binary_testprint as print_program
from Experiments.Big_substrate_20x.grating_ifov_test import binary_testprint as print_program
# from Experiments.Grating_20x.grating_big_stitching import binary_testprint as print_program
# from Experiments.Grating_63.test_stitching import binary_testprint as print_program
# from Experiments.Grating_63.test_program_cycle import binary_testprint as print_program
# from Experiments.parameter_study.line_test.Power_speed_line_test import dhm_testprint as print_program

# from Experiments.parameter_study.parameter_testprint_power_speed_test4orientation import testprint as print_program
# from Experiments.testprint_dhm import dhm_testprint as print_program

"""
Hannes 0912e
"""


def main():
    edges = [
        [-500, -18750],  # right edge
        [-750, -9500],  # left edge
        [-5250, -14000],  # near edge
        [3750, -14000]  # far edge

    ]
    # old experiment 100-20200 (double corner) - other corners in negative x and negative y direction

    # center = Point2D(X=-1000,  #
    #                  Y=22000)  #
    center = Point2D(X=-1000,  #
                     Y=-16000)  #


    root_path = os.path.join(os.getcwd(), ".output/")
    t1 = datetime.datetime.now()

    print_program(absolute_center=center,
                  resin_dimension=edges,
                  ask_continue_box=True,
                  # path=r"C:\Users\Nanofactory\Desktop\Hannes\Experiment data\stacked_lens",  # please change here
                  # path=r"C:\Users\Nanofactory\Desktop\Hannes\Experiment data\stitching+grating",  # please change here
                  path=r"C:\Users\Nanofactory\Desktop\Hannes\Experiment data\IFOV",  # please change here
                  # path=r"C:\Users\Nanofactory\Desktop\Hannes\Experiment data\FINAL_dhm",  # please change here
                  # objective="Zeiss 63x",
                  objective="Zeiss 20x",
                  user="Hannes",
                  substrate={"Name": "IFOV Test",
                             "Number of drops": 3,
                             "Used drop": "Rechter tropfen",
                             "Beschreibung": "Hoffentlich keine bugs mehr?"},
                  dhm_usage=False,
                  setup="IFOV_on")
    t2 = datetime.datetime.now()
    time = t2 - t1
    print(f"Total time: {time}")


# General ToDos

if __name__ == "__main__":
    main()
