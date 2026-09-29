import os
import datetime
from nanofactorysystem.devices.coordinate_system import Point2D
# from Experiments.parameter_study.line_test.Power_speed_line_test import print_file as print_program
# from Experiments.Kailas.padding_test_0_5mm import print_file as print_program
# from Experiments.Kailas.ifovGrating_diffPower_500um import print_file as print_program
# from Experiments.Kailas.ifovGrating_diffPower_75um import print_file as print_program
# from Experiments.Kailas.ifovGrating_diffPower_500um import print_file as print_program
# from Experiments.Kailas.parametric_4q import print_file as print_program
#from Experiments.Kailas.Rectangle_plane_fitting import print_file as print_program
from Experiments.Kailas.power_z_pitch_lines import testprint as print_program


# from Experiments.IFOV_63.ifov_test import print_file as print_program


def main():
    edges = [
        [5720, 22330],
        [-3333, 22420],
        [1660, 17212],
        [1200, 27190]
        # [900, 17500],  # right edge
        # [1000, 26700],  # left edge
        # [-3700, 22000],  # near edge
        # [5500, 22200]  # far edge
    ]
    # old experiment 100-20200 (double corner) - other corners in negative x and negative y direction

    # center = Point2D(X=-1000,  #
    #                  Y=22000)  #
    center = Point2D(X=1310,  #
                     Y=19500)  #


    root_path = os.path.join(os.getcwd(), ".output/")
    t1 = datetime.datetime.now()

    print_program(absolute_center=center,
                  resin_dimension=edges,
                  ask_continue_box=False,
                  path=r"C:\Users\Nanofactory\Desktop\Hannes\Experiment data\Kailas_Exp\Large_z_offset_and_Pitch_vs power_3",  # please change here
                  objective="Zeiss 63x",
                  # objective="Zeiss 20x",
                  user="Hannes",
                  #substrate={"Name": "Rectangle print for evaluation of surface of substrate",
                  #           "Number of drops": 1,
                  #           "Used drop": "Mitte",
                  #           "Description": f"Rectangle test for evaluation of plane fitting approach and roughness "
                  #                          f"of the substrate. Rectangle 100µm x 100µm. "
                  #                          f"3x3 rectangles per experiment."},
                  dhm_usage=False,
                  setup="IFOV_on")

    t2 = datetime.datetime.now()
    time = t2 - t1
    print(f"Total time: {time}")


# General ToDos

if __name__ == "__main__":
    main()
