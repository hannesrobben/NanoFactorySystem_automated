##########################################################################
# Copyright (c) 2024 Reinhard Caspary                                    #
# <reinhard.caspary@phoenixd.uni-hannover.de>                            #
# This program is free software under the terms of the MIT license.      #
##########################################################################
#
# The class Scanner which is used for a coarse detection of one or both
# interfaces of the photoresin layer on a sample substrate in the Laser
# Nanofactory system.
#
##########################################################################

import logging
import random

from ..devices.coordinate_system import DropDirection
from ..parameter import Interface, Result
from .ranges import Range, RangeSet

class Scanner:

    """ Coarse photo resin layer scanner class. This iterator class will deliver parameter
    tuples z,dz for external laser scan and focus detection. The result (hit, miss, or ambiguous)
    of each focus detection must be registered using the method register(). The detection starts
    at a given initial z position and expands to both directions, until a focus will be detected.
    Then the total scan range will be exceeded until an undisputed no-focus range (no overlap
    with focus range) of given size is detected beside each requested interface (low, and/or high). """

    def __init__(self, z0, dz, zmin, zmax, drop_direction, interface, stretch, overlap, jitter, logger=None):

        """ Initialize a Scanner object.

        ``drop_direction`` decides which of two focus ranges is the resin layer
        (see :class:`DropDirection`): for DOWN the lowest range is kept and a
        second range above it (e.g. the interface to the immersion oil) is
        ignored; for UP the highest range is kept and a second range below it
        is ignored.
        """

        # Store logger
        self.log = logger or logging

        # Initial scanning parameters and scan range limits
        self.z0 = float(z0)
        self.dz = abs(float(dz))
        self.zmin = float(zmin)
        self.zmax = float(zmax)
        assert (self.zmin < self.zmax)
        assert (self.z0 > self.zmin and self.z0 < self.zmax)
        assert (self.dz < self.zmax - self.zmin)

        # Drop direction: decides which focus range is the resin layer
        assert (isinstance(drop_direction, DropDirection))
        self.drop_direction = drop_direction

        # Resin layer interfaces to be detected (low and/or high)
        assert (isinstance(interface, Interface))
        self.interface = interface

        # Minimum size of undisputed no-focus ranges (no overlap with focus range)
        stretch = abs(float(stretch))
        assert (stretch >= 1.0)
        self.minsize = stretch * self.dz

        # Overlapping factor for scanning adjacent ranges
        overlap = abs(float(overlap))
        assert (overlap >= 0 and overlap < 1.0)
        self.overlap = overlap * self.dz

        # Jitter factor for scanning positions relative to overlap
        jitter = abs(float(jitter))
        assert (jitter >= 0 and jitter < 1.0)
        self.jitter = jitter * self.overlap

        # Initialize ranges of focus detection. Will never contain more than one range.
        self.hit = RangeSet()

        # Initialize ranges of no focus detection. Will contain up to two ranges.
        self.miss = RangeSet()

    def clip(self, z):

        """ Clip given position to a value in the range [self.zmin, self.zmax]. """

        assert (self.zmax > self.zmin)
        z = float(z)
        z = min(self.zmax, z)
        z = max(self.zmin, z)
        return z

    def __iter__(self):

        """ Return iterator object. """

        return self

    def __next__(self):

        """ Yield next scan parameters until all requested interfaces have been detected or the
        scan range limits have been reached. """

        # Interface detection succeeded
        if self.finished:
            raise StopIteration

        # Random jitter
        jitter = random.uniform(-0.5, 0.5) * self.jitter

        # Initial scan parameters
        if len(self.hit | self.miss) == 0:
            z_low = self.clip(self.z0 + jitter - 0.5 * self.dz)
            z_high = self.clip(self.z0 + jitter + 0.5 * self.dz)

        # Next scan parameters
        else:
            # No further scan space left
            full = self.miss | self.hit
            if full.max >= self.zmax and full.min <= self.zmin:
                raise StopIteration

            # Increase scan range alternating at both ends until a focus spot is detected
            if len(self.hit) == 0:
                edge = (Interface.LOW, Interface.HIGH)[len(self.miss) % 2]
            # Proceed with lower interface detection
            elif Interface.LOW in self.interface and not self.low_detected:
                edge = Interface.LOW
            # Finally detect the higher interface.
            else:
                edge = Interface.HIGH

            # Increase scan range at the respective lower or higher end
            if edge == Interface.LOW:
                z_low = self.clip(full.min + jitter + self.overlap - self.dz)
                z_high = self.clip(full.min + jitter + self.overlap)
            else:
                z_low = self.clip(full.max + jitter - self.overlap)
                z_high = self.clip(full.max + jitter - self.overlap + self.dz)

        # Yield the next scan parameters
        z = 0.5 * (z_high + z_low)
        dz = z_high - z_low
        if dz <= 0.0:
            raise StopIteration
        return z, dz

    def register(self, z, dz, result):

        """ Register focus scan result for given scan parameters. """

        # Store center point scan size and focus detection result
        z = float(z)
        dz = abs(float(dz))
        assert (isinstance(result, Result))

        # Merge result into either self.miss or self.hit. Ambiguous results are discarded.
        range_item = Range((z - 0.5 * dz, z + 0.5 * dz))
        if result == Result.MISS:
            self.miss.add(range_item)
        elif result == Result.HIT:
            self.hit.add(range_item)
        else:
            return

        # Skip a second layer by adjusting zmin and zmax. Drop facing down: the resin layer is the
        # lowest range, a range above it is e.g. the substrate/immersion-oil interface. Drop facing
        # up: the interface with the higher z is decisive, so a range below is removed.
        if len(self.hit) > 1:
            assert (len(self.hit) == 2)
            if self.drop_direction == DropDirection.DOWN:
                self.zmax = self.hit.highest.low
                self.hit = RangeSet(self.hit.lowest)
                self.log.info(f"Remove second layer above {self.zmax}")
            else:
                self.zmin = self.hit.lowest.high
                self.hit = RangeSet(self.hit.highest)
                self.log.info(f"Remove second layer below {self.zmin}")
            assert (self.zmax > self.zmin)

        # Runtime sanity checks
        assert (len(self.miss) <= 2)
        assert (len(self.hit) <= 1)
        assert (len(self.hit | self.miss) <= 1)

    def status(self):

        """ Return human-readable status string. """

        # No focus detected
        if len(self.hit) == 0:

            # No result yet
            if len(self.miss) == 0:
                status = "..."

            # Size of no-focus range
            else:
                status = f"... {self.miss.size:.1f} ..."

        # Focus detected
        else:

            # No-focus ranges missing yet
            if len(self.miss) == 0:
                status = f"... / {self.hit.size:.1f} \\ ..."

            # No-focus ranges on both sides
            elif len(self.miss) > 1:
                v = [ self.hit.min - self.miss.min,
                      self.miss.lowest.high - self.hit.min,
                      self.miss.highest.low - self.miss.lowest.high,
                      self.hit.max - self.miss.highest.low,
                      self.miss.max - self.hit.max]
                status = f"{v[0]:.1f} / {v[1]:.1f} / {v[2]:.1f} \\ {v[3]:.1f} \\ {v[4]:.1f}"

            # No-focus range on lower end
            elif self.miss.min < self.hit.min:
                v = [ self.hit.min - self.miss.min,
                      self.miss.max - self.hit.min,
                      self.hit.max - self.miss.max]
                status = f"{v[0]:.1f} / {v[1]:.1f} / {v[2]:.1f} ..."

            # No-focus range on higher end
            else:
                v = [ self.miss.min - self.hit.min,
                      self.hit.max - self.miss.min,
                      self.miss.max - self.hit.max]
                status = f"... / {v[0]:.1f} \\ {v[1]:.1f} \\ {v[2]:.1f}"

        # Return status string
        return status

    def __str__(self):

        """ Return human-readable object representation. """

        return self.status()

    @property
    def low_detected(self):

        """ Return True, if the lower interface was detected successfully. """

        # No scan results yet
        if len(self.hit) == 0 or len(self.miss) == 0:
            return False

        # Get hit range and lower miss range
        hit_range = self.hit.range
        if len(self.miss) == 1:
            miss_range = self.miss.range
        else:
            miss_range = self.miss.lowest

        # Return True, if lower interface position was detected
        return hit_range.low - miss_range.low >= self.minsize or miss_range.low <= self.zmin

    @property
    def low_edge(self):

        """ Return scan parameters, which contain the lower layer interface. """

        assert (self.low_detected)

        z_low = self.clip(self.miss.lowest.high - 0.5 * self.overlap)
        z_high = self.clip(self.miss.lowest.high - 0.5 * self.overlap + self.dz)
        z = 0.5 * (z_high + z_low)
        dz = z_high - z_low
        return z, dz

    @property
    def high_detected(self):

        """ Return True, if the higher interface was detected successfully. """

        # No scan results yet
        if len(self.hit) == 0 or len(self.miss) == 0:
            return False

        # Get hit range and higher miss range
        hit_range = self.hit.range
        if len(self.miss) == 1:
            miss_range = self.miss.range
        else:
            miss_range = self.miss.highest

        # Return True, if higher interface position was detected
        return miss_range.high - hit_range.high >= self.minsize or miss_range.low >= self.zmax

    @property
    def high_edge(self):

        """ Return scan parameters, which contain the higher layer interface. """

        assert (self.high_detected)

        z_low = self.clip(self.miss.highest.low + 0.5 * self.overlap - self.dz)
        z_high = self.clip(self.miss.highest.low + 0.5 * self.overlap)
        z = 0.5 * (z_high + z_low)
        dz = z_high - z_low
        return z, dz

    @property
    def finished(self):

        """ True, if all requested interfaces have been detected. """

        # Lower interface requested, but not yet detected
        if Interface.LOW in self.interface and not self.low_detected:
            return False

        # Higher interface requested, but not yet detected
        if Interface.HIGH in self.interface and not self.high_detected:
            return False

        # All requested interfaces detected
        return True

    def result(self):

        """ Return the detection result dictionary. """

        assert (self.finished)

        result = {
            "zStart": self.z0,
            "dz": self.dz,
            "zMin": self.zmin,
            "zMax": self.zmax,
            "dropDirection": self.drop_direction.name,
            "interface": self.interface.name.lower(),
            "minSize": self.minsize,
            "overlap": self.overlap,
            "jitter": self.jitter,
        }

        if self.low_detected:
            result["zLowApproximate"], result["dzLowApproximate"] = self.low_edge
        if self.high_detected:
            result["zHighApproximate"], result["dzHighApproximate"] = self.high_edge

        return result
