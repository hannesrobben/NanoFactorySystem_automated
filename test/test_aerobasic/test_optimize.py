"""Tests for the program optimiser (T130): shorter programs, same exposed path within the precision."""
import math
import re
from pathlib import Path

import pytest

from nanofactorysystem.aerobasic.programs.optimize import format_number, optimize_file, optimize_lines

GOLDEN = Path(__file__).parents[1] / "golden"
AXES = "XYZAB"
_MOVE = re.compile(r"^(RAPID|LINEAR|G0|G1)\b(.*)$", re.IGNORECASE)


def exposures(lines: list[str]) -> list:
    """ Exposed segments of a program in all axes X, Y, Z, A, B, with power and feed rate.

    A small reference interpreter (independent of the optimiser and of the dummy controller, whose
    exposure model knows only X/Y/Z with the gate ON): the laser exposes during LINEAR moves while
    ``GALVO LASEROVERRIDE`` is ON or AUTO; consecutive collinear segments are joined.
    """

    position = {axis: 0.0 for axis in AXES}
    absolute, laser, power, feed = True, False, None, None
    segments = []
    for line in lines:
        text = line.strip().upper()
        if text in ("ABSOLUTE", "INCREMENTAL"):
            absolute = text == "ABSOLUTE"
        elif text.startswith("GALVO LASEROVERRIDE"):
            laser = text.split()[-1] in ("ON", "AUTO")
        elif text.startswith("$AO"):
            power = text
        elif re.fullmatch(r"F-?[\d.]+", text):
            feed = float(text[1:])
        elif match := _MOVE.match(text):
            start = dict(position)
            for axis, value in re.findall(r"([A-Z])\s*(-?[\d.]+)", match.group(2)):
                if axis == "F":
                    if match.group(1) in ("LINEAR", "G1"):
                        feed = float(value)
                else:
                    position[axis] = float(value) if absolute else position[axis] + float(value)
            if laser and match.group(1) in ("LINEAR", "G1") and position != start:
                segments.append(([start[a] for a in AXES], [position[a] for a in AXES], power, feed))
    joined = []
    for start, end, p, f in segments:
        if joined:
            s0, e0, p0, f0 = joined[-1]
            d1 = [b - a for a, b in zip(s0, e0)]
            d2 = [b - a for a, b in zip(start, end)]
            n1, n2 = math.hypot(*d1), math.hypot(*d2)
            cos = sum(a * b for a, b in zip(d1, d2)) / (n1 * n2)
            if (p, f) == (p0, f0) and math.dist(e0, start) < 1e-12 and cos > 1 - 1e-9:
                joined[-1] = (s0, end, p, f)
                continue
        joined.append((start, end, p, f))
    return joined


def assert_same_exposures(original: list[str], optimized: list[str], tolerance: float = 1e-5):
    before, after = exposures(original), exposures(optimized)
    assert len(before) == len(after) > 0
    for (s1, e1, p1, f1), (s2, e2, p2, f2) in zip(before, after):
        assert (p1, f1) == (p2, f2) and math.dist(s1, s2) <= tolerance and math.dist(e1, e2) <= tolerance


def test_format_number():
    assert format_number(1.0, 5) == "1"
    assert format_number(-1.0238750000, 5) == "-1.02388"
    assert format_number(-0.000001, 5) == "0"
    assert format_number(0.1, 5) == "0.1"


def test_modal_words_and_collinear_moves():
    lines = ["ABSOLUTE", "F5", "GALVO LASEROVERRIDE A ON",
             "LINEAR X0.0000000000 Y0.0000000000 F2.000000", "LINEAR X1.0000000000 Y0.0000000000 F2.000000",
             "LINEAR X2.0000000000 Y0.0000000000 F2.000000", "LINEAR X2.0000000000 Y1.0000000000 F2.000000",
             "F2", "LINEAR X2.0000000000 Y1.0000000000"]

    out, stats = optimize_lines(lines)

    assert out == ["ABSOLUTE", "F5", "GALVO LASEROVERRIDE A ON", "LINEAR X0 Y0 F2", "LINEAR X2", "LINEAR Y1"]
    assert stats.merged_moves == 1 and stats.dropped_moves == 1 and stats.lines_after == 6
    assert_same_exposures(lines, out)


def test_lines_with_variables_and_unknown_commands_are_kept_and_reset_knowledge():
    lines = ["ABSOLUTE", "LINEAR X1 Y1 F1", "LINEAR X$x Y1", "LINEAR X1 Y1", "HOME X", "LINEAR X1 Y1 F1"]

    out, _ = optimize_lines(lines)

    # After the variable move X is unknown, so "X1" is written again; after HOME everything is unknown
    assert out == ["ABSOLUTE", "LINEAR X1 Y1 F1", "LINEAR X$x Y1", "LINEAR X1", "HOME X", "LINEAR X1 Y1 F1"]


def test_moves_across_a_laser_switch_are_not_merged():
    lines = ["ABSOLUTE", "LINEAR X0 Y0 F1", "LINEAR X1 Y0", "GALVO LASEROVERRIDE A ON", "LINEAR X2 Y0", "LINEAR X3 Y0"]

    out, stats = optimize_lines(lines)

    assert out == ["ABSOLUTE", "LINEAR X0 Y0 F1", "LINEAR X1", "GALVO LASEROVERRIDE A ON", "LINEAR X3"]
    assert stats.merged_moves == 1


def test_incremental_moves():
    lines = ["INCREMENTAL", "LINEAR X0.0000000000 Y0.5000000000 F1", "LINEAR X0 Y0", "ABSOLUTE"]

    out, stats = optimize_lines(lines)

    assert out == ["INCREMENTAL", "LINEAR Y0.5 F1", "ABSOLUTE"] and stats.dropped_moves == 1


@pytest.mark.parametrize("name", ["rectangle3d_default.txt", "binary_grating_ifov_63x.txt", "qrcode_default.txt"])
def test_golden_programs_expose_the_same_path(name, tmp_path):
    lines = (GOLDEN / name).read_text().splitlines()

    out, stats = optimize_lines(lines)

    assert stats.bytes_after < stats.bytes_before and stats.lines_after <= stats.lines_before
    assert_same_exposures(lines, out)
    path = tmp_path / name
    path.write_text("\n".join(lines) + "\n")
    assert optimize_file(path).lines_after == stats.lines_after
    assert (tmp_path / f"{Path(name).stem}.opt.txt").read_text().splitlines() == out
