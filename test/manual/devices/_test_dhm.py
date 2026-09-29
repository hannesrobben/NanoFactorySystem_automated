##########################################################################
# Copyright (c) 2024 Reinhard Caspary                                    #
# <reinhard.caspary@phoenixd.uni-hannover.de>                            #
# This program is free software under the terms of the MIT license.      #
##########################################################################
import time

import cv2
import matplotlib.pyplot as plt
import numpy as np

from nanofactorysystem import Dhm, sysConfig, getLogger, mkdir
from nanofactorysystem.dhm.optimage import optImageMedian
from nanofactorysystem.image.functions import normcolor

args = {
    "dhm": {
        "oplmode": "both",
        },
    }

user = "Reinhard"
objective = "Zeiss 20x"
objective = sysConfig.objective(objective)
path = mkdir(".test/dhm")
logger = getLogger(logfile=f"{path}/console.log")
with Dhm(user, objective, logger, **args) as dhm:
    # t0 = time.perf_counter()
    # for s in [300, 700, 1000]:
    #     dhm.device.CameraShutter = s
    #     means = []
    #     ts = []
    #     for j in range(100):
    #         ts.append(time.perf_counter())
    #         img = dhm.device.CameraImage
    #         img_mean = np.mean(img)
    #         means.append(img_mean)
    #     plt.plot(np.asarray(ts) - t0, means, label=f"{s}")
    #
    # plt.legend()
    # plt.show()
    # exit(0)

    optImageMedian(dhm, vmedian=128, logger=logger)

    m0 = 2750.0
    hist = []
    ref, _ = dhm.getimage(opt=False)
    for i, m in enumerate(np.arange(m0 - 500, m0 + 500, 10)):
    #for i, m in enumerate(np.arange(0, 15000, 75)):
        dhm.device.MotorPos = m
        img, _ = dhm.getimage(opt=False)
        #img = cv2.absdiff(img, ref)
        hist.append(cv2.calcHist(img, [0], None, [256], (0, 255)))
        vlo, vhi = np.quantile(img, [0.05, 0.95], method="nearest")
        c = float(vhi - vlo) / 255
        print(i, m, vlo, vhi, c)
    hist = np.concatenate(hist, axis=1)
    # cv2.namedWindow("hist", cv2.WINDOW_NORMAL)
    #cv2.imshow("hist", normcolor(hist))
    cv2.imwrite("hist.png", normcolor(hist))
    #cv2.waitKey(0)

    dhm.device.MotorPos = 3250.0
    logger.info("Motor scan.")
    m = dhm.motorscan()
    logger.info(f"Motor pos: {dhm.device.MotorPos:.1f} µm (set: {m:.1f} µm)")

    # logger.info("Get hologram container.")
    # dc = dhm.container(opt=True)
    # fn = f"{path}/hologram.zdc"
    # logger.info(f"Store hologram container file '{fn}'")
    # dc.write(fn)
    # print(dc)
    #
    # logger.info("Test camera shutter.")
    # shutter = dhm.device.CameraShutter
    # shutterus = dhm.device.CameraShutterUs
    # logger.info(f"Shutter: {shutterus:.1f} us [{shutter:d}]")

    logger.info("Done.")
