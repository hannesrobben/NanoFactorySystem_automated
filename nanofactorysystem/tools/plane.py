##########################################################################
# Copyright (c) 2022-2024 Reinhard Caspary                               #
# <reinhard.caspary@phoenixd.uni-hannover.de>                            #
# This program is free software under the terms of the MIT license.      #
##########################################################################
#
# This module provides a photoresin interface plane class for the Laser
# Nanofactory system from Femtika.
#
##########################################################################
from functools import cached_property

import numpy as np
from scidatacontainer import Container

from ..parameter import Parameter
from ..config import popargs
from ..devices.coordinate_system import normalize_angle
from ..runtime import mkdir
from .layer import Layer


##########################################################################
class PlaneFit(object):

    """ Fit a plane to the given list of x,y,z values by least squares
    fitting of the z values. """

    def __init__(self, points, *, params=None):

        """ Run the fitting algorithm and store the results. """

        # Least squares plane fitting
        A = np.array(points, dtype=float)
        b = np.array(A[:,-1])
        A[:,-1] = 1.0
        if params is None:
            params = np.linalg.lstsq(A, b, rcond=None)[0]

        self.params = params

        # Average z deviation
        self.dev = np.dot(A, self.params) - b
        self.avg = np.sqrt(sum(self.dev*self.dev))/len(self.dev)

        # Surface normal vector
        p0 = self.getvec(0, 0)
        p1 = self.getvec(1, 0) - p0
        p2 = self.getvec(0, 1) - p0
        x, y, z = np.cross(p1, p2)

        # Length of y projection and length of vector
        rxy = np.hypot(x, y)
        #r = np.hypot(rxy, z)

        # Plane slope and polar angle
        self.slope = rxy / z
        self.theta = np.arctan2(rxy, z) * 180.0 / np.pi

        # Azimuthal angle in (-180, 180]
        self.phi = normalize_angle(np.arctan2(y, x) * 180.0 / np.pi)

    @cached_property
    def max_dev(self) -> float:
        return np.max(np.abs(self.dev))

    def __str__(self) -> str:

        """ Return result string. """

        s = [
            f"polar angle:    {self.theta:.1f}° ({100 * self.slope:.2f} %)",
            f"azimuth angle:  {self.phi:.1f}°",
            f"mean deviation: {self.avg:.3f} µm (max. {self.max_dev:.3f} µm)"
        ]
        return "\n".join(s)

    def log_results(self, func, name=None):

        """ Pass result string to given logger function line by line.
        Each line eventually preceded by an optional name string. """

        for line in str(self).split("\n"):
            if name is not None:
                line = f"{name} {line}"
            func(line)


    def getz(self, x: float, y: float) -> float:

        """ Return z value of the plane at the given lateral xy
        position. """

        return np.dot(self.params, [x, y, 1])


    def getvec(self, x: float, y: float) -> np.ndarray:

        """ Return xyz vector with z value of the plane at the given
        lateral xy position. """

        z = self.getz(x, y)
        return np.asarray([x, y, z], dtype=float)


##########################################################################
class zPlane(object):

    def __init__(self, plane, key):

        """ Store plane parameters. """

        params = plane["meas/result.json"][key]
        sx = params["xSlope"]
        sy = params["ySlope"]
        z0 = params["z0"]
        self.params = np.asarray([sx, sy, z0], dtype=float)


    def getz(self, x, y):

        """ Return z value of the plane at the given lateral xy
        position. """

        return np.dot(self.params, [x, y, 1])


##########################################################################
class Plane(Parameter):

    """ Layer plane class. """

    _defaults = {
        }

    def __init__(self, z_low, z_high, system, logger=None, **kwargs):

        """ Initialize the layer scan object. """

        # Store system object
        self.system = system
        user = self.system.user["key"]

        # Initialize parameter class
        args = popargs(kwargs, "plane")
        super().__init__(user, logger, **args)
        self.log.info("Initializing plane detector.")

        # Initialize layer object
        args = popargs(kwargs, ("layer", "focus"))
        self.layer = Layer(system, logger, **args)

        # Store initial values
        self.z_low = z_low
        self.z_high = z_high

        # No results yet
        self.steps = []
        self.log.info("Initialized plane detector.")


    def run(self, x, y, path=None, home=False):

        pos = len(self.steps)
        path = mkdir(f"{path}/layer", clean=False)
        path = mkdir(f"{path}/layer-{pos:02d}")

        # Store current xyz position
        x0, y0, z0 = self.system.position("XYZ")

        # Detect layer interfaces
        coarse = len(self.steps) == 0
        self.layer.run(x, y, self.z_low, self.z_high, coarse, None, path, home=False)
        layer_dc = self.layer.container()
        layer_dc.write(f"{path}/layer.zdc")
        result = layer_dc["meas/result.json"]

        # Results of this step
        step = {
            "scan": pos,
            "x": x,
            "y": y,
            "layerUuid": layer_dc.uuid,
            }

        # Add results for low interface
        if self.z_low is not None:
            step.update({
                "zLowInit": self.z_low,
                "zLow": result["low"]["z"],
                "dzLow": result["low"]["dz"],
            })
            self.z_low = result["low"]["z"]

        # Add results for high interface
        if self.z_high is not None:
            step.update({
                "zHighInit": self.z_high,
                "zHigh": result["high"]["z"],
                "dzHigh": result["high"]["dz"],
            })
            self.z_high = result["high"]["z"]

        # Append all results to the steps list
        self.steps.append(step)

        # Move stages back to initial position
        if home:
            delay = self.system["delay"]
            self.system.moveabs(wait=delay, x=x0, y=y0, z=z0)


    def _pop_results(self):

        steps = list(self.steps)
        result = {}

        for z, key, name in [
            (self.z_low, "zLow", "Low"),
            (self.z_high, "zHigh", "High")
        ]:
            if z is None:
                continue

            points = [[s["x"], s["y"], s[key]] for s in steps]
            points = np.array(points, dtype=float)
            plane = PlaneFit(points)
            plane.log_results(self.log.info, name)

            result[name.lower()] = {
                "xSlope": plane.params[0],
                "ySlope": plane.params[1],
                "z0": plane.params[2],
                "avgDeviation": plane.avg,
                "maxDeviation": plane.max_dev,
                "gradient": plane.slope,
                "polarAngle": plane.theta,
                "azimuthAngle": plane.phi,
                "points": points.tolist(),
                }

        self.steps = []
        return result, steps

    def container(self, config=None, **kwargs):

        """ Return results as SciDataContainer. """

        # Collect results
        if len(self.steps) == 0:
            raise RuntimeError("No results!")
        result, steps = self._pop_results()

        # Collect UUIDs of focus detections as references
        refs = {}
        for step in steps:
            key = f"scan-{step['scan']:02d}"
            refs[key] = step["layerUuid"]

        # General metadata
        content = {
            "containerType": {"name": "LayerPlane", "version": 1.1},
            }
        meta = {
            "title": "Plane Detection Data",
            "description": "Detection of upper and lower photoresin interface planes.",
            }

        # Container dictionary
        items = self.system.items() | {
            "content.json": content,
            "meta.json": meta,
            "references.json": refs,
            "data/plane.json": self.parameters(),
            "meas/steps.json": steps,
            "meas/result.json": result,
            }

        # Return container object
        config = config or self.config
        return Container(items=items, config=config, **kwargs)
