# optimizer.py
"""Path optimizer on the Toolpath-IR.

Goal: minimize *print time*, not travel distance — the cost function is
timing.estimate_toolpath. Because short moves live in the triangular part
of the velocity profile, two short travels cost more than one long travel
of the same total length; a pure distance heuristic would optimize the
wrong thing (docs/03 §3).

Rules per ElementGroup (docs/01 §6):
  * role != "infill" (shell, contour): the element ORDER is preserved
    (outer -> inner matters for shrinkage and attachment). Closed rings
    have no natural start point, so the start is rotated to the vertex
    closest to the current laser position — free savings, zero risk.
  * role == "infill": elements are freely permuted and may be reversed.
    Greedy nearest-endpoint: from the current position, jump to the closest
    available start point, where every open element offers two candidate
    starts (its two ends). Implemented with a cKDTree over all 2N endpoints
    and a used-mask (k-doubling query, since KD trees don't support
    deletion).

Greedy is O(N log N) and typically recovers 70–95 % of the possible travel
savings on raster-like paths; a 2-opt refinement pass is a documented
future extension, not a prerequisite.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, replace

import numpy as np
from scipy.spatial import cKDTree

from .timing import MotionParameters, TimeEstimate, estimate_toolpath
from .toolpath import ElementGroup, PathElement, ToolpathJob, ROLE_INFILL

log = logging.getLogger(__name__)


@dataclass
class OptimizationResult:
    job: ToolpathJob
    time_before: TimeEstimate
    time_after: TimeEstimate
    wall_time_s: float

    @property
    def improvement_pct(self) -> float:
        t0 = self.time_before.total_s
        return 100.0 * (t0 - self.time_after.total_s) / t0 if t0 else 0.0

    def __str__(self) -> str:
        return (
            f"optimized in {self.wall_time_s:.2f} s: "
            f"{self.time_before.total_s:.2f} s -> "
            f"{self.time_after.total_s:.2f} s "
            f"({self.improvement_pct:.1f} % faster; travel "
            f"{self.time_before.travel_s:.2f} s -> "
            f"{self.time_after.travel_s:.2f} s)"
        )


# --------------------------------------------------------------------------
# building blocks
# --------------------------------------------------------------------------

def _rotate_ring_start(el: PathElement, pos: np.ndarray) -> PathElement:
    """Rotate a closed ring so it starts at the vertex nearest to pos."""
    d2 = np.sum((el.points - pos) ** 2, axis=1)
    i = int(np.argmin(d2))
    return el.with_start_index(i) if i else el


def _greedy_order(elements: list[PathElement],
                  pos: np.ndarray) -> tuple[list[PathElement], np.ndarray]:
    """Greedy nearest-endpoint ordering of open elements (may reverse them).

    Endpoint layout: candidate 2i   = element i forward  (start = points[0])
                     candidate 2i+1 = element i reversed (start = points[-1])
    """
    n = len(elements)
    if n == 0:
        return [], pos
    if n == 1:
        el = elements[0]
        # still pick the cheaper orientation
        if (np.linalg.norm(el.points[-1] - pos)
                < np.linalg.norm(el.points[0] - pos)):
            el = el.reversed()
        return [el], el.end

    starts = np.empty((2 * n, 3), dtype=np.float64)
    for i, el in enumerate(elements):
        starts[2 * i] = el.points[0]
        starts[2 * i + 1] = el.points[-1]
    tree = cKDTree(starts)
    used = np.zeros(n, dtype=bool)

    ordered: list[PathElement] = []
    for _ in range(n):
        # k-doubling query: KD trees can't delete, so skip used candidates
        k = 2
        chosen = -1
        while chosen < 0:
            k = min(k * 2, 2 * n)
            dist, idx = tree.query(pos, k=k)
            for j in np.atleast_1d(idx):
                if not used[j // 2]:
                    chosen = int(j)
                    break
            if k >= 2 * n and chosen < 0:
                raise RuntimeError("greedy walk ran out of candidates")

        i, rev = chosen // 2, chosen % 2
        el = elements[i].reversed() if rev else elements[i]
        used[i] = True
        ordered.append(el)
        pos = el.end
    return ordered, pos


def optimize_group(group: ElementGroup,
                   start_pos: np.ndarray | None = None
                   ) -> tuple[ElementGroup, np.ndarray]:
    """Optimize one group; returns (new group, final laser position)."""
    if start_pos is None:
        start_pos = (group.elements[0].start.copy() if group.elements
                     else np.zeros(3))
    pos = np.asarray(start_pos, dtype=np.float64)

    fixed = [e for e in group.elements if e.role != ROLE_INFILL]
    infill = [e for e in group.elements if e.role == ROLE_INFILL]

    ordered: list[PathElement] = []
    for el in fixed:  # order preserved; rings get a free start rotation
        el = _rotate_ring_start(el, pos) if el.closed else el
        ordered.append(el)
        pos = el.end

    greedy, pos = _greedy_order(infill, pos)
    ordered.extend(greedy)

    return replace(group, elements=ordered), pos


def optimize_job(job: ToolpathJob,
                 motion: MotionParameters | None = None,
                 start_pos: np.ndarray | None = None) -> OptimizationResult:
    """Optimize all groups of a job, chaining the laser position across
    groups (the end of layer i is the start situation of layer i+1)."""
    motion = motion or MotionParameters()
    t_wall = time.perf_counter()
    before = estimate_toolpath(job, motion, start_pos)

    pos = (np.asarray(start_pos, dtype=np.float64)
           if start_pos is not None else None)
    new_groups: list[ElementGroup] = []
    for group in job.groups:
        new_group, pos = optimize_group(group, pos)
        new_groups.append(new_group)

    new_job = replace(job, groups=new_groups,
                      meta={**job.meta, "optimized": True})
    after = estimate_toolpath(new_job, motion, start_pos)
    result = OptimizationResult(job=new_job, time_before=before,
                                time_after=after,
                                wall_time_s=time.perf_counter() - t_wall)
    new_job.meta["optimizer"] = {
        "time_before_s": round(before.total_s, 4),
        "time_after_s": round(after.total_s, 4),
        "improvement_pct": round(result.improvement_pct, 2),
    }
    log.info("%s", result)
    return result
