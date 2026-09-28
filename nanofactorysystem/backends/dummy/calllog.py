"""Ordered log of every call that reaches a simulated device."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterator, Optional


@dataclass(frozen=True)
class CallRecord:
    """ One call to a simulated device.

    Attributes
    ----------
    device : str
        Device name: ``"controller"``, ``"camera"``, ``"dhm"`` or ``"program"``.
    call : str
        Command string (controller) or method/attribute name (other devices).
    args : tuple
        Arguments of the call.
    result : Any
        Returned value or response frame.
    t : float
        Virtual time in seconds at which the call happened.
    """

    device: str
    call: str
    args: tuple = ()
    result: Any = None
    t: float = 0.0


class CallLog:
    """ Ordered, append-only list of :class:`CallRecord` objects. """

    def __init__(self):
        self.records: list[CallRecord] = []

    def __len__(self) -> int:
        return len(self.records)

    def __iter__(self) -> Iterator[CallRecord]:
        return iter(self.records)

    def __getitem__(self, index):
        return self.records[index]

    def record(self, device: str, call: str, args: tuple = (), result: Any = None, t: float = 0.0) -> CallRecord:
        """ Append a record and return it.

        Parameters
        ----------
        device : str
            Device name.
        call : str
            Command string or method name.
        args : tuple
            Call arguments.
        result : Any
            Returned value.
        t : float
            Virtual time in seconds.

        Returns
        -------
        CallRecord
            The new record.
        """

        rec = CallRecord(device, call, tuple(args), result, t)
        self.records.append(rec)
        return rec

    def filter(self, device: Optional[str] = None, call: Optional[str] = None) -> list[CallRecord]:
        """ Return the records matching the given device and call name.

        Parameters
        ----------
        device : str, optional
            Only records of this device.
        call : str, optional
            Only records with exactly this call name.

        Returns
        -------
        list of CallRecord
            Matching records in call order.
        """

        return [r for r in self.records
                if (device is None or r.device == device) and (call is None or r.call == call)]

    def commands(self) -> list[str]:
        """ Return the controller command strings in the order they were sent.

        Returns
        -------
        list of str
            Command lines without the terminating character.
        """

        return [r.call for r in self.records if r.device == "controller"]

    def clear(self) -> None:
        """ Remove all records. """

        self.records.clear()
