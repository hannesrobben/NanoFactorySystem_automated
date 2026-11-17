##########################################################################
# Copyright (c) 2026 Hannes Robben                                       #
# <hannes.robben@phoenixd.uni-hannover.de>                               #
# This program is free software under the terms of the MIT license.      #
##########################################################################
"""Named structure factories (T77, docs/design/INFORMATION_MODEL.md §6.3).

Some structures need values that exist only once the experiment runs, mostly
the galvo acceleration read from the controller. A plain callable
``factory(experiment)`` cannot be stored, so an experiment that uses one
cannot be saved as a project file. A *named* factory can::

    @structure_factory("parameter_study.rectangle")
    def rectangle(context: BuildContext, *, hatch: float, slice_size: float, velocity: float) -> DrawableObject:
        return Rectangle3D(..., acceleration=context.accel_a_um)

    StructureSpec("rect_0", factory=rectangle(hatch=0.2, slice_size=0.2, velocity=1000))

Calling the registered factory with its keyword arguments returns a
:class:`FactoryCall` (name + JSON arguments); the structure is built later
with a :class:`BuildContext` of the running experiment. The stored form keeps
the name, the arguments, the module and the source file of the function, so
that loading imports the module (or the file) when the name is not
registered yet.
"""
import importlib
import importlib.util
import inspect
import math
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from .aerobasic.programs.drawings.base import DrawableObject, decode_json_value, encode_json_value
from .devices.coordinate_system import DropDirection

__all__ = ["BuildContext", "FactoryCall", "StructureFactory", "structure_factory", "registered_factory",
           "factory_from_json", "factory_names"]


@dataclass(frozen=True)
class BuildContext:
    """ The values of the running experiment that a structure factory may read.

    Not the whole :class:`~nanofactorysystem.experiment.Experiment`: this keeps
    factories testable and their result independent of hardware objects.

    Parameters
    ----------
    objective : str
        Objective key, e.g. ``"Zeiss 63x"``.
    setup : str
        Setup of the structure (``"IFOV_on"`` / ``"IFOV_off"``).
    accel_x_um, accel_a_um, accel_z_um : float
        Accelerations in µm/s² as used by the experiment (NaN if unknown).
    drop_direction : DropDirection, optional
    power_min_mw, power_max_mw : float, optional
        Power range of the attenuator calibration.
    power_calibration : PowerCalibration, optional
        Calibration of the attenuator, for structures that set powers in mW.
    """

    objective: str = ""
    setup: str = "IFOV_off"
    accel_x_um: float = math.nan
    accel_a_um: float = math.nan
    accel_z_um: float = math.nan
    drop_direction: Optional[DropDirection] = None
    power_min_mw: Optional[float] = None
    power_max_mw: Optional[float] = None
    power_calibration: Any = field(default=None, compare=False)

    @classmethod
    def from_experiment(cls, experiment) -> "BuildContext":
        """ Collect the context from a running experiment (or an object with the same attributes).

        Missing attributes are left at their defaults, so test doubles only
        need the values their factories read.
        """

        attenuator = getattr(getattr(getattr(experiment, "system", None), "controller", None), "attenuator", None)
        power_min = power_max = calibration = None
        if attenuator is not None:
            try:
                power_min, power_max = attenuator["powerMin"], attenuator["powerMax"]
            except (KeyError, TypeError):
                pass
            if getattr(attenuator, "data", None) is not None:
                from .devices.power_calibration import PowerCalibration
                calibration = PowerCalibration(attenuator.data)
        return cls(objective=str(getattr(experiment, "objective", "")),
                   setup=str(getattr(experiment, "setup", "IFOV_off")),
                   accel_x_um=float(getattr(experiment, "accel_x_um", math.nan)),
                   accel_a_um=float(getattr(experiment, "accel_a_um", math.nan)),
                   accel_z_um=float(getattr(experiment, "accel_z_um", math.nan)),
                   drop_direction=getattr(experiment, "drop_direction", None),
                   power_min_mw=power_min, power_max_mw=power_max, power_calibration=calibration)

    def check_power(self, *powers_mw: float) -> None:
        """ Raise ValueError if a power lies outside the attenuator calibration range.

        Raises
        ------
        ValueError
            If the range is unknown or a power lies outside it.
        """

        if self.power_min_mw is None or self.power_max_mw is None:
            raise ValueError("The power range of the attenuator calibration is unknown.")
        out_of_range = [p for p in powers_mw if not self.power_min_mw <= p <= self.power_max_mw]
        if out_of_range:
            raise ValueError(f"Powers {out_of_range} mW lie outside the attenuator calibration range "
                             f"({self.power_min_mw:.4f} - {self.power_max_mw:.4f} mW).")


@dataclass(frozen=True)
class StructureFactory:
    """ A registered factory ``function(context, **arguments) -> DrawableObject``.

    Calling it with keyword arguments returns a :class:`FactoryCall`.
    """

    name: str
    function: Callable[..., DrawableObject]

    @property
    def module(self) -> str:
        """ Module of the function. """

        return self.function.__module__

    @property
    def file(self) -> str:
        """ Source file of the function, or ``""``. """

        try:
            return str(Path(inspect.getsourcefile(self.function)).resolve())
        except (TypeError, OSError):
            return ""

    def __call__(self, **arguments) -> "FactoryCall":
        try:
            inspect.signature(self.function).bind(None, **arguments)
        except TypeError as error:
            raise TypeError(f"Structure factory {self.name!r}: {error}") from None
        return FactoryCall(self.name, dict(arguments))


_REGISTRY: dict[str, StructureFactory] = {}


def structure_factory(name: str) -> Callable[[Callable[..., DrawableObject]], StructureFactory]:
    """ Decorator that registers a structure factory under ``name``.

    The function takes a :class:`BuildContext` as first argument and only
    keyword arguments with JSON values after it. Registering the same name
    again from the same module and function (a re-imported script) replaces
    the entry.

    Raises
    ------
    ValueError
        If ``name`` is registered for another function.
    """

    def register(function: Callable[..., DrawableObject]) -> StructureFactory:
        factory = StructureFactory(name, function)
        existing = _REGISTRY.get(name)
        if existing is not None and (existing.function.__qualname__, Path(existing.file).name) != \
                (function.__qualname__, Path(factory.file).name):
            raise ValueError(f"Structure factory {name!r} is already registered for "
                             f"{existing.module}.{existing.function.__qualname__}.")
        _REGISTRY[name] = factory
        return factory

    return register


def factory_names() -> list[str]:
    """ Names of all registered factories. """

    return sorted(_REGISTRY)


def registered_factory(name: str, module: str = "", file: str = "") -> StructureFactory:
    """ Return the factory registered under ``name``, importing ``module`` or ``file`` if needed.

    Raises
    ------
    KeyError
        If the factory is still unknown after the import.
    """

    if name not in _REGISTRY and module and module != "__main__":
        try:
            importlib.import_module(module)
        except ImportError:
            pass
    if name not in _REGISTRY and file and Path(file).is_file():
        module_name = f"_structure_factory_{Path(file).stem}"
        spec = importlib.util.spec_from_file_location(module_name, file)
        loaded = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = loaded
        spec.loader.exec_module(loaded)
    if name not in _REGISTRY:
        raise KeyError(f"Structure factory {name!r} is not registered (module {module or '?'}, file {file or '?'}); "
                       f"import the script that defines it first.")
    return _REGISTRY[name]


@dataclass(frozen=True)
class FactoryCall:
    """ A named factory with its arguments; builds the structure once the experiment runs.

    It can also be called like the former plain factories, ``call(experiment)``.
    """

    name: str
    arguments: dict = field(default_factory=dict)

    def build(self, context: BuildContext) -> DrawableObject:
        """ Build the structure with the given context. """

        return registered_factory(self.name).function(context, **self.arguments)

    def __call__(self, experiment) -> DrawableObject:
        context = experiment if isinstance(experiment, BuildContext) else BuildContext.from_experiment(experiment)
        return self.build(context)

    def to_json(self) -> dict:
        """ JSON form (``kind: "factory"``) with name, arguments, module and source file.

        Raises
        ------
        TypeError
            If an argument cannot be encoded; the message names it.
        """

        factory = registered_factory(self.name)
        arguments = {}
        for key, value in self.arguments.items():
            try:
                arguments[key] = encode_json_value(value)
            except TypeError as error:
                raise TypeError(f"argument {key!r} of factory {self.name!r}: {error}") from None
        return {"kind": "factory", "name": self.name, "arguments": arguments, "module": factory.module,
                "file": factory.file}


def factory_from_json(data: dict) -> FactoryCall:
    """ Rebuild a :class:`FactoryCall` from :meth:`FactoryCall.to_json` (imports the factory if needed). """

    registered_factory(data["name"], data.get("module", ""), data.get("file", ""))
    return FactoryCall(data["name"], {k: decode_json_value(v) for k, v in data.get("arguments", {}).items()})
