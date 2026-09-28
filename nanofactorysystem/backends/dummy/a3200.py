"""Socket-level simulation of the Aerotech A3200 ASCII command interface.

:class:`FakeA3200Transport` behaves like a connected TCP socket: it receives
command lines terminated by ``\\n`` and answers with protocol-correct frames
(``%<data>\\n`` success, ``!\\n`` invalid, ``#\\n`` fault). Both controller
facades (``devices.A3200`` and ``aerobasic.ascii.AerotechAsciiInterface``)
therefore run unchanged on top of it, and the command strings they generate
are recorded in the call log.
"""
from __future__ import annotations

import ast
import operator
import re
from collections import deque
from pathlib import Path
from typing import Any, Callable, Optional, Union

from nanofactorysystem.backends.dummy.world import AXES, SimulatedWorld

SUCCESS = "%"
INVALID = "!"
FAULT = "#"

# TaskState values (see aerobasic.constants.tasks.TaskState)
_IDLE, _READY, _RUNNING, _COMPLETE, _ERROR = 2, 3, 4, 7, 8

# Command prefixes that are accepted without changing the simulated state
_NOOP_PREFIXES = (
    "ACKNOWLEDGEALL", "PRIMARY", "SECONDS", "MINUTES", "METRIC", "ENGLISH", "LOOKAHEAD", "CRITICAL",
    "RAMP", "WAIT MODE", "ENCODER", "GALVO", "IFOV", "APPLYDEFAULTS", "ABORT", "DVAR", "END PROGRAM",
)

_NUMBER = r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?"
_VARIABLE = r"\$\w+(?:\[\d+\])?"
_MOTION_ARG = re.compile(rf"([XYZABF])\s*({_VARIABLE}|{_NUMBER})")

Response = Union[str, Callable[[re.Match, SimulatedWorld], str]]


class _Unhandled(Exception):
    """ Raised for commands the simulation does not know. """


class _Fault(Exception):
    """ Raised for commands that fail on the simulated controller. """


class FakeA3200Transport:
    """ In-process, socket-like simulation of the A3200 ASCII interface.

    Parameters
    ----------
    world : SimulatedWorld
        Shared state of the dummy backend.
    strict : bool
        If True, unknown commands are answered with INVALID (``!``).
        Otherwise they succeed and are listed in :attr:`unhandled`.
    decimal_comma : bool
        Format numbers with a decimal comma, like a controller with German
        locale settings.
    version : str
        Answer to ``~VERSION``.
    acceleration : dict, optional
        Acceleration rate in mm/s² per axis, overriding the defaults.
    refuse_connection : bool
        If True, :meth:`connect` raises ``ConnectionRefusedError``.
    running_polls : int
        Number of ``TaskState`` queries after ``PROGRAM n START`` that are
        answered with ``program_running`` before the final state.

    Attributes
    ----------
    unhandled : list of str
        Commands that were accepted without simulation.
    """

    def __init__(self, world: SimulatedWorld, *, strict: bool = False, decimal_comma: bool = False,
                 version: str = "4.9.0.0", acceleration: Optional[dict[str, float]] = None,
                 refuse_connection: bool = False, running_polls: int = 0):
        self.world = world
        self.strict = strict
        self.decimal_comma = decimal_comma
        self.version = version
        self.acceleration = {"X": 1000.0, "Y": 1000.0, "Z": 100.0, "A": 10000.0, "B": 10000.0}
        self.acceleration.update(acceleration or {})
        self.refuse_connection = refuse_connection
        self.running_polls = int(running_polls)

        self.connected = False
        self.address: Optional[tuple[str, int]] = None
        self.timeout: Optional[float] = None
        self.last_error = ""
        self.current_task = 1
        self.unhandled: list[str] = []

        self._inbuf = ""
        self._outq: deque[str] = deque()
        self._overrides: list[tuple[re.Pattern, Response]] = []
        self._faults: list[list[Any]] = []
        self._program_errors: deque[tuple[int, int, int]] = deque()

    # Socket interface

    def connect(self, address: tuple[str, int]) -> None:
        """ Simulate connecting to the controller. """

        if self.refuse_connection:
            raise ConnectionRefusedError(f"Simulated refusal of {address}")
        self.address = address
        self.connected = True

    def settimeout(self, value: Optional[float]) -> None:
        """ Store the timeout; the simulation never blocks. """

        self.timeout = value

    def send(self, data: bytes) -> int:
        """ Receive bytes from the client and process every complete line.

        Parameters
        ----------
        data : bytes
            Encoded command text.

        Returns
        -------
        int
            Number of bytes accepted.
        """

        self._inbuf += data.decode()
        while "\n" in self._inbuf:
            line, self._inbuf = self._inbuf.split("\n", 1)
            self._process(line)
        return len(data)

    def sendall(self, data: bytes) -> None:
        """ Same as :meth:`send`. """

        self.send(data)

    def recv(self, bufsize: int) -> bytes:
        """ Return the next response frame.

        A command without terminating character (the old ``A3200.run``
        sends ``~LASTERROR`` like this) is processed when its response is
        requested.

        Raises
        ------
        RuntimeError
            If no response is pending. A real socket would block forever.
        """

        if not self._outq and self._inbuf.strip():
            line, self._inbuf = self._inbuf, ""
            self._process(line)
        if not self._outq:
            raise RuntimeError("FakeA3200Transport.recv() called without pending response "
                               "(the real controller connection would block here)")
        return self._outq.popleft().encode()[:bufsize]

    def close(self) -> None:
        """ Simulate closing the connection. """

        self.connected = False

    # Configuration of responses

    def respond(self, pattern: str, response: Response) -> None:
        """ Override the answer to commands matching a regular expression.

        Parameters
        ----------
        pattern : str
            Regular expression searched in the command line.
        response : str or callable
            Data of the success frame, or ``f(match, world) -> str``.
        """

        self._overrides.append((re.compile(pattern), response))

    def fail_next(self, pattern: str, *, code: str = "FAULT", error: str = "Simulated fault", count: int = 1) -> None:
        """ Let the next matching command(s) fail.

        Parameters
        ----------
        pattern : str
            Regular expression searched in the command line.
        code : {"FAULT", "INVALID"}
            Return code of the failure.
        error : str
            Answer to the following ``~LASTERROR``.
        count : int
            Number of matching commands that fail.
        """

        frame = {"FAULT": FAULT, "INVALID": INVALID}[code]
        self._faults.append([re.compile(pattern), frame, error, count])

    def program_error_next(self, error_code: int = 1, error_location: int = 0, *, running_polls: int = 1) -> None:
        """ Let the next started program end in the task state ``error``.

        Parameters
        ----------
        error_code, error_location : int
            Values reported by ``TaskErrorCode`` and ``TaskErrorLocation``.
        running_polls : int
            ``TaskState`` queries answered with ``program_running`` before
            the error. With 0 the task never appears to start.
        """

        self._program_errors.append((error_code, error_location, running_polls))

    # Processing

    def _process(self, line: str) -> None:
        line = line.rstrip("\r")
        code, data = self._respond(line)
        self.world.calllog.record("controller", line, (), code + data, self.world.clock.now)
        self._outq.append(code + data + "\n")

    def _respond(self, line: str) -> tuple[str, str]:
        for fault in self._faults:
            pattern, frame, error, count = fault
            if count > 0 and pattern.search(line):
                fault[3] -= 1
                self.last_error = error
                return frame, ""
        for pattern, response in self._overrides:
            match = pattern.search(line)
            if match:
                return SUCCESS, response(match, self.world) if callable(response) else str(response)
        try:
            return SUCCESS, self.execute(line)
        except _Fault as error:
            self.last_error = str(error)
            return FAULT, ""
        except _Unhandled:
            self.unhandled.append(line)
            if self.strict:
                return INVALID, ""
            return SUCCESS, ""

    def _format(self, value: float) -> str:
        text = f"{value:.6f}"
        return text.replace(".", ",") if self.decimal_comma else text

    def _eval(self, expr: str) -> float:
        """ Evaluate a numeric AeroBasic expression with variables. """

        def substitute(match: re.Match) -> str:
            name = match.group(0)[1:]
            if name not in self.world.variables:
                raise _Unhandled(f"Unknown variable {name}")
            return repr(float(self.world.variables[name]))

        text = re.sub(_VARIABLE, substitute, expr.strip())
        return _safe_eval(text)

    def execute(self, line: str) -> str:
        """ Execute one immediate command or program statement.

        Parameters
        ----------
        line : str
            Command line without terminating character.

        Returns
        -------
        str
            Data of the success response.

        Raises
        ------
        _Unhandled
            If the command is not simulated.
        _Fault
            If the command fails on the simulated controller.
        """

        s = line.strip()
        if not s or s.startswith("'") or s.startswith("//"):
            return ""
        u = s.upper()
        world = self.world

        if u == "~VERSION":
            return self.version
        if u == "~LASTERROR":
            return self.last_error
        if u == "~RESETCONTROLLER":
            return ""
        if m := re.fullmatch(r"~TASK\s+(\d+)", u):
            self.current_task = int(m.group(1))
            return ""
        if m := re.fullmatch(r"~STOPTASK(?:\s+(\d+))?", u):
            world.task(int(m.group(1) or self.current_task)).state = _IDLE
            return ""
        if m := re.fullmatch(r"~STATUS\s*(.*)", s, re.IGNORECASE):
            queries = re.findall(r"\(([^)]*)\)", m.group(1))
            return " ".join(self._status([q.strip() for q in query.split(",")]) for query in queries)
        if m := re.fullmatch(r"AXISSTATUS\(\s*(\w+)\s*,\s*DATAITEM_(\w+)\s*(?:,.*)?\)", s, re.IGNORECASE):
            return self._axis_item(m.group(1).upper(), m.group(2))
        if m := re.fullmatch(r"TASKSTATUS\(\s*(\d+)\s*,\s*DATAITEM_(\w+)\s*(?:,.*)?\)", s, re.IGNORECASE):
            return self._task_item(int(m.group(1)), m.group(2))
        if m := re.fullmatch(r"SYSTEMSTATUS\(\s*DATAITEM_(\w+)\s*(?:,.*)?\)", s, re.IGNORECASE):
            return self._system_item(m.group(1))
        if m := re.fullmatch(r"ERRORDECODE\s+(-?\d+)\s*,\s*(-?\d+)", u):
            return f"Simulated error {m.group(1)} at {m.group(2)}"

        if u == "ABSOLUTE":
            world.absolute = True
            return ""
        if u == "INCREMENTAL":
            world.absolute = False
            return ""
        if m := re.fullmatch(r"(LINEAR|RAPID|G0|G1)\b(.*)", s, re.IGNORECASE):
            target, feed = {}, None
            for axis, token in _MOTION_ARG.findall(m.group(2)):
                value = self._eval(token)
                if axis == "F":
                    feed = value
                else:
                    target[axis] = value
            world.move(target, feed)
            return ""
        if m := re.fullmatch(rf"(MOVEABS|MOVEINC)\s+([XYZAB])\s+({_NUMBER})\s+({_NUMBER})", u):
            world.move({m.group(2): float(m.group(3))}, float(m.group(4)), incremental=m.group(1) == "MOVEINC")
            return ""
        if m := re.fullmatch(r"HOME\s+(.+)", u):
            world.move({axis: 0.0 for axis in m.group(1).split() if axis in AXES}, incremental=False)
            return ""
        if m := re.fullmatch(r"(ENABLE|DISABLE)\s+(.+)", u):
            axes = {axis for axis in m.group(2).split() if axis in AXES}
            world.enabled = world.enabled | axes if m.group(1) == "ENABLE" else world.enabled - axes
            return ""
        if m := re.fullmatch(r"GALVO\s+LASEROVERRIDE\s+(\w+)\s+(\w+)", u):
            world.laser_on = m.group(2) == "ON"
            return ""
        if m := re.fullmatch(r"VELOCITY\s+(ON|OFF)", u):
            return ""
        if m := re.fullmatch(r"IFOV\s+(ON|OFF)", u):
            world.ifov = m.group(1) == "ON"
            return ""
        if m := re.fullmatch(rf"DWELL\s+({_NUMBER})", u):
            world.clock.advance(float(m.group(1)))
            return ""
        if m := re.fullmatch(r"\$AO\[0\]\.A\s*=\s*(.+)", s, re.IGNORECASE):
            world.attenuator_value = self._eval(m.group(1))
            return ""
        if m := re.fullmatch(r"\$(\w+(?:\[\d+\])?)\s*=\s*(.+)", s):
            world.variables[m.group(1)] = self._eval(m.group(2))
            return ""
        if m := re.fullmatch(r'PROGRAM\s+(\d+)\s+(LOAD|ASSOCIATE)\s+"(.*)"', s, re.IGNORECASE):
            return self._program_load(int(m.group(1)), m.group(3), m.group(2).upper() == "LOAD")
        if m := re.fullmatch(r"PROGRAM\s+(?:(\d+)\s+)?(START|STOP)", u):
            task_id = int(m.group(1) or self.current_task)
            if m.group(2) == "START":
                return self._program_start(task_id)
            world.task(task_id).state = _IDLE
            world.task(task_id).running_polls = 0
            return ""
        if re.fullmatch(r'REMOVEPROGRAM\s+"(.*)"', s, re.IGNORECASE):
            return ""
        if re.fullmatch(rf"A?F{_NUMBER}", u):  # connected speed, e.g. "F10"
            return ""
        if u.startswith(_NOOP_PREFIXES):
            return ""
        raise _Unhandled(s)

    # Status queries

    def _status(self, query: list[str]) -> str:
        if len(query) == 1:
            return self._system_item(query[0])
        first, item = query[0], query[1]
        if first.isdigit():
            return self._task_item(int(first), item)
        return self._axis_item(first.upper(), item)

    def _axis_item(self, axis: str, item: str) -> str:
        if axis not in AXES:
            raise _Fault(f"Unknown axis {axis}")
        if item in ("PositionFeedback", "PositionCommand", "ProgramPositionFeedback", "ProgramPositionCommand"):
            return self._format(self.world.stage[axis])
        if item in ("VelocityFeedback", "VelocityCommand"):
            return self._format(0.0)
        if item == "AccelerationRate":
            return self._format(self.acceleration[axis])
        if item == "DriveStatus":
            return str(0x02000000 | 0x00000001)  # InPosition | Enabled
        if item == "AxisStatus":
            return str(0x00000001)  # Homed
        if item in ("AxisFault", "AxisFaultMask"):
            return "0"
        raise _Unhandled(f"AXISSTATUS item {item}")

    def _task_item(self, task_id: int, item: str) -> str:
        task = self.world.task(task_id)
        if item == "TaskState":
            if task.running_polls > 0:
                task.running_polls -= 1
                return str(_RUNNING)
            return str(task.state)
        if item == "TaskMode":
            return str(0x00000002 if self.world.absolute else 0)  # TaskMode.Absolute
        if item in ("TaskStatus0", "TaskStatus1", "TaskStatus2", "QueueLineCount"):
            return "0"
        if item == "ProgramLineNumber":
            return str(task.line_number)
        if item == "TaskErrorCode":
            return str(task.error_code)
        if item == "TaskErrorLocation":
            return str(task.error_location)
        raise _Unhandled(f"TASKSTATUS item {item}")

    def _system_item(self, item: str) -> str:
        if item == "Timer":
            return str(int(round(self.world.clock.now * 1000)))
        raise _Unhandled(f"SYSTEMSTATUS item {item}")

    # Program tasks

    def _program_load(self, task_id: int, path: str, check_file: bool) -> str:
        if check_file and not Path(path).is_file():
            raise _Fault(f"Program file not found: {path}")
        task = self.world.task(task_id)
        task.program_path = path
        task.state = _READY
        task.line_number = 0
        task.error_code = task.error_location = 0
        return ""

    def _program_start(self, task_id: int) -> str:
        task = self.world.task(task_id)
        if task.program_path is None:
            raise _Fault(f"No program loaded on task {task_id}")

        path = Path(task.program_path)
        lines = path.read_text().splitlines() if path.is_file() else []
        executed, not_simulated = self.run_program(lines)
        task.line_number = len(lines)
        if self._program_errors:
            task.error_code, task.error_location, task.running_polls = self._program_errors.popleft()
            task.state = _ERROR
        else:
            task.running_polls = self.running_polls
            task.state = _COMPLETE
        self.world.calllog.record("program", str(path), (task_id,),
                                  {"lines": len(lines), "executed": executed, "not_simulated": not_simulated},
                                  self.world.clock.now)
        return ""

    def run_program(self, lines: list[str]) -> tuple[int, int]:
        """ Execute the statements of an AeroBasic program.

        Only statements that change the simulated state are executed (see
        :meth:`execute`). Other statements are counted as not simulated.

        Parameters
        ----------
        lines : list of str
            Program lines.

        Returns
        -------
        tuple of int
            Number of executed and of not simulated statements.
        """

        executed = not_simulated = 0
        for line in lines:
            statement = line.split("'", 1)[0] if '"' not in line else line
            statement = statement.strip()
            if not statement:
                continue
            if statement.upper() == "END PROGRAM":
                break
            try:
                self.execute(statement)
                executed += 1
            except (_Unhandled, _Fault):
                not_simulated += 1
        return executed, not_simulated


_OPERATORS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
    ast.Pow: operator.pow, ast.USub: operator.neg, ast.UAdd: operator.pos,
}


def _safe_eval(text: str) -> float:
    """ Evaluate an arithmetic expression of numbers only. """

    def visit(node):
        if isinstance(node, ast.Expression):
            return visit(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        if isinstance(node, ast.BinOp) and type(node.op) in _OPERATORS:
            return _OPERATORS[type(node.op)](visit(node.left), visit(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in _OPERATORS:
            return _OPERATORS[type(node.op)](visit(node.operand))
        raise _Unhandled(f"Unsupported expression {text!r}")

    try:
        return visit(ast.parse(text, mode="eval"))
    except SyntaxError as error:
        raise _Unhandled(f"Unsupported expression {text!r}") from error
