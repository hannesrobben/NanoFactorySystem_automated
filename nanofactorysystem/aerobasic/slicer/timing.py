# timing.py
"""Print time estimation based on a trapezoidal velocity profile.

Units: um, s, um/s, um/s^2 throughout (see docs/03).

Model per move (start and end at rest):
    d_acc = v^2 / (2a)
    L >= v^2/a  (trapezoid):  t = L/v + v/a
    L <  v^2/a  (triangle):   t = 2*sqrt(L/a),  v_peak = sqrt(a*L)

The triangle case dominates TPP hatching: at v=10_000 um/s and
a=1e6 um/s^2 any segment shorter than 100 um never reaches full speed —
a plain L/v model would systematically underestimate print time.

This module is also the cost function of the path optimizer:
travel *time* (not distance) is what gets minimized.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np


# --------------------------------------------------------------------------
# parameters & result containers
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class MotionParameters:
    """Machine motion model.

    Attributes:
        mark_speed_um_s: Velocity while the laser writes.
        travel_speed_um_s: Velocity of laser-off repositioning moves.
        acceleration_um_s2: Acceleration/deceleration (assumed symmetric).
        laser_switch_s: Overhead per written segment (laser on + off).
        z_speed_um_s: Velocity of layer-change moves.
        z_settle_s: Settle/wait time after each z move.
        corner_slowdown: Multiplier >= 1 on marking time of polylines to
            account for cornering (1.0 = ignore corners).
    """
    mark_speed_um_s: float = 10_000.0
    travel_speed_um_s: float = 50_000.0
    acceleration_um_s2: float = 1.0e6
    laser_switch_s: float = 0.002
    z_speed_um_s: float = 5_000.0
    z_settle_s: float = 0.05
    corner_slowdown: float = 1.0

    def __post_init__(self) -> None:
        for name in ("mark_speed_um_s", "travel_speed_um_s",
                     "acceleration_um_s2", "z_speed_um_s"):
            if getattr(self, name) <= 0:
                raise ValueError(f"{name} must be > 0")
        if self.corner_slowdown < 1.0:
            raise ValueError("corner_slowdown must be >= 1")


@dataclass
class TimeEstimate:
    """Breakdown of estimated print time (seconds)."""
    mark_s: float = 0.0
    travel_s: float = 0.0
    switch_s: float = 0.0
    z_s: float = 0.0
    mark_length_um: float = 0.0
    travel_length_um: float = 0.0
    n_segments: int = 0

    @property
    def total_s(self) -> float:
        return self.mark_s + self.travel_s + self.switch_s + self.z_s

    def __iadd__(self, other: "TimeEstimate") -> "TimeEstimate":
        self.mark_s += other.mark_s
        self.travel_s += other.travel_s
        self.switch_s += other.switch_s
        self.z_s += other.z_s
        self.mark_length_um += other.mark_length_um
        self.travel_length_um += other.travel_length_um
        self.n_segments += other.n_segments
        return self

    def __str__(self) -> str:
        t = self.total_s
        def pct(x: float) -> str:
            return f"{100 * x / t:.0f}%" if t else "-"
        return (
            f"total {t:.2f} s  ("
            f"mark {self.mark_s:.2f} s [{pct(self.mark_s)}], "
            f"travel {self.travel_s:.2f} s [{pct(self.travel_s)}], "
            f"switch {self.switch_s:.2f} s [{pct(self.switch_s)}], "
            f"z {self.z_s:.2f} s [{pct(self.z_s)}]; "
            f"{self.n_segments} segments, "
            f"mark {self.mark_length_um / 1000:.2f} mm, "
            f"travel {self.travel_length_um / 1000:.2f} mm)"
        )


# --------------------------------------------------------------------------
# motion primitives
# --------------------------------------------------------------------------

def move_time_s(distance_um: float, v_um_s: float, a_um_s2: float) -> float:
    """Time for one move from rest to rest over distance_um."""
    L = abs(float(distance_um))
    if L == 0.0:
        return 0.0
    if L >= v_um_s * v_um_s / a_um_s2:
        return L / v_um_s + v_um_s / a_um_s2          # trapezoid
    return 2.0 * math.sqrt(L / a_um_s2)               # triangle


def _segment_lengths(hatches: np.ndarray) -> np.ndarray:
    """(N, 4) or (N, 6) segment array -> lengths (N,)."""
    h = np.asarray(hatches, dtype=np.float64)
    if h.size == 0:
        return np.zeros(0)
    dim = h.shape[1] // 2
    return np.linalg.norm(h[:, dim:] - h[:, :dim], axis=1)


def _travel_lengths(hatches: np.ndarray) -> np.ndarray:
    """Gaps between segment end i and segment start i+1, in stored order."""
    h = np.asarray(hatches, dtype=np.float64)
    if h.shape[0] < 2:
        return np.zeros(0)
    dim = h.shape[1] // 2
    return np.linalg.norm(h[1:, :dim] - h[:-1, dim:], axis=1)


def _moves_time_s(lengths: np.ndarray, v: float, a: float) -> float:
    """Vectorized sum of move_time_s over many rest-to-rest moves."""
    if lengths.size == 0:
        return 0.0
    crit = v * v / a
    tri = lengths < crit
    t = np.empty_like(lengths)
    t[tri] = 2.0 * np.sqrt(lengths[tri] / a)
    t[~tri] = lengths[~tri] / v + v / a
    return float(t.sum())


# --------------------------------------------------------------------------
# estimation on job pieces
# --------------------------------------------------------------------------

def estimate_hatches(hatches: np.ndarray, motion: MotionParameters,
                     mark_speed_um_s: float | None = None) -> TimeEstimate:
    """Estimate for a set of straight segments in their stored order.

    Each segment is one rest-to-rest marking move; gaps between consecutive
    segments are laser-off travel moves. Reordering the segments changes the
    travel term — this is exactly what the path optimizer minimizes.
    """
    v_mark = mark_speed_um_s or motion.mark_speed_um_s
    seg = _segment_lengths(hatches)
    trav = _travel_lengths(hatches)
    return TimeEstimate(
        mark_s=_moves_time_s(seg, v_mark, motion.acceleration_um_s2),
        travel_s=_moves_time_s(trav, motion.travel_speed_um_s,
                               motion.acceleration_um_s2),
        switch_s=len(seg) * motion.laser_switch_s,
        mark_length_um=float(seg.sum()),
        travel_length_um=float(trav.sum()),
        n_segments=int(len(seg)),
    )


def estimate_polyline(points: np.ndarray, motion: MotionParameters,
                      closed: bool = False,
                      mark_speed_um_s: float | None = None) -> TimeEstimate:
    """Estimate for one continuous polyline (e.g. a contour ring).

    Modeled as a single rest-to-rest move over the total path length —
    the laser stays on, no per-vertex switching. Cornering losses are
    covered by motion.corner_slowdown (>= 1).
    """
    v_mark = mark_speed_um_s or motion.mark_speed_um_s
    p = np.asarray(points, dtype=np.float64)
    if p.ndim != 2 or p.shape[0] < 2:
        return TimeEstimate()
    L = float(np.linalg.norm(np.diff(p, axis=0), axis=1).sum())
    if closed and not np.allclose(p[0], p[-1]):
        L += float(np.linalg.norm(p[-1] - p[0]))
    t = move_time_s(L, v_mark, motion.acceleration_um_s2)
    return TimeEstimate(
        mark_s=t * motion.corner_slowdown,
        switch_s=motion.laser_switch_s,
        mark_length_um=L,
        n_segments=1,
    )


# --------------------------------------------------------------------------
# estimation on the Toolpath-IR
# --------------------------------------------------------------------------

def estimate_element(element, motion: MotionParameters,
                     default_speed_um_s: float | None = None) -> TimeEstimate:
    """Marking + switch time for one PathElement (no travel)."""
    v = element.speed_um_s or default_speed_um_s or motion.mark_speed_um_s
    L = element.length_um
    t = move_time_s(L, v, motion.acceleration_um_s2)
    if element.closed or element.n_vertices > 2:
        t *= motion.corner_slowdown
    return TimeEstimate(mark_s=t, switch_s=motion.laser_switch_s,
                        mark_length_um=L, n_segments=1)


def estimate_group(group, motion: MotionParameters,
                   default_speed_um_s: float | None = None,
                   start_pos: np.ndarray | None = None,
                   ) -> tuple[TimeEstimate, np.ndarray]:
    """Estimate one ElementGroup in its stored element order.

    Travel between elements = 3D euclidean distance at travel speed.
    Returns (estimate, final laser position) so groups can be chained.
    The element order is exactly what the optimizer permutes — this
    function IS its cost function.
    """
    est = TimeEstimate()
    pos = start_pos
    for el in group.elements:
        if pos is not None:
            delta = el.start - pos
            d_xy = float(np.hypot(delta[0], delta[1]))
            d_z = abs(float(delta[2]))
            est.travel_s += move_time_s(d_xy, motion.travel_speed_um_s,
                                        motion.acceleration_um_s2)
            est.z_s += move_time_s(d_z, motion.z_speed_um_s,
                                   motion.acceleration_um_s2)
            est.travel_length_um += d_xy + d_z
        est += estimate_element(el, motion, default_speed_um_s)
        pos = el.end
    if pos is None:
        pos = start_pos if start_pos is not None else np.zeros(3)
    return est, pos


def estimate_toolpath(job, motion: MotionParameters | None = None,
                      start_pos: np.ndarray | None = None) -> TimeEstimate:
    """Estimate a full ToolpathJob.

    Default marking speed comes from the job's laser parameters; per-element
    overrides win. Travel is decomposed into xy (at travel_speed) and z
    (at z_speed) uniformly by estimate_group; group transitions add one
    settle time.
    """
    motion = motion or MotionParameters()
    v_default = job.params.laser.scan_speed_um_s
    total = TimeEstimate()
    pos = start_pos
    for i, group in enumerate(job.groups):
        if i > 0:
            total.z_s += motion.z_settle_s
        est, pos = estimate_group(group, motion, v_default, pos)
        total += est
    return total
