
import logging
import os

import cv2
import matplotlib.pyplot as plt
import numpy as np
from offaxisholo import reconstruct
# from ..nanofactorysystem.postprocessing import utils
from live_tilt_cv import (getImage, showImage)
import nanofactorysystem.image.functions as image
from nanofactorysystem import Dhm, sysConfig, getLogger



############################################################################
# Main function
############################################################################


args = {
    "dhm": {},
}

user = "Hannes"
objective_str = "Zeiss 63x"
objective = sysConfig.objective(objective_str)
path = os.path.join(os.getcwd(), ".test/objective_test")
if not os.path.exists(path): os.mkdir(path)

save_path = os.path.join(path, objective_str)
if not os.path.exists(save_path): os.mkdir(save_path)


opt = True
scan = True
spectrum = False

logger = getLogger()
logger.setLevel(logging.DEBUG)
with Dhm(user, objective, logger, **args) as dhm:
    if opt:
        # dhm.device.MotorPos = 464.8  # 63x objective
        dhm.device.MotorPos = 100.0  # 20x objective
        # dhm.device.MotorPos = 3732.0  # 20x objective
        if scan:
            logger.info("Run OPL Motor Scan...")
            dhm.motorscan()
        logger.info("Motor pos: %.1f µm" % dhm.device.MotorPos)

        logger.info("Optimize Camera Exposure Time...")
        dhm.getimage(opt=True)
        # client.CameraShutter = client.CameraShutter-2
        shutter = dhm.device.CameraShutter
        shutterus = dhm.device.CameraShutterUs
        logger.info(f"Shutter: {shutterus:.1f} us [{shutter:d}]")

    dc = dhm.container()
    # dc.write(os.path.join(save_path, "Holo_noOil_sub+resin_wrongID.zdc"))
    # dc.write(os.path.join(save_path, "Holo_Oil_sub+resin_y20k_z25.3k.zdc"))
    # dc.write(os.path.join(save_path, "Holo_structure(medium)_x_+1.5_y20.1_z25.3.zdc"))


    #
    # logger.info("Start Spectrum Display Loop...")
    # run = True
    # while run:
    #     if spectrum:
    #         img = getImage(dhm)
    #     else:
    #         holo, count = dhm.getimage(opt=False)
    #         img = image.normcolor(holo)
    #         img = image.drawCross(img, 0, 0, 30, image.CV_RED, 1)
    #     showImage(img)
    #     if cv2.waitKey(10) == ord("q"):
    #         print("Quitting...")
    #         run = False
    #
    # logger.info("Done.")
