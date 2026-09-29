import re
import socket
import time
from typing import Callable, Optional

from nanofactorysystem.aerobasic import AeroBasicAPI, SingleAxis
from nanofactorysystem.aerobasic.constants import ReturnCode, Version, DataItemEnum
from nanofactorysystem.utils.typing import StatusQueryType


class AerotechError(RuntimeError):
    """ Error reported by the A3200 controller.

    It is a ``RuntimeError``, the exception the older ``A3200`` controller
    class raised, so existing handlers for both keep working.
    """


class TaskFailedError(AerotechError, ValueError):
    """ A controller task (program) ended in a state other than ``program_complete``.

    It is an :class:`AerotechError`, so callers handling controller errors
    catch it, and a ``ValueError`` for code that caught the previous
    exception type of ``Task.wait_to_finish``.
    """


def recv_line(sock, terminator: str = chr(10), bufsize: int = 4096) -> str:
    """ Read from a socket until the terminating character arrives.

    Parameters
    ----------
    sock : socket-like
        Connected socket (or simulated transport).
    terminator : str
        Terminating character of a response.
    bufsize : int
        Maximum number of bytes per ``recv`` call.

    Returns
    -------
    str
        The decoded response including the terminating character.

    Raises
    ------
    ConnectionError
        If the connection is closed before the response is complete.
    """

    data = b""
    end = terminator.encode()
    while not data.endswith(end):
        chunk = sock.recv(bufsize)
        if not chunk:
            raise ConnectionError(f"Connection closed while waiting for a response (received {data!r})")
        data += chunk
    return data.decode()


class AsciiCommandResponse:
    def __init__(self, command: str):
        self.command = command

        # Return data
        self.return_code: Optional[ReturnCode] = None
        self.data: Optional[str] = None
        self.error: Optional[str] = None

        # Timings
        self.timestamp_sent: Optional[float] = None
        self.timestamp_received: Optional[float] = None
        self.timestamp_error: Optional[float] = None

    def __str__(self) -> str:
        """
        Formats the AsciiCommandResponse. Examples:
            - [SUCCESS] 'ENABLE X' -> '' <1716309894.6362026 -> 1716309894.6562026 ping=20ms>
            - [INVALID] 'ENBALE X' -> ''<1716309894.6362026 -> 1716309894.6562026 ping=20ms>
            - [FAULT] 'ENABLE X' -> '' (Axis already enabled!) <1716309894.6362026 -> 1716309894.6562026 ping=20ms>
            - [WAIT] 'ENABLE X' -> <1716309894.6362026>
            - [PENDING] 'ENABLE X'
        """
        if self.has_response():
            if self.has_error():
                error_string = f" ({self.error})"
            else:
                error_string = ""

            return (
                f"[{self.return_code.name}] {repr(self.command)} -> {repr(self.data)}{error_string} "
                f"<{self.timestamp_sent} -> {self.timestamp_received} ping={self.ping * 1000}ms>"
            )
        if self.is_sent():
            return f"[WAIT] {repr(self.command)} -> <{self.timestamp_sent}>"
        return f"[PENDING] {repr(self.command)}"

    def is_sent(self) -> bool:
        return self.timestamp_sent is not None

    def has_response(self) -> bool:
        return self.return_code is not None

    def has_error(self) -> bool:
        return self.error is not None

    @property
    def ping(self) -> float:
        if self.timestamp_sent is None:
            return -float("inf")

        if self.timestamp_received is None:
            return float("inf")

        return self.timestamp_received - self.timestamp_sent


class AerotechAsciiInterface(AeroBasicAPI):
    COMMAND_TERMINATING_CHARACTER = 10  # \n

    def __init__(self, hostname: str = "127.0.0.1", port: int = 8000, *,
                 transport_factory: Optional[Callable[[], "socket.socket"]] = None,
                 connect_timeout: Optional[float] = 10.0, response_timeout: Optional[float] = None):
        """ ASCII command interface of the Aerotech A3200 controller.

        Parameters
        ----------
        hostname : str
            Host of the ASCII command interface.
        port : int
            TCP port of the ASCII command interface.
        transport_factory : callable, optional
            Returns a socket-like object that is used by :meth:`connect`
            instead of a new TCP socket, e.g. the simulated controller of the
            dummy backend.
        connect_timeout : float or None
            Timeout in seconds for establishing the connection.
        response_timeout : float or None
            Timeout in seconds for each response. Default None (no limit),
            because motion commands may legitimately take long.
        """
        super().__init__()
        self.hostname = hostname
        self.port = port
        self.transport_factory = transport_factory
        self.connect_timeout = connect_timeout
        self.response_timeout = response_timeout

        # Safety limit for immediate absolute z moves in mm (None: no limit).
        # The programming mode is tracked from the ABSOLUTE/INCREMENTAL
        # commands sent through this interface; the controller starts in
        # ABSOLUTE mode.
        self.z_limit: Optional[float] = None
        self._absolute = True
        self.history: list[AsciiCommandResponse] = []

        # TCP socket to the A3200 system
        self.socket: Optional[socket.socket] = None
        self._follow_errors = True  # Internal variable that is used to avoid recursion

    def __call__(self, program):
        from nanofactorysystem.aerobasic.programs import AeroBasicProgram
        if isinstance(program, str):
            for line in program.split("\n"):
                self.send(line)
        elif isinstance(program, AeroBasicProgram):
            for line in program.lines:
                self.send(line)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(hostname={self.hostname}, port={self.port})"

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        self.close()
        return False  # Propagate exception to higher levels

    def __del__(self):
        self.close()

    def __enter__(self):
        return self.connect()

    @property
    def is_opened(self) -> bool:
        return self.socket is not None

    def connect(self) -> "AerotechAsciiInterface":
        if self.socket is None:
            try:
                if self.transport_factory is None:
                    self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                else:
                    self.socket = self.transport_factory()
                self.socket.settimeout(self.connect_timeout)
                self.socket.connect((self.hostname, self.port))
                self.socket.settimeout(self.response_timeout)
            except (ConnectionRefusedError, TimeoutError):
                self.socket.close()
                self.socket = None
                self.logger.error(f"Connection to A3200 controller failed! ({self.hostname}:{self.port})")
                raise
        return self

    def close(self):
        if self.socket is not None:
            self.socket.close()
            self.socket = None

    def run_testzweck_altesSystem(self, cmd: str):
        """ Run the given AeroBasic command on the A3200 controller. """

        cmdTerminatingChar= 10
        cmdSuccessChar= 37
        cmdInvalidChar= 33
        cmdFaultChar= 35
        if not self.is_opened:
            raise RuntimeError("Not connected!")

        # Append terminal character
        if cmd[-1] != chr(cmdTerminatingChar):
            cmd += chr(cmdTerminatingChar)

        # Send command
        self.socket.send(cmd.encode())

        # Read and return response
        line = recv_line(self.socket, chr(cmdTerminatingChar)).strip()
        code, response = line[0], line[1:]
        if code != chr(cmdSuccessChar):
            self.socket.send(("~LASTERROR" + chr(cmdTerminatingChar)).encode())
            line = recv_line(self.socket, chr(cmdTerminatingChar)).strip()
            self.logger.error(f"Command failed! {code}, {response} -> {line}")

        data = "".join(response)

        # Check return code
        self.logger.debug(str(response))

        return data

    def send_one(self, command: str) -> str:
        """ Send a command; on an AerotechError retry it with the old, simpler protocol handling. """
        try:
            return self.send(command)
        except AerotechError:
            return self.run_testzweck_altesSystem(command)

    def send(self, command: str) -> str:

        """ Run the given AeroBasic command on the A3200 controller. """

        if not self.is_opened:
            raise RuntimeError("Not connected!")
        self._check_z_limit(command)

        # Append terminal character
        if not command.endswith(chr(self.COMMAND_TERMINATING_CHARACTER)):
            command += chr(self.COMMAND_TERMINATING_CHARACTER)

        # Send command
        cmd_resp = AsciiCommandResponse(command)
        self.history.append(cmd_resp)
        cmd_resp.timestamp_sent = time.time()
        self.socket.send(command.encode())

        # Read and return response
        code, *data = recv_line(self.socket, chr(self.COMMAND_TERMINATING_CHARACTER)).strip()
        cmd_resp.timestamp_received = time.time()
        data = "".join(data)
        cmd_resp.return_code = ReturnCode(ord(code))
        cmd_resp.data = data

        # Check return code
        self.logger.debug(str(cmd_resp))
        if cmd_resp.return_code == ReturnCode.SUCCESS:
            return data

        # Error handling -> Invalid Syntax
        if cmd_resp.return_code == ReturnCode.INVALID:
            self.logger.error(str(cmd_resp))
            raise AerotechError(f"Command '{command.strip()}' has an invalid syntax!")

        # Error handling -> Code execution failed
        if cmd_resp.return_code == ReturnCode.FAULT:
            if self._follow_errors:
                error = self.LAST_ERROR()
            else:
                error = "Error retrieving last error..."

            cmd_resp.error = error
            self.logger.error(str(cmd_resp))
            raise AerotechError(f"Execution failed for {command}. Reason: {error}")

        raise RuntimeError(f"Could not identify return code {code}")

    def _check_z_limit(self, command: str) -> None:
        """ Refuse an immediate absolute z move beyond :attr:`z_limit`.

        Raises
        ------
        AerotechError
            If the command moves z above the limit.
        """

        text = command.strip().upper()
        if text == "ABSOLUTE":
            self._absolute = True
            return
        if text == "INCREMENTAL":
            self._absolute = False
            return
        if self.z_limit is None or not self._absolute:
            return
        match = re.match(r"(LINEAR|RAPID|G0|G1)\b(.*)", text)
        if match:
            z = re.search(r"(?<![A-Z$_])Z\s*(-?\d+\.?\d*(?:E[-+]?\d+)?)", match.group(2))
        else:
            z = re.match(r"MOVEABS\s+Z\s+(-?\d+\.?\d*(?:E[-+]?\d+)?)", text)
        if z is not None and float(z.group(1)) > self.z_limit:
            raise AerotechError(f"Refused '{command.strip()}': z {float(z.group(1))} mm exceeds the "
                                f"maximum z position {self.z_limit} mm (zMax)")

    # SYSTEM COMMANDS
    def LAST_ERROR(self) -> str:
        self._follow_errors = False
        resp = self.send("~LASTERROR")
        self._follow_errors = True
        return resp

    def VERSION(self) -> Version:
        """
        Use the ~VERSION command to retrieve the version of the A3200 software that is running on the server.
        The ASCII command interface returns version information in the format of MAJOR.MINOR.REVISION.BUILD.
        """
        return Version.parse_string(self.send("~VERSION"))

    def RESETCONTROLLER(self) -> str:
        """
        Use the ~RESETCONTROLLER command to reset the controller. This command has the same functionality as when
        you click the Reset Controller button in Motion Composer. The ASCII command interface does not respond to
        this command until the reset completes.
        """
        return self.send("~RESETCONTROLLER")

    def TASK(self, task_id: int) -> str:
        """
        Use the ~TASK command to change the task on which controller commands execute. By default, controller
        commands execute on the Library task. If you change the executing task, the executing task changes only for
        that specific client. The executing tasks of other clients do not change.

        If the value that you specify for the <TaskID> argument is negative, or if the value is greater than
        the number of possible tasks, the ASCII command interface returns the CommandInvalidCharacter. If you specify
        a valid value for the <TaskID> argument and the specified task cannot execute commands, for example the task
        is in the PLCReserved state, the interface returns the CommandFaultCharacter.
        """
        return self.send(f"~TASK {task_id}")

    def STOPTASK(self, task_id: Optional[int]) -> str:
        """
        Use the ~STOPTASK command to stop a task and reset all the states for that task.
        This command has the same functionality as when you click the Stop button in Motion Composer.
        The <TaskID> argument is optional. If you specify the <TaskID> argument, the ~STOPTASK command stops the
        specified task. If you do not specify the <TaskID> argument, this command stops the current task of the client.
        """
        if task_id is None:
            return self.send("~STOPTASK")
        return self.send(f"~STOPTASK {task_id}")

    def STATUS(self, *query_tuples: StatusQueryType):
        def stringify_query(query):
            """ Converts all arguments to strings if necessary """
            args = []
            for item in query:
                if isinstance(item, str):
                    args.append(item)
                elif isinstance(item, DataItemEnum):
                    args.append(str(item.name))  # Need value here and not DataItem_value!
                elif isinstance(item, SingleAxis):
                    args.append(item.parameter_name)
                else:
                    args.append(str(item))

            return args

        query_string = " ".join([
            f"({', '.join(stringify_query(query))})"
            for query in query_tuples
        ])
        return self.send(f"~STATUS {query_string}")


class DummyAsciiInterface(AerotechAsciiInterface):
    """ Deprecated: echoes every command instead of answering it.

    Use ``nanofactorysystem.backends.dummy.FakeA3200Transport`` (via
    ``AerotechAsciiInterface(transport_factory=...)`` or the dummy backend),
    which answers queries and keeps a simulated state.
    """

    def send(self, command: str) -> str:
        self.logger.debug(command)
        return command

    def connect(self) -> "AerotechAsciiInterface":
        return self

    def close(self):
        pass
