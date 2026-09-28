##########################################################################
# Copyright (c) 2022-2024 Reinhard Caspary                               #
# <reinhard.caspary@phoenixd.uni-hannover.de>                            #
# This program is free software under the terms of the MIT license.      #
##########################################################################
#
# This module provides access to the the ASCII command interface of the
# AeroTech A3200 system.
#
# Note:
# Enable the ASCII command interface in the A3200 Configuration Manager:
#     Computer - Open Files - * - System - Communication - ASCII
# You must reset the controller for changes to become effective.
#
##########################################################################

import os
import socket
import time
from enum import Enum
from typing import Any, Optional

from scidatacontainer import Container

from .attenuator import Attenuator
from ..config import sysConfig, popargs
from ..parameter import Parameter

# Task states
TASKSTATE_Unavailable = 0
TASKSTATE_Inactive = 1
TASKSTATE_Idle = 2
TASKSTATE_ProgramReady = 3
TASKSTATE_ProgramRunning = 4
TASKSTATE_ProgramFeedheld = 5
TASKSTATE_ProgramPaused = 6
TASKSTATE_ProgramComplete = 7
TASKSTATE_Error = 8
TASKSTATE_Queue = 9
TASKSTATE = ("unavailable", "inactive", "idle", "programReady",
             "programRunning", "programFeedheld", "programPaused",
             "programComplete", "error", "queue")


class TaskState(Enum):
    unavailable = 0
    inactive = 1
    idle = 2
    program_ready = 3
    program_running = 4
    programmfeed_held = 5
    program_paused = 6
    program_complete = 7
    error = 8
    queue = 9


# Drive status bit masks
DRIVESTATUS_InPosition = 0x02000000

# AeroBasic program doing an aial line scan
ZLINE_PGM = """
DVAR $dz
DVAR $dzhalf
DVAR $fast
DVAR $slow

$fast = $global[0]
$slow = $global[1]
$dz = $global[2]
$dzhalf = -0.5 * $dz

LOOKAHEAD FAST
CRITICAL START
VELOCITY ON
RAMP MODE RATE
RAMP RATE 0.00000
WAIT MODE AUTO
INCREMENTAL

LINEAR Z $dzhalf F $fast
GALVO LASEROVERRIDE A ON
LINEAR Z $dz F $slow
GALVO LASEROVERRIDE A OFF
LINEAR Z $dzhalf F $fast

ABSOLUTE
VELOCITY ON
CRITICAL END
END PROGRAM
"""


##########################################################################
class A3200(Parameter):
    """ Class for controlling an Aerotech A3200 system."""

    _defaults = sysConfig.controller | {
        "xInit": None,
        "yInit": None,
        "zInit": None,
        "zMax": None,
        "tasks": {},
        "softwareVersion": None,
    }

    def __init__(self, user, logger=None, **kwargs):

        # Initialize parameter class
        args = popargs(kwargs, "controller")
        super().__init__(user, logger, **args)
        self.log.info("Initializing Aerotech A3200 system.")

        # Safety net: maximum z position
        if self["zMax"] is None:
            raise RuntimeError("Maximum z position is missing!")

        # TCP socket to the A3200 system
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.opened = False

        # Connect to the A3200 system
        try:
            self.socket.connect((self["host"], self["port"]))
        except ConnectionRefusedError:
            self.log.error("Connection to A3200 controller failed!")
            return
        self.opened = True

        # Acknowledge all warnings
        self.reset()

        # Some standard definitions
        # self.run("ABSOLUTE")
        # self.run("METRIC")
        # self.run("SECONDS")
        # self.run("VELOCITY OFF")
        # self.run("IFOV OFF")

        # Store software version
        self["softwareVersion"] = self.version()

        # Store current xyz position
        self["xInit"], self["yInit"], self["zInit"] = self.position("XYZ")

        # No program tasks loaded yet
        self.task_pgms = {}

        # Laser calibration
        args = popargs(kwargs, "attenuator")
        self.attenuator = Attenuator(user, self.log, **args)

        # Done
        self.log.info(str(self))
        self.log.info("Initialized Aerotech A3200 system.")

    def __str__(self):

        if self.opened:
            result = f"{self['manufacturer']} {self['model']} (driver {self['softwareVersion']}) at {self['host']}:{self['port']}."
        else:
            result = "Aerotech A3200 disconnected."
        return result

    def __enter__(self):

        """ Context manager entry method. """

        return self

    def __exit__(self, errtype, value, tb):

        """ Context manager exit method. """

        # print("".join(traceback.format_exception(errtype, value, tb)))
        self.close()

    def close(self):

        """ Close connection to the A3200 system. """

        self.socket.close()
        self.opened = False

    def run(self, cmd: str) -> str:

        """ Run the given AeroBasic command on the A3200 controller. """

        if not self.opened:
            raise RuntimeError("Not connected!")

        # Append terminal character
        if cmd[-1] != chr(self["cmdTerminatingChar"]):
            cmd += chr(self["cmdTerminatingChar"])

        # Send command
        self.socket.send(cmd.encode())

        # Read and return response
        line = self.socket.recv(4096).decode().strip()
        code, response = line[0], line[1:]
        if code != chr(self["cmdSuccessChar"]):
            self.socket.send("~LASTERROR".encode())
            line = self.socket.recv(4096).decode().strip()
            raise RuntimeError(f"Command failed! {code}, {response} -> {line}")
        return response

    def version(self) -> str:

        """ Return A3200 software version. """

        return self.run("~VERSION")

    def reset(self):

        """ Acknowledge all warnings. """

        if not self.opened:
            raise RuntimeError("Not connected!")

        self.run("ACKNOWLEDGEALL")

    def home(self, axes=None):

        """ Run a home cycle on the given axes. """

        if axes in None:
            axes = "XYZ"
        axes = self.normaxes(axes, "XYZ")
        for axis in axes:
            self.run(f"HOME {axis}")

    def normaxes(self, axes, limit=None):

        """ Return normalized string of uppercase axis letters. The
        parameter limit may contain a string of allowed axis letters.
        Default is "XYZAB". """

        if limit is None:
            limit = "XYZAB"
        else:
            limit = limit.upper()
        false = tuple(c for c in axes if c.upper() not in limit)
        if len(false) > 0:
            false = ", ".join(false)
            raise RuntimeError(f"Wrong axes: {false}!")
        return axes.upper()

    def moveinc(self, speed, **axes):

        """ Move on one or more axes with the given speed in micrometers
        per second. The relative movement distances are given in
        micrometers as named parameters. Example: moveinc(100, x=10.7,
        z=-2.0)"""

        dest = []
        for axis, pos in axes.items():
            axis = self.normaxes(axis, "XYZAB")
            if axis == "Z":
                self.z += pos
                if self.z > self["zMax"]:
                    self.close()
                    raise RuntimeError("Maximum z position exceeded!")
            dest.append(f"{axis}{0.001 * pos:f}")
        dest = " ".join(sorted(dest))
        self.run("INCREMENTAL")
        self.run(f"LINEAR {dest} F{0.001 * speed:f}")

    def moveabs(self, speed, **axes):

        """ Move on one or more axes with the given speed in micrometers
        per second. The absolute positions are given in micrometers as
        named parameters. Example: moveabs(100, x=10327.7, z=2456.5)"""

        dest = []
        for axis, pos in axes.items():
            axis = self.normaxes(axis, "XYZAB")
            if axis == "Z":
                self.z = pos
                if self.z > self["zMax"]:
                    self.close()
                    raise RuntimeError("Maximum z position exceeded!")
            dest.append(f"{axis}{0.001 * pos:f}")
        dest = " ".join(sorted(dest))
        self.run("ABSOLUTE")
        self.run(f"LINEAR {dest} F{0.001 * speed:f}")

    def position(self, axes):

        """ Return current measured positions in micrometers on the
        given axes as a list of floating point numbers. Return a single
        number if a single axis is requested. """

        axes = self.normaxes(axes, "XYZAB")
        cmd = [f"AXISSTATUS({a}, DATAITEM_PositionFeedback)" for a in axes]
        pos = [self.run(c) for c in cmd]
        pos = [1000 * float(p.replace(",", ".")) for p in pos]
        if len(pos) == 1:
            return pos[0]
        return pos

    def speed(self, axes):

        """ Return current measured speed in micrometers per second of
        the given axes as a list of floating point numbers. Return a
        single number if a single axis is requested. """

        axes = self.normaxes(axes, "XYZAB")
        cmd = [f"AXISSTATUS({a}, DATAITEM_VelocityFeedback)" for a in axes]
        speed = [self.run(c) for c in cmd]
        speed = [1000 * float(p.replace(",", ".")) for p in speed]
        if len(speed) == 1:
            return speed[0]
        return speed

    def drivestatus(self, axes, wait=False):

        """ Return True, if all given axes are in position. Wait until
        all given axes are in position if the parameter wait is True.
        """

        axes = self.normaxes(axes, "XYZAB")
        cmd = [f"AXISSTATUS({a}, DATAITEM_DriveStatus)" for a in axes]
        bitmask = DRIVESTATUS_InPosition
        if not wait:
            return all((int(self.run(c)) & bitmask) != 0 for c in cmd)

        while not all((int(self.run(c)) & bitmask) != 0 for c in cmd):
            pass
        return True

    def wait(self, axes, pause: Optional[float] = None):

        """ Wait until all given axes are in position after pause
        milliseconds. """

        if pause is not None:
            time.sleep(0.001 * pause)
        self.drivestatus(axes, True)

    def load(self, task, fn):

        """ Load AeroBasic program from given file and store it as task.
        Valid task numbers range from 1-32. """

        # print(f'PROGRAM {task:d} LOAD "{fn}"')
        self.run(f'PROGRAM {task:d} LOAD "{fn}"')

    def start(self, task):

        """ Start execution of the given task. """

        self.run(f"PROGRAM {task:d} START")

    def stop(self, task_id):

        """ Stop and remove the given task. """

        self.run(f"PROGRAM {task_id:d} STOP")

    def state(self, task_id: int) -> TaskState:

        """ Return status of given task as integer value and as string.
        """

        state_id = int(self.run(f"TASKSTATUS({task_id:d}, DATAITEM_TaskState)"))
        return TaskState(state_id)

    def attenuate(self, att):

        """ Set laser attenuator to given value in the range 0.0..10.0.
        """

        att = float(att)
        if att < 0.0 or att > 10.0:
            raise RuntimeError(f"Not a valid attenuator value: {att:g}!")
        self.run(f"$AO[0].A={att:f}")

    def power(self, power):

        """ Set laser power to given value in milliwatts. """

        att = self.attenuator.ptoa(power)
        self.attenuate(att)

    def laseron(self, power):

        """ Switch laser on with given power. """

        self.power(power)
        self.run("GALVO LASEROVERRIDE A ON")

    def laseroff(self):

        """ Switch laser off. """

        self.run("GALVO LASEROVERRIDE A OFF")

    def pulse(self, power, duration):

        """ Deliver laser pulse with given power in milliwatts and
        duration in seconds. """

        self.laseron(power)
        time.sleep(duration)
        self.laseroff()

    def init_zline(self, fn=None):

        """ Load and compile zline program. """

        # Sanity check
        name = "zline"
        if name in self["tasks"]:
            return

        # Default file name
        if fn is None:
            fn = "__zline__.pgm"

        # First free task number
        tasks = self["tasks"].values()
        if len(tasks) == 0:
            task_id = 1
        else:
            task_id = min(set(range(1, max(tasks) + 2)) - set(tasks))

        # Store AeroBasic program as file
        self["tasks"][name] = task_id
        self.task_pgms[name] = ZLINE_PGM
        with open(fn, "w") as fp:
            fp.write(self.task_pgms[name])

        # Stop any running program 1 
        self.stop(task_id)

        # Load AeroBasic program 1 from file
        path = os.path.join(os.getcwd(), fn)
        self.load(task_id, path)

        # Done
        return task_id

    def zline(self, power, fast, slow, dz):

        """ Run zline program with fast and slow speed in µm/s as well
        as axial distance in µm. Return when the program finished
        successfully and raise a RuntimeError otherwise. """

        # Initialize zline program
        name = "zline"
        if name not in self["tasks"]:
            self.init_zline()

        # Task number        
        task = self["tasks"][name]

        # Store task parameters as global variables
        if self.z + 0.5 * dz > self["zMax"]:
            self.close()
            raise RuntimeError("Maximum z position exceeded!")
        self.run(f"$global[0] = {0.001 * fast:f}")
        self.run(f"$global[1] = {0.001 * slow:f}")
        self.run(f"$global[2] = {0.001 * dz:f}")

        # Set laser power
        self.power(power)

        # Run zline program
        self.start(task)
        state = TaskState.program_running
        while state == TaskState.program_running:
            state = self.state(task)

        # Program failure
        if state != TaskState.program_complete:
            self.close()
            raise RuntimeError(f"Task state '{state.name}' ({state.value})!")

    def info(self) -> dict[str, Any]:

        """ Return information dictionary. """

        keys = (
            "zMax",
            "description",
            "model",
            "manufacturer",
            "softwareVersion",
            "host",
            "port"
        )
        return {k: self[k] for k in keys}

    def container(self, config=None, **kwargs):

        """ Return results as SciDataContainer. """

        # General metadata
        content = {
            "containerType": {"name": "MotionControl", "version": 1.1},
        }
        meta = {
            "title": "Motion control system parameters",
            "description": "Parameters of the Aerotech A3200 system.",
        }

        # Create container dictionary
        items = {
            "content.json": content,
            "meta.json": meta,
            "data/controller.json": self.parameters(),
        }

        # Add program files
        for name, task in self["tasks"]:
            item = f"data/{name}.pgm"
            items[item] = self.task_pgms[name]

        # Return container object
        config = config or self.config
        return Container(items=items, config=config, **kwargs)
