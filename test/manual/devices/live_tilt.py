##########################################################################
# Copyright (c) 2024 Reinhard Caspary                                    #
# <reinhard.caspary@phoenixd.uni-hannover.de>                            #
# This program is free software under the terms of the MIT license.      #
##########################################################################

import logging
import numpy as np
import matplotlib.pyplot as plt

from offaxisholo import reconstruct

from nanofactorysystem import Dhm, sysConfig, getLogger
import nanofactorysystem.image.functions as image

run = False

############################################################################
# Utility functions
############################################################################

def on_close(event):

    global run
    run = False
    print("Quitting...")


def getImage(dhm):

    #holo_get, count = dhm.getimage(opt=False)
    #return image.normcolor(holo_get)
    holo, count = dhm.getimage()
    spectrum, fx, fy, weight = reconstruct.locateOrder(holo, 16)
    dhm.log.info(f"First order coordinates: {fx:d}, {fy:d} [{100 * weight:.1f}%]")

    maxpixel = 255
    numof = np.count_nonzero(holo >= maxpixel)
    dhm.log.info(f"Overflow pixels: {numof:d}")
    
    img = np.log(np.abs(spectrum))
    h, w = img.shape
    vmax = 0.5*np.max(img)
    img = np.where(img > vmax, vmax, img) 

    img = image.normcolor(img)    
    r0 = dhm.objective["dcRadius"]
    img = image.drawCircle(img, 0, 0, r0, image.CV_RED, 1)
    
    rmax = np.sqrt(fx**2 + fy**2) - r0
    rmax = min(rmax, abs(fx), w//2-abs(fx), abs(fy), h//2-abs(fy))
    dhm.log.info(f"Maximum radius: {rmax:.0f} pixels")
    if rmax > 0:
        img = image.drawCircle(img, fx, fy, rmax, image.CV_RED, 1)
        img = image.drawCircle(img, -fx, -fy, rmax, image.CV_RED, 1)
    img = image.drawCross(img, fx, fy, 30, image.CV_RED, 1)
    img = image.drawCross(img, -fx, -fy, 30, image.CV_RED, 1)
    return img


def showImage(ax, img, win):

    h, w, d = img.shape
    border = 20
    img = image.addBorder(img, border, 127)
    extent = [-w//2-border, w//2+border-1, -h//2-border, h//2+border-1]

    if win is None:
        win = ax.imshow(img[:,:,::-1], origin="lower", extent=extent)
    else:
        win.set_data(img[:,:,::-1])
    plt.pause(0.1)
    return win


############################################################################
# Main function
############################################################################

if __name__ == "__main__":

    args = {
        "dhm": {},
        }

    user = "Reinhard"
    objective = "Zeiss 20x"
    objective = sysConfig.objective(objective)
    #path = mkdir(".test/tilt")
    opt = True
    
    fig, ax = plt.subplots()
    fig.canvas.mpl_connect("close_event", on_close)

    logger = getLogger()
    logger.setLevel(logging.INFO)
    with Dhm(user, objective, logger, **args) as dhm:

        if opt:
            dhm.device.MotorPos = 5079
            #logger.info("Run OPL Motor Scan...")
            #dhm.motorscan()
            logger.info("Motor pos: %.1f µm" % dhm.device.MotorPos)

            logger.info("Optimize Camera Exposure Time...")
            dhm.getimage(opt=True)
            #client.CameraShutter = client.CameraShutter-2
            shutter = dhm.device.CameraShutter
            shutterus = dhm.device.CameraShutterUs
            logger.info(f"Shutter: {shutterus:.1f} us [{shutter:d}]")
        
        logger.info("Start Spectrum Display Loop...")
        run = True
        win = None
        while run:
            img = getImage(dhm)
            win = showImage(ax, img, win)
            #print(np.mean(img))
            #plt.pause(0.1)

        logger.info("Done.")
