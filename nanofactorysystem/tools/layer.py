##########################################################################
# Copyright (c) 2022-2024 Reinhard Caspary                               #
# <reinhard.caspary@phoenixd.uni-hannover.de>                            #
# This program is free software under the terms of the MIT license.      #
##########################################################################
#
# This module provides a photoresin layer detector class for the Laser
# Nanofactory system from Femtika.
#
##########################################################################

import math
import numpy as np
from skimage.registration import phase_cross_correlation
from scidatacontainer import Container

from ..parameter import Parameter, Orientation, Interface, Result, flex_round
from ..config import popargs
from ..runtime import mkdir
from ..image import functions as image
from .focus import Focus, focusStatus
from .detector import Scanner
from .bisect import Locator


##########################################################################
class Spiral:

    """ Object, which delivers x,y coordinate tuples forming a quadratic spiral
    starting at the given center point (index 0) and with the given pitch."""

    def __init__(self, x, y, pitch):

        self.x = x
        self.y = y
        self.pitch = pitch
        self.index = 0

    def next(self):

        x, y = self.position(self.index)
        self.index += 1
        return x, y

    def position(self, index):

        """ Return x,y coordinates of point with given index. """

        # Sanity checks
        assert(isinstance(index, int))
        assert(index >= 0)

        # Start at center point
        if index == 0:
            i, j = 0, 0

        # Other points
        else:
            # Radius 1, 2, 3, ...
            fp, r = math.modf(0.5 * (math.sqrt(index) + 1))
            r = round(r)

            # Side 0, 1, 2, or 3
            v = index - (4 * r * (r - 1) + 1)
            s = v // (2 * r)

            # Position on the side -r+1 ... +r
            p = (v % (2 * r)) - r + 1

            # Integer x, y coordinates relative to center point
            if s == 0:
                i, j = p, -r
            elif s == 1:
                i, j = r, p
            elif s == 2:
                i, j = -p, r
            else:
                i, j = -r, -p

        # Return pair of coordinates
        x = self.x + i * self.pitch
        y = self.y + j * self.pitch
        return x, y


##########################################################################
class LayerDetectionError(Exception):

    pass

class Layer(Parameter):

    """ Layer edge detector class. After initializing just call the
    method detect() to run the edge detection. """

    _defaults = {
        "xCenter": None,
        "yCenter": None,
        "dzCoarseDefault": 50.0,
        "dzFineDefault": 45.0,
        "laserPower": 0.7,
        "stageSpeed": 200.0,
        "duration": 0.2,
        "stretch": 1.5,
        "overlap": 0.3,
        "jitter": 0.5,
        "beta": 0.7,
        "resolution": 0.5,
        "lateralPitch": 4.0,
        }

    def __init__(self, system, logger=None, **kwargs):

        """ Initialize the layer scan object. """

        # Store system object
        self.system = system
        user = self.system.user["key"]
        # self["sampleOrientation"] = self.system.sample['sample']["orientation"]
        
        # Initialize parameter class
        args = popargs(kwargs, "layer")
        super().__init__(user, logger, **args)
        self.log.info("Initializing layer detector.")

        # Store minimum and maximum allowed z position
        self.zmin = 0.0
        self.zmax = self.system.controller["zMax"]

        # Initialize focus detection
        args = popargs(kwargs, "focus")
        self.focus = Focus(self.system, logger, **args)

        # No result yet
        self.steps = None
        self.log.info("Initialized layer detector.")

    def focus_result(self):

        """ Return focus result as either Result.HIT, Result.MISS or Result.AMBIGUOUS. """

        status = self.focus.result["status"]
        if status == focusStatus.focus:
            result = Result.HIT
        elif status == focusStatus.nofocus:
            result = Result.MISS
        else:
            result = Result.AMBIGUOUS
        return result

    def interface_mode(self, z_low=None, z_high=None):

        """ Return given z position and interface mode based on given approximate values for high
         and/or low interface. """

        # Both values given, take mean
        if z_low is not None and z_high is not None:
            interface = Interface.BOTH
            z = 0.5 * (z_low + z_high)

        # Low interface only
        elif z_low is not None:
            interface = Interface.LOW
            z = z_low

        # High interface only
        elif z_high is not None:
            interface = Interface.HIGH
            z = z_high

        # No interface is an error
        else:
            raise ValueError("Unknown interface!")

        # Return approximate z position and Interface object
        return z, interface

    def run(self, x, y, z_low=None, z_high=None, coarse=False, dz=None, path=None, home=True):

        """ Main method of the layer detector. Find the z coordinates of the low and/or high interface
        of the photoresist layer for the interfaces with given start value z_low or z_high. Start with
        a coarse scan, if requested. Return results as layer container object. """

        self.log.info("Photoresist layer detection started.")

        # Store current xyz position
        x0, y0, z0 = self.system.position("XYZ")

        # Initialize quadratic spiral of x,y scanning points
        self["xCenter"] = float(x)
        self["yCenter"] = float(y)
        spiral = Spiral(self["xCenter"], self["yCenter"], self["lateralPitch"])

        # Coarse guess of z location and interface mode
        z_guess, interface = self.interface_mode(z_low, z_high)

        # Initialize result lists
        self.steps = []
        self.offsets = []
        self.result = {}

        # Coarse interface scanner
        if coarse:
            if dz is None:
                dz = self["dzCoarseDefault"]

            # orientation = Orientation[self["sampleOrientation"].upper()]
            # orientation = Orientation["DOWN"]
            orientation = Orientation["UP"]
            scanner = Scanner(z_guess, dz, self.zmin, self.zmax, orientation, interface, self["stretch"], self["overlap"], self["jitter"], self.log)
            self.result["coarse"] = self.scan(spiral, scanner, "coarse", path)
            if z_low is not None:
                z_low, dz_low = scanner.low_edge
            else:
                z_low, dz_low = None, None
            if z_high is not None:
                z_high, dz_high = scanner.high_edge
            else:
                z_high, dz_high = None, None
            self.zmin = scanner.zmin
            self.zmax = scanner.zmax
        else:
            dz_low = dz_high = dz

        # Low interface locator using bisection
        if Interface.LOW in interface:
            if dz_low is None:
                dz = self["dzFineDefault"]
            else:
                dz = dz_low
            locator = Locator(z_low, dz, self.zmin, self.zmax, Interface.LOW, self["beta"], self["jitter"], self["resolution"], self.log)
            self.result["low"] = self.scan(spiral, locator, "fine low", path)
            z_low, dz_low = locator.z, locator.dz
        else:
            z_low, dz_low = None, None

        # High interface locator using bisection
        if Interface.HIGH in interface:
            if dz_high is None:
                dz = self["dzFineDefault"]
            else:
                dz = dz_high
            locator = Locator(z_high, dz, self.zmin, self.zmax, Interface.HIGH, self["beta"], self["jitter"], self["resolution"], self.log)
            self.result["high"] = self.scan(spiral, locator, "fine high", path)
            z_high, dz_high = locator.z, locator.dz
        else:
            z_high, dz_high = None, None

        # Evaluate focus offsets
        dx, dy = np.mean(self.offsets, axis=0)
        sx, sy = np.std(self.offsets, axis=0)
        self.result["camera"] = {
            "xOffsetMean": dx,
            "yOffsetMean": dy,
            "xOffsetStd": sx,
            "yOffsetStd": sy,
            "numOffset": len(self.offsets),
            }

        # Update current coordinate transformation matrix
        self.system.update_pos("focus", dx, dy, sx, sy, len(self.offsets))

        if z_low is not None:
            self.log.info("Low resin interface: %g [%g]" % flex_round(z_low, dz_low))
        if z_high is not None:
            self.log.info("High resin interface: %g [%g]" % flex_round(z_high, dz_high))
        self.log.info("Photoresist layer detection finished.")

        # Move stages back to initial position
        if home:
            self.system.moveabs(x=x0, y=y0, z=z0)

    def scan(self, spiral, scanner, mode, path=None):

        for z, dz in scanner:

            # Next exposure coordinates
            index = len(self.steps)
            x, y = spiral.position(index)

            # Expose an axial line and detect the focus
            self.focus.run(x, y, z, dz, self["laserPower"], self["stageSpeed"], self["duration"])
            focus_dc = self.focus.container()
            if path:
                subpath = mkdir(f"{path}/focus-{index:02d}")
                self.focus.imgPre.write(f"{subpath}/image_pre.zdc")
                self.focus.imgPost.write(f"{subpath}/image_post.zdc")
                focus_dc.write(f"{subpath}/focus.zdc")

            # Register the focus detection result
            result = self.focus_result()
            scanner.register(z, dz, result)

            # Store parameters and results of this step
            step = dict(self.focus.exposure)
            step.update({
                "exposure": index,
                "scanMode": mode,
                "focusStatus": result.name.lower(),
                "focusUuid": focus_dc.uuid,
                "finished": scanner.finished,
                })
            if result == Result.HIT:
                step.update({
                    "focusOffset": self.focus.result["focusOffset"],
                    "focusArea": self.focus.result["focusArea"],
                    "circularity": self.focus.result["circularity"],
                    })
                self.offsets.append(self.focus.result["focusOffset"])
            self.steps.append(step)

            # Send info line to logger
            step = f"Step {index:d} ({mode}):"
            z = "%g [%g]" % flex_round(z, dz)
            hit = result.name.lower()
            status = scanner.status()
            self.log.debug(f"{step:<20} {z:>16} -> {hit:<9} | {status}")

        if not scanner.finished:
            raise LayerDetectionError(f"Layer detection '{mode}' failed!")
        return scanner.result()

    def pitch(self):
        
        """ Improve the camera pitch matrix from the configuration file by
        registering images of the layer test structure in all for cardinal
        directions. Store the new camera pitch matrix in the results
        dictionary. """
        
        if not self.result:
            raise RuntimeError("Run layer scan first!")
            
        # Lateral center of the test spiral
        x0 = self["xCenter"]        
        y0 = self["yCenter"]
        
        # Camera z position
        if "low" in self.result and "high" in self.result:
            z0 = 0.5 * (self.result["low"]["z"] + self.result["high"]["z"])
        elif "low" in self.result:
            z0 = self.result["low"]["z"]
        else:
            z0 = self.result["high"]["z"]

        # Stage coordinates required to place the camera focus in the center
        # of the test spiral
        x, y, z = self.system.stage_pos([x0, y0, z0], [0, 0])

        # Lateral camera shift for the test images
        shift = self["lateralPitch"]
        
        # Size of AOI is twice the size of the test spiral
        size = round(np.sqrt(len(self.steps))) * self["lateralPitch"]
        size += 2 * shift
        size = self.system.camera_pos([size, size], [0, 0])
        size = 2 * round(np.abs(size).max())

        # Delay after stage movement
        delay = self.system["delay"]

        # Take image in the center and all four cardinal directions
        self.system.moveabs(x=x, y=y, z=z, wait=delay)
        imgC = image.crop(self.system.getimage().img, size)
        self.system.moveabs(x=x-shift, y=y, z=z, wait=delay)
        imgW = image.crop(self.system.getimage().img, size)
        self.system.moveabs(x=x+shift, y=y, z=z, wait=delay)
        imgE = image.crop(self.system.getimage().img, size)
        self.system.moveabs(x=x, y=y-shift, z=z, wait=delay)
        imgS = image.crop(self.system.getimage().img, size)
        self.system.moveabs(x=x, y=y+shift, z=z, wait=delay)
        imgN = image.crop(self.system.getimage().img, size)

        # Horizontal and vertical shift in pixels
        diffE = image.diff(imgC, imgE)
        diffW = image.diff(imgW, imgC)    
        diffN = image.diff(imgC, imgN)
        diffS = image.diff(imgS, imgC)
        args = {
            "normalization": None,
            "upsample_factor": 20,
            "overlap_ratio": 0.3
            }
        (pxy, pxx), err_x, _ = phase_cross_correlation(diffW, diffE, **args)
        (pyy, pyx), err_y, _ = phase_cross_correlation(diffS, diffN, **args)

        # Pixel pitch matrix    
        inv_pitch = np.array([[pxx, pxy], [pyx, pyy]], dtype=float) / shift
        pitch = np.linalg.inv(inv_pitch)
        self.result["camera"]["cameraPitch"] = pitch.tolist()
        self.result["camera"]["cropSize"] = size
        self.result["camera"]["horzPitchCorrelation"] = err_x
        self.result["camera"]["vertPitchCorrelation"] = err_y
        
        # Update current coordinate transformation matrix
        self.system.update_pos("layer", pitch, size, err_x, err_y)

        # Done.
        return pitch

    def container(self, config=None, **kwargs):

        """ Return results as SciDataContainer. """

        if self.result is None:
            raise RuntimeError("No results!")

        # Collect UUIDs of focus detections as references
        refs = {}
        for step in self.steps:
            key = f"focus-{step['exposure']:02d}"
            refs[key] = step["focusUuid"]

        # General metadata
        content = {
            "containerType": {"name": "LayerDetect", "version": 1.1},
            }
        meta = {
            "title": "Layer Detection Data",
            "description": "Detection of upper and lower photoresin interfaces.",
            }

        # Container dictionary
        items = self.system.items() | {
            "content.json": content,
            "meta.json": meta,
            "references.json": refs,
            "data/layer.json": self.parameters(),
            "meas/steps.json": self.steps,
            "meas/result.json": self.result,
            }

        # Return container object
        config = config or self.config
        return Container(items=items, config=config, **kwargs)
