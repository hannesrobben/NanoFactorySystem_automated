"""Hardware backends of the NanoFactorySystem package.

The backend decides which objects talk to the devices. ``"real"`` (the
default) opens the lab hardware exactly as before. ``"dummy"`` uses simulated
devices that share one deterministic :class:`~nanofactorysystem.backends.dummy.SimulatedWorld`.

Select a backend with the explicit argument ``System(..., backend=...)``
(or ``Experiment(..., backend=...)``). There is no environment variable.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional, Protocol, Union, runtime_checkable

from nanofactorysystem.backends.real import RealBackend

__all__ = ["Backend", "BackendLike", "RealBackend", "DummyBackend", "resolve_backend"]


@runtime_checkable
class Backend(Protocol):
    """ Factory for the objects that touch the hardware.

    A method returning None tells the device class to open its hardware
    itself (the real behaviour).
    """

    name: str

    def controller_transport(self) -> Optional[Any]: ...

    def camera_driver(self, product: Optional[str], device_id: Optional[Any]) -> Optional[Any]: ...

    def dhm_driver(self, objective: dict[str, Any]) -> Optional[Any]: ...

    def attenuator_args(self) -> dict[str, Any]: ...

    def program_dir(self) -> Optional[Path]: ...


BackendLike = Union[str, Backend, None]


def __getattr__(name: str):
    # Import the dummy backend only when it is used
    if name == "DummyBackend":
        from nanofactorysystem.backends.dummy import DummyBackend
        return DummyBackend
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def resolve_backend(backend: BackendLike = None) -> Backend:
    """ Return the backend object for the given selection.

    Parameters
    ----------
    backend : str, Backend or None
        ``None`` or ``"real"`` for the real hardware, ``"dummy"`` for a
        new :class:`DummyBackend` with default settings, or a backend
        object, which is returned unchanged.

    Returns
    -------
    Backend
        The backend object.

    Raises
    ------
    ValueError
        For an unknown backend name or object.
    """

    if backend is None or backend == "real":
        return RealBackend()
    if backend == "dummy":
        from nanofactorysystem.backends.dummy import DummyBackend
        return DummyBackend()
    if isinstance(backend, Backend):
        return backend
    raise ValueError(f"Unknown backend {backend!r}! Use 'real', 'dummy' or a backend object.")
