"""Tests for splitting too long AeroBasic programs (aerobasic/programs/split.py, T125)."""
import pytest

from nanofactorysystem.aerobasic.programs.split import (MAX_PROGRAM_LINES, ProgramSplitError, count_lines,
                                                        plan_split, split_lines, split_program_file)

IFOV_HEADER = [
    "' Created on 2026-11-21 by (AeroBasicProgram)",
    "LINEAR X0.5000000000 Y-25.0000000000",
    "LOOKAHEAD FAST",
    "CRITICAL START",
    "ABSOLUTE",
    "VELOCITY ON",
    "IFOV OFF",
    "GALVO LASEROVERRIDE A AUTO",
    "IFOV AXISPAIR 0, A, X",
    "IFOV AXISPAIR 1, B, Y",
    "$AO[0].A=1.6328611001410334",
    "F5",
    "AF5",
    "BF5",
    "ZF1",
    "GALVO ROTATION A -0.600000",
    "ABSOLUTE",
    "RAPID X0.5000000000 Y-25.0000000000 Z25.3292031647",
    "RAPID A0.0000000000 B0.0000000000",
    "IFOV ON",
]
IFOV_FOOTER = ["CRITICAL END", "IFOV OFF", "ENCODER OUT X OFF", "ENCODER OUT Y OFF", "END PROGRAM"]


def ifov_program(n_segments):
    """ HeightMap_IFOV-like layer: header, RAPID/LINEAR pairs on the galvo axes, footer. """

    body = []
    for i in range(n_segments):
        body += [f"RAPID A{i * 0.001:.10f} B-1.0238750000", f"LINEAR A{i * 0.001 + 0.0005:.10f} B-1.0238750000"]
    return IFOV_HEADER + body + IFOV_FOOTER, body


def gated_program(n_segments):
    """ Rectangle-like layer (IFOV off): explicit laser gate, moves that omit axes, F words. """

    lines = ["' Created on 2026-11-22 by (AeroBasicProgram)", "LINEAR X1.3100000000 Y19.5000000000",
             "LINEAR Z20.0000000000"]
    for i in range(n_segments):
        x = 1.305 + 0.001 * i
        lines += [f"LINEAR X{x:.10f} Y17.4950000000 Z20.0000000000 F1.000000",
                  "LINEAR Y19.4950000000 F1.000000",
                  "GALVO LASEROVERRIDE A ON",
                  "LINEAR Y19.5050000000 F2.000000",
                  "GALVO LASEROVERRIDE A OFF"]
    return lines + ["END PROGRAM"]


def test_short_program_is_not_split():
    lines, _ = ifov_program(10)

    assert plan_split(lines, 1000).cuts == []
    assert split_lines(lines, 1000) == [lines]


def test_ifov_program_parts_repeat_header_and_footer():
    lines, body = ifov_program(500)

    parts = split_lines(lines, 200, source="layer.txt")

    assert len(parts) > 1
    assert all(len(part) <= 200 for part in parts)
    assert all(part[0].startswith("' Part") and "layer.txt" in part[0] for part in parts)
    assert all(part[1:1 + len(IFOV_HEADER)] == IFOV_HEADER for part in parts)
    assert all(part[-len(IFOV_FOOTER):] == IFOV_FOOTER for part in parts)
    # The bodies of the parts are the original body, every later part starts with a RAPID (laser off)
    bodies = [part[1 + len(IFOV_HEADER):-len(IFOV_FOOTER)] for part in parts]
    assert sum(bodies, []) == body
    assert all(b[0].startswith("RAPID") for b in bodies[1:])


def test_gated_program_is_cut_with_the_laser_off_at_an_absolute_position():
    lines = gated_program(100)

    parts = split_lines(lines, 120)

    assert len(parts) > 1 and all(len(part) <= 120 for part in parts)
    for part in parts[1:]:
        # Replayed feed rate of the last move before the cut, then a move naming X, Y and Z
        feed = part[1]
        assert feed == "F2.000000"
        first_move = part[2]
        assert first_move.startswith("LINEAR X") and " Y" in first_move and " Z" in first_move
        # The laser is off at the start of every part: the first gate line switches it on
        gates = [line for line in part if "LASEROVERRIDE" in line]
        assert gates[0].endswith("ON")
    # The footer (after the last move) closes the laser gate in every part
    footer = ["GALVO LASEROVERRIDE A OFF", "END PROGRAM"]
    assert all(part[-2:] == footer for part in parts)
    rebuilt = parts[0][1:-2] + sum((part[2:-2] for part in parts[1:]), [])
    assert rebuilt == lines[:-2]


def test_power_set_in_the_body_is_replayed():
    lines, body = ifov_program(300)
    lines.insert(len(IFOV_HEADER) + 10, "$AO[0].A=2.5")

    parts = split_lines(lines, 150)

    assert all(len(part) <= 150 for part in parts)
    assert all("$AO[0].A=2.5" in part for part in parts[1:])


def test_long_laser_on_run_cannot_be_split():
    # One LINEAR after another with IFOV laser gating AUTO: there is no RAPID to cut at
    lines = IFOV_HEADER + [f"LINEAR A{i * 0.001:.10f} B0.0" for i in range(500)] + IFOV_FOOTER

    with pytest.raises(ProgramSplitError, match="No place to cut"):
        plan_split(lines, 200)


def test_incremental_program_is_refused():
    lines, _ = ifov_program(500)
    lines.insert(5, "INCREMENTAL")

    with pytest.raises(ProgramSplitError, match="incremental"):
        plan_split(lines, 200)


def test_too_long_header_is_refused():
    lines, _ = ifov_program(50)

    with pytest.raises(ProgramSplitError, match="Header"):
        plan_split(lines, 30)


def test_split_program_file_and_count_lines(tmp_path):
    lines, _ = ifov_program(500)
    path = tmp_path / "program_doe.070.txt"
    path.write_text("\n".join(lines) + "\n")

    assert count_lines(path) == len(lines)
    parts = split_program_file(path, 200)

    assert len(parts) > 1
    assert parts[0] == tmp_path / "split" / f"program_doe.070.part1of{len(parts)}.txt"
    assert all(count_lines(p) <= 200 for p in parts)
    # A short program is returned unchanged and nothing is written
    assert split_program_file(path, len(lines)) == [path]


def test_default_limit():
    assert MAX_PROGRAM_LINES == 80_000
