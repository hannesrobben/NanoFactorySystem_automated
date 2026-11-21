##########################################################################
# Copyright (c) 2026 Hannes Robben                                       #
# <hannes.robben@phoenixd.uni-hannover.de>                               #
# This program is free software under the terms of the MIT license.      #
##########################################################################
"""Figures that never leave Tk objects behind for another thread (T120).

With the TkAgg backend every ``plt.subplots()`` creates a Tk window with
toolbar images and variables, even when the figure is never shown. After
``plt.close`` these Python objects stay alive until the garbage collector
frees them. If that happens in a thread other than the main thread (a camera
driver thread, for example), Tk aborts the whole process with
``Tcl_AsyncDelete: async handler deleted by the wrong thread``.

- A figure that is not shown is built without pyplot
  (:class:`matplotlib.figure.Figure`), so no Tk object is created at all.
- After a shown figure is closed, the garbage collector runs at once in the
  calling (main) thread, so the Tk objects are freed there.
"""
import gc

from matplotlib.figure import Figure


def new_figure(show: bool, **kwargs):
    """ Return ``(figure, axes)``: a pyplot figure if it will be shown, else a plain Figure.

    Parameters
    ----------
    show : bool
        The figure will be shown with :func:`finish_figure`.
    **kwargs
        Passed to ``plt.subplots`` / ``Figure`` (e.g. ``figsize``).

    Returns
    -------
    (matplotlib.figure.Figure, matplotlib.axes.Axes)
    """

    if show:
        import matplotlib.pyplot as plt
        return plt.subplots(**kwargs)
    figure = Figure(**kwargs)
    return figure, figure.add_subplot()


def finish_figure(figure, show: bool) -> None:
    """ Show a figure from :func:`new_figure` (blocking) and free its Tk objects in this thread.

    Parameters
    ----------
    figure : matplotlib.figure.Figure
    show : bool
        Same value as for :func:`new_figure`.
    """

    if show:
        import matplotlib.pyplot as plt
        plt.show()
        plt.close(figure)
        gc.collect()
