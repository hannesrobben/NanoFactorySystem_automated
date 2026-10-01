##########################################################################
# Copyright (c) 2024 Reinhard Caspary                                    #
# <reinhard.caspary@phoenixd.uni-hannover.de>                            #
# This program is free software under the terms of the MIT license.      #
##########################################################################
#
# This module provides the function motorScan, which performs an optical
# path length (OPL) scan on the digital holographic microscope of
# LyncéeTec in order to balance the lengths of the object and reference
# beams.
#
##########################################################################

import bisect
import logging

import numpy as np
# from offaxisholo.reconstruct import locateOrder

class Contrast(object):

    def __init__(self):

        self.position = []
        self.values = []

    def __len__(self):

        return len(self.position)

    def __iter__(self):

        return self.values.__iter__()

    def __getitem__(self, pos):

        try:
            i = self.position.index(pos)
        except ValueError:
            return
        return self.values[i]

    def add(self, pos, value):

        """ Add motor position and contrast to the list of datapoints. """

        if pos in self.position:
            i = self.position.index(pos)
            self.position[i] = value
        else:
            i = bisect.bisect_left(self.position, pos)
            self.position.insert(i, pos)
            self.values.insert(i, value)

    @property
    def imax(self):

        return np.argmax(self.values)

    @property
    def minPos(self):

        if len(self) == 0:
            return None
        return self.position[0]

    @property
    def maxPos(self):

        if len(self) == 0:
            return None
        return self.position[-1]

    @property
    def nextPos(self):

        imax = self.imax
        if imax <= 0:
            return -1
        elif imax >= len(self) - 1:
            return 1
        return 0

    @property
    def hasTriple(self):

        return self.nextPos == 0

    @property
    def triple(self):

        if not self.hasTriple:
            raise RuntimeError("No triple!")
        imax = self.imax
        return self.position[imax - 1:imax + 2]

    @property
    def tripleValues(self):

        if not self.hasTriple:
            raise RuntimeError("No triple!")
        imax = self.imax
        return self.values[imax - 1:imax + 2]

    def tripleThreshold(self, thresh):

        return self.hasTriple and min(self.tripleValues) > thresh

    def maxThreshold(self, thresh):

        return max(self) > thresh


def moveMotor(dhm, m, opt=False):
    """ ... """

    # Move the OPL motor
    #dhm.log.info(f"Motorpos: {m:.1f}")
    dhm.device.MotorPos = m

    # Grab camera image
    imgs = []
    k = 5
    for i in range(k):
        img = dhm.getimage(opt=False)[0]
        imgs.append(img)

    vlo, vhi = np.quantile(np.stack(imgs), [0.05, 0.95], method="nearest")
    c = float(vhi - vlo) / 255
    return c

    # img = dhm.getimage(opt)[0]
    # if opt:
    #     dhm.device.CameraShutter = dhm.device.CameraShutter - 2
    #
    # # Return weight of diffraction order peak
    # return locateOrder(img)[-1]


def addMotor(dhm, data, m, opt=False, logger=None):
    """ Move the OPL motor to the given position, take a camera image and
    return its contrast and the weight of its first diffraction order peak. """

    # Prepare logger
    logger = logger or logging

    # Minimum and maximum motor position
    minpos = dhm.device.MotorMinPos
    maxpos = dhm.device.MotorMaxPos
    if m < minpos or m > maxpos:
        return

    value = data[m]
    if value is not None:
        return

    w = moveMotor(dhm, m, opt)
    data.add(m, w)

    logger.debug(f"Motor scan {len(data):02d}: {m:.1f} µm - {100 * w:.1f}%")


def shortScan(dhm, steps=11, dm=250.0, thresh=0.05, m0=None, opt=True,
              logger=None):
    # Minimum and maximum motor position
    minpos = dhm.device.MotorMinPos
    maxpos = dhm.device.MotorMaxPos

    # Center point of the scan
    if m0 is None:
        m0 = dhm.device.MotorPos
    else:
        m0 = float(m0)

    # Determine coarse scan range
    m1 = m0 - dm * (steps - 1) / 2
    if m1 < minpos:
        m1 = minpos
    m2 = m0 + dm * (steps - 1) / 2
    #m2 = m1 + (steps - 1) * dm
    if m2 > maxpos:
        m2 = maxpos
        #m1 = m2 - (steps - 1) * dm

        # Sanity check: That should never happen.
        #if m1 < minpos:
        #    raise RuntimeError("OPL scan range too small!")
    #dhm.log.info(f"MinPos: {minpos:.1f}")
    #dhm.log.info(f"MaxPos: {maxpos:.1f}")
    return runScan(dhm, m1, m2, dm, thresh, opt, logger)


def longScan(dhm, dm=250.0, thresh=0.05, opt=True, logger=None):
    # Minimum and maximum motor position
    m1 = dhm.device.MotorMinPos
    m2 = dhm.device.MotorMaxPos

    return runScan(dhm, m1, m2, dm, thresh, opt, logger)


def runScan(dhm, m1, m2, dm=250.0, thresh=0.05, opt=True, logger=None):
    # Prepare logger
    logger = logger or logging

    # Minimum and maximum motor position
    minpos = dhm.device.MotorMinPos
    maxpos = dhm.device.MotorMaxPos

    # Perform scan
    data = Contrast()
    i = 0
    while True:

        # Get weight of diffraction peak at current position
        m = min(m2, m1 + i * dm)

        if data:
            opt = False
        addMotor(dhm, data, m, opt, logger=logger)

        if data[m] is None:
            print(data.position)
            print(m)
        if data[m] > thresh:
            addMotor(dhm, data, m - 0.7 * dm, logger=logger)
            addMotor(dhm, data, m - 0.3 * dm, logger=logger)
            addMotor(dhm, data, m + 0.3 * dm, logger=logger)
            addMotor(dhm, data, m + 0.7 * dm, logger=logger)

        # Stop if a increased diffraction peak indicates interference
        # if data.tripleThreshold(thresh):
        #    break

        if m == m2:
            break
        i += 1

    # No interference detected
    if not data.maxThreshold(thresh):
        return

    # Make sure that there is at least one data point below the
    # maximum contrast point
    while data.nextPos < 0:
        m = max(minpos, data.minPos - dm)
        if m >= data.minPos:
            return
        addMotor(dhm, data, m, logger=logger)

    # Make sure that there is at least one data point above the
    # maximum contrast point
    while data.nextPos > 0:
        m = min(maxpos, data.maxPos + dm)
        if m >= data.maxPos:
            return
        addMotor(dhm, data, m, logger=logger)

    # Return motor position with maximum contrast and its two neighbors
    logger.debug(f"Scan result: {data.triple[1]:.1f} µm - {max(data):.1f}%")
    return data.triple


def bisectMax(dhm, triple, minc=0.005, minm=5.0, opt=True, logger=None):
    # Prepare logger
    logger = logger or logging

    # Determine image contrast at the initial motor positions.
    # Eventually optimize the exposure time at the center position.
    m0, m1, m2 = triple
    c1 = moveMotor(dhm, m1, opt)
    c0 = moveMotor(dhm, m0)
    c2 = moveMotor(dhm, m2)
    count = 0
    logger.debug(
        f"Bisect {count:02d}: {m0:.1f} µm - {100 * c0:.1f}%  ==  {m1:.1f} µm - {100 * c1:.1f}%  ==  {m2:.1f} µm {100 * c2:.1f}%")

    # Center point must have maximum contrast
    if c0 > c1 or c2 > c1:
        raise MotorScanError("No contrast maximum!")

    # Bisectioning algorithm to find the motor position with maximum
    # image contrast. Proceed until either the difference of the
    # contrast or the difference of the positions falls below the given
    # limits.
    while max(abs(c1 - c0), abs(c1 - c2)) > minc and m2 - m0 > minm:
        count += 1

        if m1 - m0 > m2 - m1:
            m = (m0 + m1) / 2
            c = moveMotor(dhm, m)
            # print(f"lo: {m:.1f} {c:.2f}")
            if (c1 - c) < 0:
                m2, c2 = m1, c1
                m1, c1 = m, c
            else:
                m0, c0 = m, c
        else:
            m = (m1 + m2) / 2
            c = moveMotor(dhm, m)
            # print(f"hi: {m:.1f} {c:.2f}")
            if (c - c1) > 0:
                m0, c0 = m1, c1
                m1, c1 = m, c
            else:
                m2, c2 = m, c

        logger.debug(
            f"Bisect {count:02d}: {m0:.1f} µm - "
            f"{100 * c0:.1f}%  ==  {m1:.1f} µm - "
            f"{100 * c1:.1f}%  ==  {m2:.1f} µm {100 * c2:.1f}%"
        )

    # Return the center of the final range
    m = (m0 + m2) / 2
    logger.debug(f"Bisect result: {m:.1f} µm")
    return m


def motorScan(
        dhm,
        mode="both",
        steps=11,
        dm=250.0,
        thresh=0.05,
        init=None,
        minc=0.005,
        minm=5.0,
        opt=True,
        logger=None
):
    mode = mode.lower()
    if mode not in ("short", "long", "both"):
        raise RuntimeError("Unknown OPL scan mode!")

    result = None
    if mode in ("short", "both"):
        if init is None:
            init = dhm.device.MotorPos
        else:
            init = float(init)
        result = shortScan(dhm, steps=steps, dm=dm, thresh=thresh,
                           m0=init, opt=opt, logger=logger)
    else:
        init = None
    if result is None and mode == "short":
        raise RuntimeError("Short OPL scan detected no interference!")
    if result is None:
        result = longScan(dhm, dm=dm, thresh=thresh, opt=opt, logger=logger)
    if result is None:
        raise RuntimeError("Long OPL scan detected no interference!")

    m = bisectAroundMax(dhm, result, minc, minm, opt, logger=logger)
    dhm.device.MotorPos = m
    return m, init


def bisectAroundMax(dhm, triple, minc=0.005, minm=5.0, opt=True, widening=(1, 2, 4, 8), logger=None):

    """ Find the contrast maximum in the bracket ``triple`` = (m0, m1, m2).

    If the bisection finds no maximum, the bracket around m1 is widened by
    the next factor of ``widening`` and the bisection is repeated, as long as
    the bracket stays inside the motor range (MotorMinPos, MotorMaxPos).

    Raises
    ------
    MotorScanError
        If the widened bracket leaves the motor range or no factor gives a
        maximum.
    """

    m0, m1, m2 = triple
    dm0 = m1 - m0
    dm2 = m2 - m1
    min_pos = float(dhm.device.MotorMinPos)
    max_pos = float(dhm.device.MotorMaxPos)
    for factor in widening:
        bracket = (m1 - factor * dm0, m1, m1 + factor * dm2)
        if bracket[0] < min_pos or bracket[2] > max_pos:
            raise MotorScanError(f"OPL scan bracket {bracket[0]:.1f} - {bracket[2]:.1f} um exceeds the motor range "
                                 f"{min_pos:.1f} - {max_pos:.1f} um")
        try:
            return bisectMax(dhm, bracket, minc, minm, opt, logger=logger)
        except MotorScanError:
            if logger is not None:
                logger.info(f"No contrast maximum in {bracket[0]:.1f} - {bracket[2]:.1f} um; widening the bracket")
    raise MotorScanError(f"No contrast maximum within {widening[-1]} times the initial bracket around {m1:.1f} um")


class MotorScanError(Exception):

    """ The OPL motor scan found no contrast maximum inside the motor range. """