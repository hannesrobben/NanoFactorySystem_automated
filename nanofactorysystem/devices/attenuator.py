##########################################################################
# Copyright (c) 2022-2024 Reinhard Caspary                               #
# <reinhard.caspary@phoenixd.uni-hannover.de>                            #
# This program is free software under the terms of the MIT license.      #
##########################################################################
#
# This module provides access to the attenuator calibration file.
#
##########################################################################

import struct

import numpy
from scidatacontainer import Container, register
from scipy.interpolate import interp1d

from ..config import sysConfig, popargs, ConfigDefaults
from ..parameter import Parameter

# Register binary data calibration format
register("dat", "bin")


##########################################################################
class Attenuator(Parameter):
    """ Class for the laser attenuator of the Femtika Laser Nanofactory.
    It loads a calibration file and provides translation between
    attenuator value and laser power in both directions. """

    _defaults = ConfigDefaults("attenuator", {
        "calibrationFile": None,
        "fitKind": "cubic",
        "polynomialOrder": None,
        "valueMin": 0.0,
        "valueMax": 10.0,
        "powerMin": None,
        "powerMax": None,
    }, from_config=("calibrationFile",))

    def __init__(self, user, logger=None, **kwargs):

        # Initialize parameter class
        args = popargs(kwargs, "attenuator")
        super().__init__(user, logger, **args)
        self.log.info("Initializing attenuator.")

        # Read content of the binary calibration file
        if self["calibrationFile"] is None:
            raise RuntimeError("attenuator.calibrationFile is not configured! Set it in the config file "
                               "or pass it in the 'attenuator' section of the arguments.")
        with open(self["calibrationFile"], "rb") as fp:
            self.raw = fp.read()
        if len(self.raw) % 16:
            raise RuntimeError("File size must be a multiple of 16!")

        # Convert calibration data to numpy array. First column are
        # attenuator values, second column is laser power in mW.
        self.num = len(self.raw) // 16
        fmt = "<" + 2 * self.num * "d"
        self.data = struct.unpack(fmt, self.raw)
        self.data = numpy.array(self.data)
        self.data.shape = (self.num, 2)

        # Either spline or polynomial interpolation.
        # Warning: Polynomial interpolation (in contrast to spline
        # interpolation) does not necessarily contain the original data
        # points!
        a = self.data[:, 0]
        p = self.data[:, 1]
        if self["fitKind"] == "poly":
            order = self["polynomialOrder"]
            if order is None:
                order = self["polynomialOrder"] = 2
            self.atop = numpy.poly1d(numpy.polyfit(a, p, order))
            self.ptoa = numpy.poly1d(numpy.polyfit(p, a, order))
        else:
            self.atop = interp1d(a, p, kind=self["fitKind"])
            self.ptoa = interp1d(p, a, kind=self["fitKind"])

        # Attenuator range is always 0..10
        if min(a) != self["valueMin"]:
            raise RuntimeError(f"Attenuator data must start at {self['valueMin']:.1f}!")
        if max(a) != self["valueMax"]:
            raise RuntimeError(f"Attenuator data must end at {self['valueMax']:.1f}!")

        # Power range
        self["powerMin"] = min(p)
        self["powerMax"] = max(p)

        # Done
        self.log.info(str(self))
        self.log.info("Initialized attenuator.")

    def __str__(self):

        return f"Attenuator: {self['powerMin']:.2f} - {self['powerMax']:.2f} mW ({self.num:d} steps)."

    def info(self):

        """ Return information dictionary. """

        result = self.parameters()
        result["calibration"] = self.data.tolist()
        return result

    def container(self, config=None, **kwargs):

        """ Return results as SciDataContainer. """

        # General metadata
        content = {
            "containerType": {"name": "PowerAttenuator", "version": 1.1},
        }
        meta = {
            "title": "Laser power calibration data",
            "description": "Calibration data for laser attenuator.",
        }

        # Calibration data in JSON format
        data = {"calibration": self.data.tolist()}

        # Create container dictionary
        items = {
            "content.json": content,
            "meta.json": meta,
            "data/attenuator.json": self.parameters(),
            "meas/calibration.json": data,
            "meas/calibration.dat": self.raw,
        }

        # Return container object
        config = config or self.config
        return Container(items=items, config=config, **kwargs)
