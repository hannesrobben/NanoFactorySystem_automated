##########################################################################
# Copyright (c) 2026 Hannes Robben                                       #
# <hannes.robben@phoenixd.uni-hannover.de>                               #
# This program is free software under the terms of the MIT license.      #
##########################################################################
"""Where is what on a substrate: ``substrate_layout.json`` and ``substrate_layout.png`` (T118).

Both files lie next to ``substrate.json`` in the substrate folder and are
rewritten from the substrate index every time the index changes
(:meth:`~nanofactorysystem.storage.substrate_store.SubstrateStore._update`),
so they always show every experiment ever entered on the substrate (planned,
running, done, aborted) with its area in absolute stage coordinates, and the
resin drops. The index (``substrate.json``) stays the source of truth; these
two files are a readable copy for the lab and are never read back.

The plot is drawn on a plain :class:`matplotlib.figure.Figure` (no pyplot),
so writing it never opens a window and works without a display.
"""
from pathlib import Path
from typing import Optional

import numpy as np

from .json_copies import write_json
from .records import utc_timestamp

LAYOUT_JSON = "substrate_layout.json"
LAYOUT_PNG = "substrate_layout.png"
LAYOUT_SCHEMA = "nanofactory.substrate_layout/1"
# State of an index entry (see substrate_store.STATES) -> colour in the plot
STATE_COLORS = {"planned": "tab:blue", "running": "tab:orange", "done": "tab:green", "aborted": "tab:red"}


def _ellipse(edges) -> Optional[dict]:
    """ Ellipse of a resin drop as dict (``cx_um``, ``cy_um``, ``a_um``, ``b_um``), None without four edges. """

    from ..resin_drop import drop_outline

    outline = drop_outline(edges)
    if outline is None:
        return None
    return {"cx_um": float(outline.cx), "cy_um": float(outline.cy), "a_um": float(outline.a),
            "b_um": float(outline.b)}


def layout_dict(record) -> dict:
    """ Return the content of ``substrate_layout.json`` for a substrate record.

    Parameters
    ----------
    record : SubstrateRecord
        The substrate with its index.

    Returns
    -------
    dict
        ``schema``, ``written``, ``substrate`` (label, uuid, user, material,
        type, dimensions, notes), ``resin_drops`` (index, edges, ellipse,
        material, batch, thickness, application), ``experiments`` (label,
        name, status, state, objective, center, area incl. markers, resin
        drop, folder relative to the substrate folder, started, uuid),
        ``bounds_um`` (bounding box of drops and areas, None if empty) and
        ``image`` (file name of the plot). All coordinates are absolute stage
        coordinates in µm.
    """

    from .substrate_store import STATES

    drops = []
    for index, drop in enumerate(record.resin_drops):
        edges = drop.get("edges_um") or []
        drops.append({"index": index, "edges_um": edges, "ellipse": _ellipse(edges),
                      "material": drop.get("material", ""), "batch": drop.get("batch", ""),
                      "thickness_um": drop.get("thickness_um"), "application": drop.get("application", "drop"),
                      "added": drop.get("added", "")})
    experiments = []
    for entry in record.experiments:
        status = entry.get("status", "")
        experiments.append({"label": entry.get("label", ""), "name": entry.get("name", ""), "status": status,
                            "state": STATES.get(status, "running"), "objective": entry.get("objective", ""),
                            "center_um": entry.get("center_um"), "area_um": entry.get("area_um"),
                            "resin_drop": entry.get("resin_drop"), "path": entry.get("path", ""),
                            "started": entry.get("started", entry.get("planned", "")),
                            "uuid": entry.get("uuid", "")})
    return {"schema": LAYOUT_SCHEMA, "written": utc_timestamp(),
            "substrate": {"label": record.label, "uuid": record.uuid, "user": record.user,
                          "substrate_material": record.substrate_material, "substrate_type": record.substrate_type,
                          "dimensions": record.dimensions, "material": record.material, "notes": record.notes},
            "resin_drops": drops, "experiments": experiments, "bounds_um": _bounds(drops, experiments),
            "image": LAYOUT_PNG}


def _bounds(drops: list[dict], experiments: list[dict]) -> Optional[list[list[float]]]:
    """ Bounding box of all drop edges and experiment areas, None if there is nothing to show. """

    points = [p for d in drops for p in d["edges_um"]]
    points += [p for e in experiments if e["area_um"] for p in e["area_um"]]
    if not points:
        return None
    points = np.asarray(points, dtype=float)
    return [[float(v) for v in points.min(axis=0)], [float(v) for v in points.max(axis=0)]]


def plot_layout(layout: dict):
    """ Draw a layout (see :func:`layout_dict`) without pyplot.

    Resin drops are grey (edges as crosses, ellipse through them), experiment
    areas are coloured by state (planned blue, running orange, done green,
    aborted red) and labelled with experiment label, name and status.

    Parameters
    ----------
    layout : dict
        Content of ``substrate_layout.json``.

    Returns
    -------
    matplotlib.figure.Figure
    """

    from matplotlib.figure import Figure
    from matplotlib.patches import Ellipse, Patch, Rectangle

    figure = Figure(figsize=(8, 8))
    ax = figure.add_subplot()
    for drop in layout["resin_drops"]:
        edges = np.asarray(drop["edges_um"], dtype=float).reshape(-1, 2)
        if len(edges):
            ax.plot(edges[:, 0], edges[:, 1], "x", color="grey")
        ellipse = drop["ellipse"]
        if ellipse is not None:
            ax.add_patch(Ellipse((ellipse["cx_um"], ellipse["cy_um"]), 2 * ellipse["a_um"], 2 * ellipse["b_um"],
                                 fill=False, color="grey"))
            ax.annotate(f"drop {drop['index']} {drop['material']}".strip(),
                        (ellipse["cx_um"], ellipse["cy_um"] + ellipse["b_um"]), ha="center", va="bottom",
                        fontsize=7, color="grey")
    for experiment in layout["experiments"]:
        if not experiment["area_um"]:
            continue
        lower, upper = np.asarray(experiment["area_um"], dtype=float)
        color = STATE_COLORS.get(experiment["state"], "tab:grey")
        planned = experiment["state"] == "planned"
        ax.add_patch(Rectangle(lower, *(upper - lower), alpha=0.15 if planned else 0.35, color=color,
                               linestyle="--" if planned else "-"))
        ax.add_patch(Rectangle(lower, *(upper - lower), fill=False, color=color,
                               linestyle="--" if planned else "-"))
        name = experiment["label"] or experiment["name"]
        detail = experiment["name"] if experiment["label"] and experiment["name"] else ""
        text = "\n".join(t for t in (name, detail, experiment["status"]) if t)
        ax.annotate(text, (lower + upper) / 2, ha="center", va="center", fontsize=7)
    bounds = layout["bounds_um"]
    if bounds is not None:
        lower, upper = np.asarray(bounds, dtype=float)
        pad = max(float(np.max(upper - lower)) * 0.05, 100.0)
        ax.set_xlim(lower[0] - pad, upper[0] + pad)
        ax.set_ylim(lower[1] - pad, upper[1] + pad)
    ax.set_aspect("equal")
    ax.set_xlabel("x [µm] (stage)")
    ax.set_ylabel("y [µm] (stage)")
    ax.grid(True, linewidth=0.3)
    substrate = layout["substrate"]
    ax.set_title(f"Substrate {substrate['label']}: {len(layout['experiments'])} experiment(s), "
                 f"{layout['written']}", fontsize=9)
    ax.legend(handles=[Patch(color=c, alpha=0.5, label=s) for s, c in STATE_COLORS.items()], fontsize=7,
              loc="upper right")
    figure.tight_layout()
    return figure


def write_substrate_layout(folder: Path, record) -> tuple[Path, Path]:
    """ Write ``substrate_layout.json`` and ``substrate_layout.png`` into a substrate folder.

    Parameters
    ----------
    folder : Path
        The substrate folder (next to ``substrate.json``).
    record : SubstrateRecord
        The substrate with its index.

    Returns
    -------
    (Path, Path)
        The JSON file and the image.
    """

    folder = Path(folder)
    layout = layout_dict(record)
    json_file, png_file = folder / LAYOUT_JSON, folder / LAYOUT_PNG
    write_json(json_file, layout)
    tmp = png_file.with_name(png_file.stem + ".tmp.png")
    plot_layout(layout).savefig(tmp, dpi=150)
    tmp.replace(png_file)
    return json_file, png_file
