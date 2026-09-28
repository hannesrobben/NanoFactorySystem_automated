##########################################################################
# Copyright (c) 2022-2024 Reinhard Caspary                               #
# <reinhard.caspary@phoenixd.uni-hannover.de>                            #
# This program is free software under the terms of the MIT license.      #
##########################################################################
#
# This module provides the class CameraDevice to access an industrial
# camera from Matrix Vision.
#
##########################################################################
# Default camera settings:
# ------------------------
# Device
#     Family mvBlueFOX3
#     Product mvBlueFOX3-2032aG
#     Serial FF008343
#     DeviceID 0
# Setting - Base - Camera - GenICam - 
# AcquisitionControl        
#     AcquisitionMode Continuous, MultiFrame, SingleFrame
#     ExposureMode Timed, TriggerWidth
#     ExposureTime 20000.000
#     ExposureAuto Off, Continuous
# AnalogControl
#     mvGainMode: Default
#     GainSelector: AnalogAll, DigitalAll
#         Gain: 0.000
#         GainAuto: Off, Continuous
##########################################################################

import ctypes

import numpy as np

# The MatrixVision library mvIMPACT is imported on first use, so that the
# package can be imported on machines without it (e.g. with the dummy backend).
acquire = None


def _import_acquire():
    """ Import ``mvIMPACT.acquire`` on first use.

    Returns
    -------
    module
        The ``mvIMPACT.acquire`` module.

    Raises
    ------
    ImportError
        If mvIMPACT is not installed.
    """

    global acquire
    if acquire is None:
        try:
            from mvIMPACT import acquire as _acquire
        except ImportError as error:
            raise ImportError(
                "The real camera backend needs mvIMPACT (Balluff/MATRIX VISION mvGenTL Acquire, "
                "https://assets.balluff.com/documents/DRF_957356_AA_000/Building_page.html). "
                "Install it, or use System(..., backend='dummy') for simulated hardware."
            ) from error
        acquire = _acquire
    return acquire


##########################################################################
class Property(object):

    def __init__(self, device, name, mvProperty):

        # Store parameters
        self.device = device
        self.name = name

        # Locate component
        locator = acquire.DeviceComponentLocator(self.device, acquire.dltSetting, "Base")
        if locator.findComponent(self.name) < 0:
            raise RuntimeError(f"Component '{self.name}' not found!")

        # Bind component to a property object
        self.obj = mvProperty
        locator.bindComponent(self.obj, self.name)

    @property
    def minValue(self):

        if not self.obj.hasMinValue:
            raise AttributeError(f"Component '{self.name}' has no min value!")
        return self.obj.getMinValue()

    @property
    def maxValue(self):

        if not self.obj.hasMaxValue:
            raise AttributeError(f"Component '{self.name}' has no max value!")
        return self.obj.getMaxValue()

    @property
    def choices(self):

        if not self.obj.hasDict:
            raise AttributeError(f"Component '{self.name}' is no selector!")
        size = self.obj.dictSize()
        return [self.obj.getTranslationDictString(i) for i in range(size)]

    @property
    def value(self):

        return self.obj.read()

    @value.setter
    def value(self, v):

        self.obj.write(v)


class PropertyS(Property):

    def __init__(self, device, name):
        super().__init__(device, name, acquire.PropertyS())


class PropertyInt(Property):

    def __init__(self, device, name):
        super().__init__(device, name, acquire.PropertyI64())


class PropertyFloat(Property):

    def __init__(self, device, name):
        super().__init__(device, name, acquire.PropertyF())


class PropertySelect(Property):

    def __init__(self, device, name):

        super().__init__(device, name, acquire.PropertyI())

    @property
    def value(self):

        return self.obj.readS()

    @value.setter
    def value(self, v):

        if not isinstance(v, str):
            if not isinstance(v, int):
                raise ValueError("Selection value not integer!")
            size = self.obj.dictSize()
            if v < 0 or v >= size:
                raise ValueError(f"Selection value {v:d} not in range 0-{size - 1:d}!")
            v = self.obj.getTranslationDictString(v)
        self.obj.writeS(v)


##########################################################################
class CameraDevice(object):
    """ MatrixVision camera device class. This is a convenience wrapper to the
    MatrixVision library. """

    # Property classes
    _properties = {
        "family": None,
        "product": None,
        "serial": None,
        "deviceID": None,
        "Width": PropertyInt,
        "Height": PropertyInt,
        "OffsetX": PropertyInt,
        "OffsetY": PropertyInt,
        "AcquisitionMode": PropertySelect,
        "ExposureMode": PropertySelect,
        "ExposureTime": PropertyFloat,
        "ExposureAuto": PropertySelect,
        "mvGainMode": PropertySelect,
        "GainSelector": PropertySelect,
        "Gain": PropertyFloat,
        "GainAuto": PropertySelect,
    }

    def __init__(self, product=None, deviceID=None):

        """ Initialize the camera. """

        # Initialize attributes
        _import_acquire()
        self._property = {}

        # Get camera device
        self.opened = False
        self.manager = acquire.DeviceManager()
        if product is None:
            self.device = self.manager.getDevice(0)
        else:
            if deviceID is None:
                assert isinstance(product, str)
                self.device = self.manager.getDeviceByProductAndID(product)
            else:
                assert isinstance(deviceID, str)
                self.device = self.manager.getDeviceByProductAndID(product, deviceID)

        # Initialize the camera device
        try:
            self.device.open()
        except acquire.EDeviceManager:
            return
        self.opened = True

        # Store a function interface and clear the request and the
        # result queue
        self.fi = acquire.FunctionInterface(self.device)

    def close(self):

        """ Close camera device. """

        self.device.close()
        self._property = {}

    def __str__(self):

        """ Return description string for the camera. """

        if self.opened:
            result = (f"Camera {self['deviceID']:d}: "
                      f"{self['product']} "
                      f"(S/N {self['serial']}), {self['Width']:d} x {self['Height']:d} pixel.")
        else:
            result = "Camera closed."
        return result

    def keys(self):

        return list(self._properties.keys())

    def __setitem__(self, key, value):

        if key in self._property:
            self._property[key].value = value
            return

        if key in self._properties:
            cls = self._properties[key]
            if cls is None:
                raise RuntimeError(f"Item {key} is read-only!")
            self._property[key] = cls(self.device, key)
            self._property[key].value = value
            return

        raise KeyError(f"Unknown item {key}!")

    def __getitem__(self, key):

        if key in self._property:
            return self._property[key].value

        if key in self._properties:
            cls = self._properties[key]
            if cls is None:
                value = getattr(self.device, key).read(0)
            else:
                self._property[key] = cls(self.device, key)
                value = self._property[key].value
            return value

        raise KeyError(f"Unknown item {key}!")

    def property(self, key):

        if key in self._property:
            return self._property[key]

        if key in self._properties:
            self._property[key] = self._properties[key](self.device, key)
            return self._property[key]

        raise KeyError(f"Unknown item {key}!")

    def getimage(self) -> np.ndarray:

        """ Grab and return a camera image. """

        img = None

        # Place an image request in the request queue
        self.fi.imageRequestSingle()

        # Get result number from the result queue
        timeout = max(50, round(2000 * self["ExposureTime"]))
        if np.log(timeout) / np.log(2) >= 32.0:
            raise RuntimeError("Timeout must be a 32 bit integer!")
        reqno = self.fi.imageRequestWaitFor(timeout)
        if self.fi.isRequestNrValid(reqno):

            # Get result from the result queue
            req = self.fi.getRequest(reqno)
            # if req.imagePixelFormat.read() == 28:
            #     print("Pixel Format is mvIMPACT.acquire.ibpfMono12Packed_V1.")  # https://assets.balluff.com/documents/DRF_957356_AA_000/classmvIMPACT_1_1acquire_1_1Request.html#a491bca5fe5a03e9523a411a90d8b29cd
            if req.isOK:

                # Get image meta data
                addr = int(req.imageData.read())
                size = req.imageSize.read()
                width = req.imageWidth.read()
                height = req.imageHeight.read()
                depth = req.imageChannelBitDepth.read()
                channels = req.imageChannelCount.read()
                if channels != 1:
                    raise RuntimeError("Gray scale camera required!")

                # Copy image data to numpy array
                cbuf = (ctypes.c_char * size).from_address(addr)
                # note: if depth is not 16 the dtype is not correctly chosen and one need to change the PixelFormat
                dtype = np.uint16 if depth > 8 else np.uint8
                img = np.copy(np.frombuffer(cbuf, dtype=dtype))

                # print(f"size={size}, width={width}, height={height}, depth={depth}")
                # print(f"Array length: {len(img)}, Expected: {height * width}")


                img.shape = (height, width)

            # Unlock the request object
            req.unlock()
            req = None

        if img is None:
            raise RuntimeError("Image grabbing failed!")
        return img
