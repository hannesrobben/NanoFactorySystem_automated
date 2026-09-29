##########################################################################
# Copyright (c) 2022-2024 Reinhard Caspary                               #
# <reinhard.caspary@phoenixd.uni-hannover.de>                            #
# This program is free software under the terms of the MIT license.      #
##########################################################################
#
# This module provides a class for Matrix Vision cameras.
#
##########################################################################

from ..camera import CameraDevice, optExpose
from ..config import sysConfig, popargs, ConfigDefaults
from ..image import ImageContainer
from ..parameter import Parameter


class Camera(Parameter):
    """ Camera class. """

    _defaults = ConfigDefaults("camera", {
        "AcquisitionMode": "SingleFrame",
        "ExposureMode": "Timed",
        "ExposureTime": 20000,
        "ExposureAuto": 0,
        "mvGainMode": "Default",
        "GainSelector": "AnalogAll",
        "Gain": 0,
        "GainAuto": 0,
    })

    def __init__(self, user, objective, logger=None, *, driver=None, **kwargs):

        """ Initialize the camera.

        Parameters
        ----------
        user : str
            User key in the configuration.
        objective : dict
            Objective data dictionary.
        logger : logging.Logger, optional
            Logger object.
        driver : CameraDriver, optional
            Camera driver to use instead of opening the MatrixVision device
            ``CameraDevice(product, deviceID)``, e.g. a simulated driver of
            the dummy backend.
        **kwargs
            Runtime configuration with the optional section ``camera``.
        """
        # Not open now
        self.opened = False

        # Objective parameters
        self.objective = objective

        # Initialize parameter class
        args = popargs(kwargs, "camera")
        product = args.pop("product", None)
        deviceID = args.pop("deviceID", None)
        super().__init__(user, logger, **args)
        self.log.info("Initializing camera.")

        # Open camera device
        if driver is None:
            self.device = CameraDevice(product, deviceID)
        else:
            self.device = driver
        self.opened = self.device.opened
        if not self.opened:
            self.log.error("Initializing of camera device failed!")
            return
        self.log.info(f"Camera: {self.device}")

        # Apply initial parameters
        for key, value in self._params.items():
            self.device[key] = value
        self.setaoi(None)

        # Done
        self.log.info("Initialized camera.")

    def __enter__(self):

        """ Context manager entry method. """

        return self

    def __exit__(self, errtype, value, tb):

        """ Context manager exit method. """

        self.device.close()

    def close(self):

        """ Close camera device. """

        # Closed already
        if not self.opened:
            return

        self.device["AcquisitionMode"] = "Continuous"

        # Close the device
        self.device.close()
        self.opened = False
        self.log.info("Camera closed.")

    def setaoi(self, size=None):

        """ Set area of interest to given quadratic field centered on
        the sensor. Set to full sensor size if no size is given. """

        if not self.opened:
            raise RuntimeError("Camera device closed!")

        # Determine minimum and maximum values
        self.device["OffsetX"] = 0
        self.device["OffsetY"] = 0
        wmin = self.device.property("Width").minValue
        wmax = self.device.property("Width").maxValue
        hmin = self.device.property("Height").minValue
        hmax = self.device.property("Height").maxValue

        # Maximize area of interest
        if size is None:
            self.device["Width"] = wmax
            self.device["Height"] = hmax
            self.w, self.h = wmax, hmax

        # Set area of interest to center of the camera sensor
        else:
            size = max(size, wmin, hmin)
            size = min(size, wmax, hmax)
            x = (wmax - size) // 2
            y = (hmax - size) // 2
            self.device["Width"] = size
            self.device["Height"] = size
            self.device["OffsetX"] = x
            self.device["OffsetY"] = y
            self.w = size
            self.h = size

    def optexpose(self, level=127):

        """ Find exposure time resulting in a given mean value of the image
        content. """

        if not self.opened:
            raise RuntimeError("Camera device closed!")
        self.log.info("Start exposure time optimization.")

        t = optExpose(self.device, level)
        img = self.device.getimage()
        avg = img.mean()
        self.log.info(f"Optimized exposure time: {0.001 * t:.3f} ms, mean image value: {avg:.1f} (goal: {level:d})")
        return img, t

    def getimage(self):

        """ Grab and return a camera image. """

        if not self.opened:
            raise RuntimeError("Camera device closed!")

        return self.device.getimage()

    def info(self):

        """ Return a dictionary containing the camera device info. """

        return {
            "family": self.device["family"],
            "product": self.device["product"],
            "serial": self.device["serial"],
            "id": self.device["deviceID"],
        }

    def container(self, loc=None, config=None, **kwargs) -> ImageContainer:

        """ Return current camera image as ImageContainer. """

        # Grab camera image
        kwargs["img"] = self.getimage()

        # Camera parameters
        kwargs["params"] = self.parameters()

        # Objective parameters
        kwargs["objective"] = self.objective

        # Location coordinates
        kwargs["loc"] = loc

        # User configuration        
        kwargs["config"] = config or self.config

        # Return container object
        return ImageContainer(items=None, **kwargs)
