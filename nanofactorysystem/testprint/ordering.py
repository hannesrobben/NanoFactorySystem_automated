"""In-layer ordering strategies of test fields (T139, design §4.3, decision D16).

The order in which the elements of one merged layer are written is expected to change (follow
outline borders, cross-hatch patterns, group by power, …; maintainer note 2026-11-25). A field
therefore names its ordering strategy (stored with the field arguments, so a restart uses the same
order), and strategies are registered by name.

A strategy takes the elements of one layer, in the order the field collected them (header first,
then the cells row by row, inside a cell the order of the primitive), and returns them in print
order. Elements carry ``meta["row"]`` and ``meta["col"]`` (-1 for the header). A strategy must be
deterministic.
"""
from __future__ import annotations

from typing import Callable

from nanofactorysystem.aerobasic.slicer.toolpath import PathElement

__all__ = ["register_ordering", "ordering", "ordering_names", "OrderingStrategy", "DEFAULT_ORDERING"]

OrderingStrategy = Callable[[list[PathElement]], list[PathElement]]
DEFAULT_ORDERING = "row_by_row"

_ORDERINGS: dict[str, OrderingStrategy] = {}


def register_ordering(name: str) -> Callable[[OrderingStrategy], OrderingStrategy]:
    """ Decorator that registers an in-layer ordering strategy under ``name``.

    Raises
    ------
    ValueError
        If ``name`` is registered for another function.
    """

    def register(function: OrderingStrategy) -> OrderingStrategy:
        existing = _ORDERINGS.get(name)
        if existing is not None and existing.__qualname__ != function.__qualname__:
            raise ValueError(f"Ordering {name!r} is already registered.")
        _ORDERINGS[name] = function
        return function

    return register


def ordering(name: str) -> OrderingStrategy:
    """ The strategy registered under ``name``.

    Raises
    ------
    ValueError
        For an unknown name.
    """

    if name not in _ORDERINGS:
        raise ValueError(f"Unknown in-layer ordering {name!r}; registered: {ordering_names()}")
    return _ORDERINGS[name]


def ordering_names() -> list[str]:
    """ Names of all registered strategies. """

    return sorted(_ORDERINGS)


@register_ordering("row_by_row")
def row_by_row(elements: list[PathElement]) -> list[PathElement]:
    """ Header first, then the cells row by row (row 0 = lowest y), each row from left to right;
    inside a cell the order of the primitive. The power changes at most once per cell part. """

    return sorted(elements, key=lambda e: (int(e.meta.get("row", -1)), int(e.meta.get("col", -1))))
