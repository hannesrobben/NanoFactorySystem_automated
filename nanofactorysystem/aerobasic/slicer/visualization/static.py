# static.py
"""PNG flipbook of a sliced job — one image per layer.

Debug view for the slicing result (docs/05): renders the Toolpath-IR
*before* IFOV translation, so slicing/hatching problems are visible at the
source instead of at the end of the pipe. Colour semantics follow the
element routing in ``Model3D_Slicer.iterate_layers``:

    grey fill     design cross-section (``ElementGroup.contours``) —
                  the "should" against which the toolpath is judged
    blue lines    contour paths -> rendered via IFOV_PolyLines
    orange lines  infill segments -> rendered via IFOV_Lines

Builds ``matplotlib.figure.Figure`` objects directly (no pyplot): works
headless (lab PC, CI) and never touches the interactive pyplot state of
the experiment's own figures (``experiment.plot_experiment`` etc.).
"""
from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
from matplotlib.collections import LineCollection
from matplotlib.figure import Figure
from matplotlib.patches import PathPatch
from matplotlib.path import Path as MplPath

from .layer_artists import LayerArtistData, job_bounds, layer_artist_data

log = logging.getLogger(__name__)

STYLE_DESIGN = dict(facecolor="0.85", edgecolor="0.6", linewidth=0.5, zorder=0)
STYLE_CONTOUR = dict(colors="tab:blue", linewidths=1.2, zorder=2)
STYLE_INFILL = dict(colors="tab:orange", linewidths=0.5, alpha=0.9, zorder=1)


def _design_patch(data: LayerArtistData) -> PathPatch | None:
    """All design polygons (with holes) as one PathPatch (even-odd fill)."""
    if not data.design_polygons:
        return None
    vertices: list[np.ndarray] = []
    codes: list[np.ndarray] = []
    for exterior, holes in data.design_polygons:
        for ring in [exterior, *holes]:
            n = len(ring)
            vertices.append(ring)
            ring_codes = np.full(n, MplPath.LINETO, dtype=np.uint8)
            ring_codes[0] = MplPath.MOVETO
            ring_codes[-1] = MplPath.CLOSEPOLY
            codes.append(ring_codes)
    path = MplPath(np.vstack(vertices), np.concatenate(codes))
    return PathPatch(path, **STYLE_DESIGN)


def draw_layer(ax, data: LayerArtistData) -> None:
    """Draw one layer's primitives onto an existing Axes."""
    patch = _design_patch(data)
    if patch is not None:
        ax.add_patch(patch)
    if data.contour_paths:
        ax.add_collection(LineCollection(data.contour_paths, **STYLE_CONTOUR))
    if data.infill_segments:
        ax.add_collection(LineCollection(data.infill_segments, **STYLE_INFILL))
    ax.set_aspect("equal")
    ax.set_xlabel("x [µm]")
    ax.set_ylabel("y [µm]")


def plot_layer(group, ax=None):
    """Plot one ``ElementGroup`` (layer). Returns the Axes.

    Convenience for interactive inspection of a single layer; the
    flipbook uses ``draw_layer`` on pre-extracted data directly.
    """
    if ax is None:
        import matplotlib.pyplot as plt
        _, ax = plt.subplots(figsize=(6, 6))
    data = layer_artist_data(group)
    draw_layer(ax, data)
    ax.autoscale_view()
    ax.set_title(f"z = {data.z_um:.3f} µm  "
                 f"({data.n_contours} contours, {data.n_infill} infill)")
    return ax


def plot_job_layers(
    job,
    out_dir: str | Path,
    *,
    dpi: int = 150,
    figsize: tuple[float, float] = (6.0, 6.0),
    margin_frac: float = 0.05,
) -> list[Path]:
    """Write one PNG per layer group of ``job`` into ``out_dir``.

    Filenames are ``layer_0000.png`` ... in print order; every frame shares
    the same axis limits (job bounding box + margin) so the flipbook can be
    scrubbed without the view jumping. Shell groups (no z) are skipped with
    a log note — they have no 2D cross-section.

    Returns the list of written file paths.

    Implementation note: builds ``matplotlib.figure.Figure`` directly (no
    pyplot state machine) — safe in headless/threaded contexts and leaks no
    figures into an interactive session.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    xmin, ymin, xmax, ymax = job_bounds(job)
    mx = (xmax - xmin) * margin_frac or 1.0
    my = (ymax - ymin) * margin_frac or 1.0

    written: list[Path] = []
    n_skipped = 0
    frame = 0
    for group in job.groups:
        if group.z_um is None:
            n_skipped += 1
            continue
        data = layer_artist_data(group)

        fig = Figure(figsize=figsize, dpi=dpi)
        ax = fig.add_subplot(111)
        draw_layer(ax, data)
        ax.set_xlim(xmin - mx, xmax + mx)
        ax.set_ylim(ymin - my, ymax + my)
        ax.set_title(
            f"Layer {frame}  |  z = {data.z_um:.3f} µm  |  "
            f"{data.n_contours} contours, {data.n_infill} infill")

        path = out_dir / f"layer_{frame:04d}.png"
        fig.savefig(path, bbox_inches="tight")
        written.append(path)
        frame += 1

    if n_skipped:
        log.info("plot_job_layers: skipped %d shell group(s) without z",
                 n_skipped)
    log.info("plot_job_layers: wrote %d layer plots to %s",
             len(written), out_dir)
    return written
