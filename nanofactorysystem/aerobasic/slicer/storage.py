# storage.py
"""Persistence of ToolpathJobs — HDF5 schema v2 (docs/02 §4).

    job.h5
    ├── metadata/                 attrs: source_file, date, recipe (JSON), ...
    │   ├── laser_params/         attrs: power_mw, scan_speed_um_s
    │   └── slicing_params/       attrs: all SlicingParameters
    ├── time_estimate/            attrs: mark_s, travel_s, switch_s, z_s, ...
    └── groups/
        ├── group_0000/           attrs: kind, z_um?, area_um2?, meta (JSON)
        │   ├── hatches           (N, 6) float64 — compact form, see below
        │   ├── elements/
        │   │   └── elem_0000/    attrs: role, closed, power_mw?, speed_um_s?
        │   │       └── points    (M, 3) float64
        │   ├── contours/poly_000/{exterior, interior_000, ...}
        │   └── dhm/              (layer)  |  surface_scan/  (shell)
        └── group_0001/ ...

Compact form: a raster of tens of thousands of 2-point infill lines as
individual HDF5 groups would drown in group overhead. Therefore the maximal
*suffix* of "plain" elements (open, 2 points, role=infill, no overrides) is
stored as one (N, 6) dataset [x0 y0 z0 x1 y1 z1]; everything before it keeps
its individual element group. Because the optimizer emits fixed elements
first and infill last, this suffix is normally the entire infill — and the
element order (including reversals) round-trips exactly: reading appends the
expanded hatches after the individual elements.

On-demand access is preserved: read_group(path, 473) touches only that
group — the basis for on-the-fly DHM comparisons during printing.
"""
from __future__ import annotations

import datetime
import json
from pathlib import Path
from typing import Iterator

import h5py
import numpy as np
from shapely.geometry import MultiPolygon, Polygon

from .parameters import JobParameters, LaserParameters, SlicingParameters
from .timing import TimeEstimate
from .toolpath import (ElementGroup, PathElement, ToolpathJob,
                       KIND_LAYER, ROLE_INFILL)

COMPRESSION = dict(compression="gzip", compression_opts=4, shuffle=True)


def _group_name(i: int) -> str:
    return f"group_{i:04d}"


def _is_plain_infill(el: PathElement) -> bool:
    return (not el.closed and el.n_vertices == 2
            and el.role == ROLE_INFILL
            and el.power_mw is None and el.speed_um_s is None
            and not el.meta)


# --------------------------------------------------------------------------
# writing
# --------------------------------------------------------------------------

def save_job(job: ToolpathJob, path: str | Path,
             time_estimate: TimeEstimate | None = None) -> Path:
    path = Path(path).with_suffix(".h5")
    with h5py.File(path, "w") as f:
        _write_metadata(f, job)
        if time_estimate is not None:
            _write_time_estimate(f, time_estimate)
        groups = f.create_group("groups")
        for i, group in enumerate(job.groups):
            _write_group(groups, i, group)
    return path


def _write_metadata(f: h5py.File, job: ToolpathJob) -> None:
    meta = f.create_group("metadata")
    meta.attrs["source_file"] = job.source_file
    meta.attrs["date"] = datetime.date.today().isoformat()
    meta.attrs["voxel_size_um"] = np.asarray(job.params.voxel_size_um)
    meta.attrs["recipe"] = json.dumps(job.recipe)
    meta.attrs["extra"] = json.dumps(job.meta, default=str)

    laser = meta.create_group("laser_params")
    for k, v in vars(job.params.laser).items():
        laser.attrs[k] = v
    slicing = meta.create_group("slicing_params")
    for k, v in vars(job.params.slicing).items():
        slicing.attrs[k] = v


def _write_time_estimate(f: h5py.File, est: TimeEstimate) -> None:
    grp = f.create_group("time_estimate")
    grp.attrs["mark_s"] = est.mark_s
    grp.attrs["travel_s"] = est.travel_s
    grp.attrs["switch_s"] = est.switch_s
    grp.attrs["z_s"] = est.z_s
    grp.attrs["total_s"] = est.total_s
    grp.attrs["mark_length_um"] = est.mark_length_um
    grp.attrs["travel_length_um"] = est.travel_length_um
    grp.attrs["n_segments"] = est.n_segments


def _write_group(parent: h5py.Group, index: int, group: ElementGroup) -> None:
    grp = parent.create_group(_group_name(index))
    grp.attrs["kind"] = group.kind
    if group.z_um is not None:
        grp.attrs["z_um"] = group.z_um
    if group.contours is not None:
        grp.attrs["area_um2"] = group.contours.area
    grp.attrs["meta"] = json.dumps(group.meta, default=str)

    # split into individual prefix + compactable suffix
    n = len(group.elements)
    split = n
    while split > 0 and _is_plain_infill(group.elements[split - 1]):
        split -= 1
    individual, compact = group.elements[:split], group.elements[split:]

    if compact:
        hatches = np.array(
            [np.concatenate([e.points[0], e.points[1]]) for e in compact],
            dtype=np.float64,
        )
    else:
        hatches = np.empty((0, 6), dtype=np.float64)
    grp.create_dataset("hatches", data=hatches, **COMPRESSION)

    elems = grp.create_group("elements")
    for i, el in enumerate(individual):
        egrp = elems.create_group(f"elem_{i:04d}")
        egrp.attrs["role"] = el.role
        egrp.attrs["closed"] = el.closed
        if el.power_mw is not None:
            egrp.attrs["power_mw"] = el.power_mw
        if el.speed_um_s is not None:
            egrp.attrs["speed_um_s"] = el.speed_um_s
        if el.meta:
            egrp.attrs["meta"] = json.dumps(el.meta, default=str)
        egrp.create_dataset("points", data=el.points, **COMPRESSION)

    if group.contours is not None:
        cont = grp.create_group("contours")
        for pi, poly in enumerate(group.contours.geoms):
            pgrp = cont.create_group(f"poly_{pi:03d}")
            pgrp.create_dataset("exterior",
                                data=np.asarray(poly.exterior.coords),
                                **COMPRESSION)
            for ii, ring in enumerate(poly.interiors):
                pgrp.create_dataset(f"interior_{ii:03d}",
                                    data=np.asarray(ring.coords),
                                    **COMPRESSION)

    # measurement slot: per-layer DHM vs. whole-shell surface scan
    grp.create_group("dhm" if group.kind == KIND_LAYER else "surface_scan")


def write_dhm(path: str | Path, group_index: int, *,
              phase_map: np.ndarray | None = None,
              height_map: np.ndarray | None = None) -> None:
    """Attach in-situ DHM data to a layer group (append mode)."""
    _write_measurement(path, group_index, "dhm",
                       phase_map=phase_map, height_map=height_map)


def write_surface_scan(path: str | Path, group_index: int,
                       **datasets: np.ndarray) -> None:
    """Attach a surface scan to a shell group (append mode)."""
    _write_measurement(path, group_index, "surface_scan", **datasets)


def _write_measurement(path, group_index, slot, **datasets) -> None:
    with h5py.File(path, "a") as f:
        grp = f[f"groups/{_group_name(group_index)}/{slot}"]
        for name, data in datasets.items():
            if data is None:
                continue
            if name in grp:
                del grp[name]
            grp.create_dataset(name, data=data, **COMPRESSION)


# --------------------------------------------------------------------------
# reading
# --------------------------------------------------------------------------

def read_params(path: str | Path) -> JobParameters:
    with h5py.File(path, "r") as f:
        meta = f["metadata"]
        laser = LaserParameters(**{
            k: (v.item() if isinstance(v, np.generic) else v)
            for k, v in meta["laser_params"].attrs.items()})
        raw = {k: (v.item() if isinstance(v, np.generic) else v)
               for k, v in meta["slicing_params"].attrs.items()}
        if "hatch_strategy" in raw:
            raw["hatch_strategy"] = str(raw["hatch_strategy"])
        slicing = SlicingParameters(**raw)
        voxel = tuple(meta.attrs["voxel_size_um"])
    return JobParameters(slicing=slicing, laser=laser, voxel_size_um=voxel)


def read_time_estimate(path: str | Path) -> TimeEstimate | None:
    with h5py.File(path, "r") as f:
        if "time_estimate" not in f:
            return None
        a = f["time_estimate"].attrs
        return TimeEstimate(
            mark_s=float(a["mark_s"]), travel_s=float(a["travel_s"]),
            switch_s=float(a["switch_s"]), z_s=float(a["z_s"]),
            mark_length_um=float(a["mark_length_um"]),
            travel_length_um=float(a["travel_length_um"]),
            n_segments=int(a["n_segments"]),
        )


def num_groups(path: str | Path) -> int:
    with h5py.File(path, "r") as f:
        return len(f["groups"])


def read_group(path: str | Path, index: int) -> ElementGroup:
    """On-demand access: load exactly one group."""
    with h5py.File(path, "r") as f:
        return _read_group(f[f"groups/{_group_name(index)}"])


def _read_group(grp: h5py.Group) -> ElementGroup:
    elements: list[PathElement] = []
    for name in sorted(grp["elements"]):
        egrp = grp[f"elements/{name}"]
        elements.append(PathElement(
            points=egrp["points"][()],
            closed=bool(egrp.attrs["closed"]),
            role=str(egrp.attrs["role"]),
            power_mw=(float(egrp.attrs["power_mw"])
                      if "power_mw" in egrp.attrs else None),
            speed_um_s=(float(egrp.attrs["speed_um_s"])
                        if "speed_um_s" in egrp.attrs else None),
            meta=json.loads(egrp.attrs.get("meta", "{}")),
        ))
    for row in grp["hatches"][()]:
        elements.append(PathElement(points=row.reshape(2, 3),
                                    closed=False, role=ROLE_INFILL))

    contours = None
    if "contours" in grp:
        polys = []
        for pname in sorted(grp["contours"]):
            pgrp = grp[f"contours/{pname}"]
            holes = [pgrp[k][()] for k in sorted(pgrp)
                     if k.startswith("interior")]
            polys.append(Polygon(pgrp["exterior"][()], holes))
        contours = MultiPolygon(polys)

    return ElementGroup(
        kind=str(grp.attrs["kind"]),
        elements=elements,
        z_um=float(grp.attrs["z_um"]) if "z_um" in grp.attrs else None,
        contours=contours,
        meta=json.loads(grp.attrs.get("meta", "{}")),
    )


def iter_groups(path: str | Path) -> Iterator[ElementGroup]:
    """Stream groups one by one — constant memory even for huge jobs."""
    with h5py.File(path, "r") as f:
        for name in sorted(f["groups"]):
            yield _read_group(f[f"groups/{name}"])


def load_job(path: str | Path) -> ToolpathJob:
    params = read_params(path)
    with h5py.File(path, "r") as f:
        source = str(f["metadata"].attrs.get("source_file", ""))
        recipe = json.loads(f["metadata"].attrs.get("recipe", "[]"))
        extra = json.loads(f["metadata"].attrs.get("extra", "{}"))
    return ToolpathJob(params=params, groups=list(iter_groups(path)),
                       source_file=source, recipe=recipe, meta=extra)
