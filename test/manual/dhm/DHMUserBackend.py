##########################################################################
# Copyright (c) 2024 Hannes Robben                                       #
# <hannes.robben@phoenixd.uni-hannover.de>                               #
# This program is free software under the terms of the MIT license.      #
##########################################################################
import logging
import os
from datetime import datetime

import numpy as np
import cv2 as cv
from nanofactorysystem import Dhm, sysConfig, getLogger, mkdir
import nanofactorysystem.image.functions as image

"""
Idee:
tmp folder machen, dort die ganzen Bilder speichern und danach wird eine methode aufgerufen,
die die gesamten aufnahmen speichert (z.B. nach einer Series aufnahme). Bilder werden dann in
dem .zdc Ordner abgelegt und die zuvor gespeicherten Bilder werden nach Speicherung gelöscht.
"""


class DHMBackend:
    HOST = "192.168.22.2"
    PORT = 27182

    args = {
        "dhm": {},
    }
    opl_scan_done = False
    opt_image_calibration = False
    continuous_saving_variable = 0

    def __init__(self, objective="Zeiss 63x", user="Hannes", motor_pos=None, save_path=None):
        self.objective_name = objective
        self.objective = sysConfig.objective(objective)
        self.user = user
        self.client = None

        # standard initialisation optical path length motor position
        if objective == "Zeiss 63x":
            if motor_pos is None:
                # self.motor_pos = 190.0  # even older
                # self.motor_pos = 790.0  # old
                self.motor_pos = 1800.0
            else:
                self.motor_pos = motor_pos
        elif objective == "Zeiss 20x":
            # self.motor_pos = 3732.0
            if motor_pos is None:
                self.motor_pos = 3100.0
                self.motor_pos = 100.0
            else:
                self.motor_pos = motor_pos
        elif objective == "Nikon 20x":
            self.motor_pos = 10.0
            raise Warning("Motor position not selected. Please run the opl motor scan.")
        else:
            raise NotImplementedError(f"Objective {objective} is not implemented. ")

        if save_path is None:
            self.save_path = os.path.join(os.getcwd(), ".output", f"{datetime.now().strftime('%d_%m_%Y-%H:%M')}")
        else:
            self.save_path = save_path
        mkdir(self.save_path, clean=False)  # creating saving directory

        self.logger = getLogger(logfile=f"{self.save_path}/console.log")
        self.logger.setLevel(logging.INFO)
        self.init_dhm()

    def reset(self):
        """
        Resets all necessary variables. ToDo: To be done and implemented!
        """
        self.client = None
        self.objective_name = None
        self.objective = None
        self.motor_pos = None

    def init_dhm(self):
        """
        Initialises the DHM client.
        """
        self.client = Dhm(self.user, self.objective, self.logger, **self.args)
        self.logger.info(f"Motor pos: {self.motor_pos:.1f} µm")

        self.logger.info("Starting camera exposure time optimisation...")
        self.client.getimage()
        self.logger.info("Finished camera exposure time optimisation.")

    def capture_hologram(self, show=False, save=False, img_name=None):
        img, count = self.client.getimage(opt=False)
        img = image.normcolor(img)
        if show:
            cv.imshow("DHM", img)
        if save:
            self.save_hologram(img, img_name)
        return img

    def save_hologram(self, img, filename=None):
        if filename is None:
            filename = "holo_" + str(self.continuous_saving_variable) + ".tif"
            self.continuous_saving_variable += 1
            filename = os.path.join(self.save_path, filename)
        else:
            if filename[-4:] != ".tif":
                if filename[-4] != ".":
                    filename = filename + ".tif"
                else:
                    if filename[-4:] != ".png" and filename[-4:] != ".bmp" and filename[-4:] != ".bin":
                        print("Image file extension will be changed to .tif!")
                        filename = filename[:-4] + ".tif"
            filename = os.path.join(self.save_path, filename)
        cv.imwrite(filename, img)

    def define_capture_grid(self):
        """
        Defines the grid for capturing a series of holograms. Coordinates are relative to the starting position.
        """

    def set_starting_position(self):
        """
        Sets the starting position.
        """

    def capt_holo_series(self):
        """
        Captures a series of hologram depending on a defined grid or distances.
        """

    def change_objective(self, obj_name):
        if obj_name != "Zeiss 63x" and obj_name != "Zeiss 20x" and obj_name != "Nikon 20x":
            raise NotImplementedError(f"Objective {obj_name} is not implemented.")
        self.objective_name = obj_name
        self.objective = sysConfig.objective(obj_name)
        self.opl_scan()

    def opl_scan(self):
        self.logger.info("Run OPL Motor Scan...")
        self.motor_pos = self.client.motorscan()
        self.opl_scan_done = True
        self.logger.info("Motor pos: %.1f µm" % self.client.device.MotorPos)

if __name__ == "__main__":
    objective_selected = "Zeiss 63x"
    desktop = os.path.join(os.path.join(os.environ['USERPROFILE']), 'Desktop')
    path = os.path.join(desktop, "publication_ifov")
    path_2 = os.path.join(path, "lens"
                                "")
    img_getter = DHMBackend(save_path=path_2, objective=objective_selected, motor_pos=190)

    print("Start capturing mode...")
    while True:
        # Display the frame
        cv.imshow('Dhm', img_getter.capture_hologram())

        # Check for key presses
        key = cv.waitKey(10) & 0xFF
        if key == ord('c'):
            # Capture an image
            img_name = input("Enter the name for the captured image: ")
            img_getter.capture_hologram(save=True, img_name=f"{img_name}.tif")
            print(f"Captured {img_name}.tif")
        elif key == ord('q'):
            # Exit the loop
            break
