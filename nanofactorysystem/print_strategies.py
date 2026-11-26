"""Extension point for dynamic slicing and hatching per structure (T81).

A structure of an ``ExperimentSpec`` may name a *print strategy* and its parameters
(``StructureSpec(strategy="…", strategy_params={…})``). The name and the parameters are stored with the spec (in
``experiment_spec.json`` and ``/spec`` of the experiment file), and an unknown name is refused when the spec is
resolved. A strategy is registered by name with :func:`register_print_strategy` and receives the slicer arguments
of the structure and its parameters; it returns the slicer arguments to build the structure with. Further
strategies (adaptive slicing, shell printing, power per layer from a model; F7, F12, F17) are added by
registering a function, without changing the experiment code. The hatching strategies inside the slicer have their
own registry (``aerobasic.slicer.hatching.register_strategy``); a print strategy may select one of them.

Only ``"static"`` is built in: the slicer arguments as given (the behaviour without a strategy). Maintainer
decision 2026-11-26: build the extension point so that more strategies can be registered; no new strategy now.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

__all__ = ["PrintStrategy", "UnknownStrategyError", "register_print_strategy", "get_print_strategy",
           "print_strategy_names", "DEFAULT_STRATEGY"]

#: Strategy used when a structure names none
DEFAULT_STRATEGY = "static"

StrategyFunction = Callable[[dict, dict], dict]


class UnknownStrategyError(ValueError):
    """ A structure names a print strategy that is not registered. """


@dataclass(frozen=True)
class PrintStrategy:
    """ A registered print strategy.

    Attributes
    ----------
    name : str
        Registry name, stored with the spec.
    function : callable
        ``function(slicer_arguments, parameters) -> slicer_arguments``; must not change its inputs.
    description : str
        One line for listings.
    """

    name: str
    function: StrategyFunction
    description: str = ""

    def apply(self, slicer: dict, parameters: dict) -> dict:
        """ Slicer arguments of a structure after the strategy (inputs are not changed).

        Parameters
        ----------
        slicer : dict
            Slicer arguments of the structure (``StructureSpec.slicer``).
        parameters : dict
            Strategy parameters (``StructureSpec.strategy_params``).

        Returns
        -------
        dict
        """

        return dict(self.function(dict(slicer), dict(parameters)))


_REGISTRY: dict[str, PrintStrategy] = {}


def register_print_strategy(name: str, description: str = "") -> Callable[[StrategyFunction], StrategyFunction]:
    """ Decorator: register a print strategy under ``name``.

    Parameters
    ----------
    name : str
        Registry name.
    description : str
        One line for listings.

    Raises
    ------
    ValueError
        If the name is registered for another function.
    """

    def register(function: StrategyFunction) -> StrategyFunction:
        existing = _REGISTRY.get(name)
        if existing is not None and existing.function.__qualname__ != function.__qualname__:
            raise ValueError(f"Print strategy {name!r} is already registered for {existing.function.__qualname__}.")
        _REGISTRY[name] = PrintStrategy(name, function, description)
        return function

    return register


def get_print_strategy(name: str) -> PrintStrategy:
    """ The registered strategy ``name``.

    Raises
    ------
    UnknownStrategyError
        If no strategy of that name is registered (the message lists the registered ones).
    """

    try:
        return _REGISTRY[name]
    except KeyError:
        raise UnknownStrategyError(f"Unknown print strategy {name!r}; registered: {', '.join(print_strategy_names())}"
                                   f" (register one with nanofactorysystem.print_strategies.register_print_strategy, "
                                   f"T81).") from None


def print_strategy_names() -> list[str]:
    """ Names of the registered print strategies, sorted. """

    return sorted(_REGISTRY)


@register_print_strategy(DEFAULT_STRATEGY, "slicer arguments as given (no dynamic slicing or hatching)")
def _static(slicer: dict, parameters: dict) -> dict:
    if parameters:
        raise ValueError(f"The print strategy 'static' takes no parameters, got {sorted(parameters)}.")
    return slicer
