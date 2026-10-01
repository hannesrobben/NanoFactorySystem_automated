import math
from abc import ABC
from enum import Enum
from typing import Optional, Literal, Iterator

import numpy as np
import qrcode

from nanofactorysystem.aerobasic import GalvoLaserOverrideMode, SingleAxis
from nanofactorysystem.aerobasic.programs.drawings import DrawableAeroBasicProgram, DrawableObject
from nanofactorysystem.aerobasic.programs.drawings.lines import Rectangle3D, step_slice_size
from nanofactorysystem.devices.coordinate_system import CoordinateSystem, Coordinate, Point3D, Point2D


def z_line_copy(self, x, y, z, dz, power, speed, duration):
    """ Exposed an axial line or point (dz=0) at given position. """

    # Fast positioning speed
    fast = self.system["speed"]

    # Delay time after stages reached their destination
    delay = self.system["delay"]
    # Move to center position
    self.system.moveabs(fast, delay, x=x, y=y, z=z + self["zCameraOffset"])

    # Take pre exposure camera image
    img0 = self.system.getimage()
    self.system.moveabs(fast, delay, z=z)

    # Expose axial line
    if dz != 0.0:
        v = min(speed, dz / duration)
        dt = dz / v
        self.system.zline(power, fast, v, dz)
        self.system.wait("XYZ", delay)

    # Expose a dot
    else:
        v = 0.0
        dz = 0.0
        dt = duration
        self.system.pulse(power, dt)

    # Take post exposure camera image
    self.system.moveabs(fast, delay, z=z + self["zCameraOffset"])
    img1 = self.system.getimage()
    # self.system.moveabs(fast, delay, x=x, y=y, z=z)

    # Exposure data
    exposure = {
        "x": x,
        "y": y,
        "zCenter": z,
        "zLength": dz,
        "laserPower": power,
        "fastSpeed": fast,
        "destinationDelay": delay,
        "setSpeed": speed,
        "setDuration": duration,
        "speed": v,
        "duration": dt,
    }

    # Done.
    return img0, img1, exposure


class Stair(DrawableObject):
    def __init__(
            self,
            center: Point3D,
            n_lines: int,
            minimal_distance: float,
            x_dimension: float,
            y_dimension: float,
            socket_height: float = 0.0,
            *,
            velocity: float,
            acceleration: float
    ):
        super().__init__()
        self.center = center
        self.n_lines = n_lines
        self.min_distance = minimal_distance
        self.x_dim = x_dimension
        self.y_dim = y_dimension
        # self.socket_height = socket_height

        self.velocity = velocity
        self.acceleration = acceleration

        self.point_list = []  # used for saving x- and y-dimension of each z-line point

    @property
    def center_point(self) -> Point2D:
        return self.center

    def iterate_layers(self, coordinate_system: CoordinateSystem) -> Iterator[DrawableAeroBasicProgram]:
        program = DrawableAeroBasicProgram(coordinate_system)
        # Add socket
        if self.socket_height > 0:
            socket = Rectangle3D(
                center=self.center,
                width=self.structure_width,
                length=self.structure_length,
                height=self.socket_height,
                hatch_size=self.hatch_size,
                slice_size=self.slice_size,
                velocity=self.velocity,
                acceleration=self.acceleration
            )
            yield from socket.iterate_layers(coordinate_system)

        # Add steps
        slice_size_opt = step_slice_size(self.step_height, self.slice_size)
        for step in range(self.n_steps):
            z_step_offset = self.socket_height + step * self.step_height
            x_offset = (step / 2) * self.step_length

            step_rectangle = Rectangle3D(
                center=self.center + Point3D(0, -x_offset, z_step_offset),
                width=self.structure_width,
                length=self.structure_length - step * self.step_length,
                height=self.step_height,
                hatch_size=self.hatch_size,
                slice_size=slice_size_opt,
                velocity=self.velocity,
                acceleration=self.acceleration
            )

            yield from step_rectangle.iterate_layers(coordinate_system)

        return program

    # generate a x-y list for possible points
    # validate if points are minimum of min_dist away from each other
    # speed and power have to be given

    # not possible as a program - because of capturing image? Maybe direct control of the system
    # --- program ---
    # move to x y z
    # take image (before)
    # laser on
    # move dz down/ up
    # laser off
    # take image (after)



