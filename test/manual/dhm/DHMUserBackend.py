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
Idea:
Create a temporary folder and save all images there; afterwards a method is called that stores
all captures together (e.g. after a series capture). The images are then placed in the .zdc
folder, and the previously saved single images are deleted once they are stored.
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
        self.initial_motor_pos = motor_pos
        self.motor_pos = self.default_motor_pos(objective, motor_pos)

        if save_path is None:
            self.save_path = os.path.join(os.getcwd(), ".output", f"{datetime.now().strftime('%d_%m_%Y-%H:%M')}")
        else:
            self.save_path = save_path
        mkdir(self.save_path, clean=False)  # creating saving directory

        self.logger = getLogger(logfile=f"{self.save_path}/console.log")
        self.logger.setLevel(logging.INFO)
        self.init_dhm()

    @staticmethod
    def default_motor_pos(objective, motor_pos=None):
        """ Return the OPL motor position to start with: ``motor_pos`` or the default of the objective.

        Raises
        ------
        Warning
            For the Nikon 20x, which has no default; run the OPL motor scan.
        NotImplementedError
            For an unknown objective.
        """

        if objective == "Zeiss 63x":
            # Earlier defaults: 190.0, 790.0
            return 1800.0 if motor_pos is None else motor_pos
        if objective == "Zeiss 20x":
            # Earlier defaults: 3732.0, 3100.0
            return 100.0 if motor_pos is None else motor_pos
        if objective == "Nikon 20x":
            raise Warning("Motor position not selected. Please run the opl motor scan.")
        raise NotImplementedError(f"Objective {objective} is not implemented. ")

    def reset(self, reconnect=True):
        """ Return the helper to the state after construction.

        The DHM client is closed, the OPL motor position goes back to the
        start value of the current objective, the OPL-scan and calibration
        flags and the file counter are cleared. The objective and the save
        folder are kept.

        Parameters
        ----------
        reconnect : bool
            Connect a new DHM client afterwards (as the constructor does);
            otherwise ``client`` stays None until :meth:`init_dhm` is called.
        """

        if self.client is not None:
            try:
                self.client.close()
            finally:
                self.client = None
        self.motor_pos = self.default_motor_pos(self.objective_name, self.initial_motor_pos)
        self.opl_scan_done = False
        self.opt_image_calibration = False
        self.continuous_saving_variable = 0
        self.logger.info("DHM helper reset.")
        if reconnect:
            self.init_dhm()

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
