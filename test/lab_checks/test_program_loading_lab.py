"""Tests for the hardware-free helpers of mains/lab_checks/program_loading_lab.py (T129)."""
import importlib.util
import json
import math
import re
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "mains" / "lab_checks" / "program_loading_lab.py"
pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="the lab script uses the Windows API")


@pytest.fixture(scope="module")
def lab():
    spec = importlib.util.spec_from_file_location("program_loading_lab", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_synthetic_program_is_dry_and_has_the_requested_length(lab):
    lines = lab.synthetic_program(1000)

    assert len(lines) == 1000 and lines[-1] == "END PROGRAM"
    gates = [line for line in lines if "LASEROVERRIDE" in line]
    assert gates and all(line.endswith("OFF") for line in gates)
    moves = [line for line in lines if re.match(r"(RAPID|LINEAR) ", line)]
    # Only the galvo axes A and B move, within +-0.05 mm
    assert all(set(re.findall(r"\b([A-Z])-?\d", line[6:])) <= {"A", "B"} for line in moves)
    values = [float(v) for line in moves for v in re.findall(r"[AB](-?[\d.]+)", line)]
    assert max(map(abs, values)) <= 0.05 + 1e-9
    assert not any(line.startswith("$AO") for line in lines)


def test_synthetic_number_formats(lab):
    long = lab.synthetic_program(100, decimals=10)
    short = lab.synthetic_program(100, decimals=5, trim=True)

    assert len(long) == len(short) == 100
    assert sum(map(len, short)) < sum(map(len, long))
    assert "RAPID A0 B0" in short


def test_truncated_program_keeps_header_and_footer(lab):
    footer = ["CRITICAL END", "IFOV OFF", "END PROGRAM"]
    lines = ["' header", "LOOKAHEAD FAST", "CRITICAL START"] + [f"LINEAR A{i}" for i in range(100)] + footer

    part = lab.truncated_program(lines, 20)

    assert len(part) == 20 and part[:3] == lines[:3] and part[-3:] == footer
    assert lab.truncated_program(lines, 10_000) == lines


def test_memory_queries(lab):
    memory = lab.system_memory()
    own = lab.process_memory()

    assert memory["total_gb"] > 0 and 0 <= memory["available_gb"] <= memory["total_gb"]
    assert own["peak_private_gb"] >= own["private_gb"] > 0


def test_budget_uses_the_largest_measured_memory_per_line(lab, tmp_path):
    session = lab.Session(tmp_path)
    assert lab.kb_per_line_estimate(session) == lab.DEFAULT_KB_PER_LINE

    session.record("ladder", {"ok": True, "kb_per_line": 20.0})
    session.record("ladder", {"ok": True, "kb_per_line": 12.0})
    session.record("ladder", {"ok": False, "kb_per_line": None})

    assert lab.kb_per_line_estimate(session) == 20.0
    assert lab.fits_budget(session, 1, 1e6)[0]
    assert not lab.fits_budget(session, 10**9, 1.0)[0]


def test_worker_result_reads_the_last_json_line(lab):
    class Proc:
        returncode = 0

        def communicate(self, timeout=None):
            return "noise\n" + json.dumps({"ok": True, "load_s": 1.0}) + "\n", ""

    assert lab.worker_result(Proc()) == {"ok": True, "load_s": 1.0}


def test_real_header_variant_keeps_the_length_and_closes_the_critical_section(lab):
    lines = lab.synthetic_program(500, header_style="real")

    assert len(lines) == 500 and lines[-1] == "END PROGRAM"
    assert lines.index("CRITICAL START") < lines.index("CRITICAL END")
    assert all(mode in lines for mode in ("SECONDS", "METRIC", "LOOKAHEAD FAST"))
    with pytest.raises(ValueError):
        lab.synthetic_program(500, header_style="other")


def test_source_lines_of_a_compiled_program_come_from_the_pgm(lab, tmp_path):
    pgm = lab.write_program(tmp_path / "part.pgm", ["LINEAR A1", "LINEAR A2", "END PROGRAM"])
    ogm = tmp_path / "PART.OGM"
    ogm.write_bytes(bytes([0, 10]) * 50)  # binary content with many line breaks

    assert lab.source_line_count(pgm) == 3
    assert lab.source_line_count(ogm) == 3
    assert lab.compiled_file(pgm) == ogm
    assert lab.source_line_count(tmp_path / "alone.ogm") is None


def test_program_name_candidates(lab, tmp_path):
    names = lab.program_name_candidates(tmp_path / "part_1.ogm")

    assert names[0] == "part_1.ogm"
    assert {"part_1.pgm", "part_1", "PART_1.OGM"} <= set(names)
    assert len(names) == len(set(names))


def test_process_age_and_stale_a3200_processes(lab):
    import datetime
    now = datetime.datetime(2026, 11, 25, 9, 0, 0)

    assert lab.process_age_minutes("2026-11-25T08:30:00", now) == 30.0
    assert lab.process_age_minutes(None) is None and lab.process_age_minutes("garbage") is None
    rows = [{"name": "A3200AsciiInterface.exe", "pid": 1, "created": "x", "age_min": 1500.0},
            {"name": "A3200CommService.exe", "pid": 2, "created": "y", "age_min": 5.0},
            {"name": "python.exe", "pid": 3, "created": "z", "age_min": 9999.0}]
    assert lab.stale_a3200_processes(rows) == ["A3200AsciiInterface.exe (PID 1, started x)"]


def test_parse_axis_states(lab):
    data = " ".join(["1 1 10,5", "0 1 0", "1 0 -2.25", "1 1 0", "1 1 0"])

    states = lab.parse_axis_states(data)

    assert states["X"] == {"enabled": True, "homed": True, "position": 10.5}
    assert states["Y"]["enabled"] is False and states["Z"]["homed"] is False
    assert states["Z"]["position"] == -2.25


def test_reset_prototype_is_recognised(lab):
    header = "BOOL DLLENTRYDECLARATION A3200Reset(A3200Handle handle);\nBOOL A3200Other(int x);"

    assert re.search(lab.RESET_SIGNATURE, header)
    assert lab.prototype(header, "A3200Reset") == "BOOL DLLENTRYDECLARATION A3200Reset(A3200Handle handle);"
    assert lab.prototype(header, "A3200Missing") is None


# ------------------------------------------------------------------------------------- lab session 3 (T153)

GOLDEN_IFOV = Path(__file__).resolve().parents[1] / "golden" / "binary_grating_ifov_63x.txt"


def test_dry_layer_switches_the_laser_off_and_never_moves_z(lab):
    original = GOLDEN_IFOV.read_text().splitlines()
    assert lab.dry_problems(original)  # the generated program opens the gate, sets the power and moves Z

    dry, info = lab.dry_layer_lines(original, 10.0, -5.0)

    assert lab.dry_problems(dry) == []
    assert info["laser_gate_lines"] > 0 and info["analog_out_lines"] > 0 and info["z_words_removed"] > 0
    assert all(line.endswith("OFF") for line in dry if "LASEROVERRIDE" in line)
    assert all(line == "$AO[0].A=0" for line in dry if line.startswith("$AO"))
    # The stage pattern is kept and starts at the current position; the galvo lines are unchanged
    stage = [line for line in dry if line.startswith("RAPID X")]
    assert stage[0] == "RAPID X10.000000 Y-5.000000" and stage[1] == "RAPID X10.000000 Y-5.004000"
    galvo = [line for line in original if re.match(r"(RAPID|LINEAR) A", line)]
    assert galvo == [line for line in dry if re.match(r"(RAPID|LINEAR) A", line)]


@pytest.mark.parametrize("line", ["INCREMENTAL", "G91", "PSOCONTROL X ON", "LINEAR Z $dz F 0.1", "LINEAR X 1.0"])
def test_dry_layer_refuses_what_cannot_be_made_safe(lab, line):
    with pytest.raises(ValueError):
        lab.dry_layer_lines(["ABSOLUTE", line, "END PROGRAM"], 0.0, 0.0)


def test_dry_layer_parts_stay_dry(lab):
    from nanofactorysystem.aerobasic.programs.split import split_lines

    text = GOLDEN_IFOV.read_text()
    layer = text[text.index("' ==== layer 0 ===="):text.index("' ==== layer 1 ====")].splitlines()
    dry, _ = lab.dry_layer_lines(layer, 1.0, 2.0)

    parts = split_lines(dry, 70, source="layer0")  # header 45 + footer 6 lines

    assert len(parts) > 1 and all(lab.dry_problems(part) == [] for part in parts)


def test_read_block_takes_a_pasted_block(lab):
    answers = iter(["", "Pool min 530156K", "Used 124976K", "", "ignored"])

    assert lab.read_block("INtime", reader=lambda _: next(answers)) == "Pool min 530156K\nUsed 124976K"


def test_session_3_steps_are_registered(lab):
    assert {"ascii-names", "recover-blocked", "dotnet-build", "layer-dry"} <= set(lab.STEPS)


def test_axes_not_ready_lists_disabled_or_unhomed_axes(lab):
    ready = {"enabled": True, "homed": True, "position": 0.0}
    axes = {"X": ready, "Y": ready, "Z": {"enabled": False, "homed": False}, "A": ready,
            "B": {"enabled": True, "homed": False}}

    assert lab.axes_not_ready(axes) == ["Z (enabled=False, homed=False)", "B (enabled=True, homed=False)"]
    assert lab.axes_not_ready({a: ready for a in lab.AXES}) == []
    assert lab.axes_not_ready({}) == [f"{a} (enabled=None, homed=None)" for a in lab.AXES]


def test_decode_bits_names_the_task_mode_flags(lab):
    # absolute (bit 1), ramp mode rate (bit 3), velocity on (bit 5), wait auto (bit 30)
    value = (1 << 1) | (1 << 3) | (1 << 5) | (1 << 30)

    flags = lab.decode_bits(f"{value}", lab.TASK_MODE_BITS)

    assert flags["absolute"] and flags["ramp_mode_rate"] and flags["velocity_on"] and flags["wait_auto"]
    assert not flags["secondary_units"] and not flags["minutes"]
    assert lab.state_entry("TaskMode", f"{value}.0")["TaskMode"] == value
    assert lab.state_entry("TaskStatus2", "1")["status2"]["rotation_active"]
    assert lab.state_entry("AccelerationRate", "2000") == {"AccelerationRate": 2000.0}


def test_rotation_angle_of_an_a_only_move(lab):
    assert lab.rotation_angle_deg(0.05, 0.0) == 0.0
    assert lab.rotation_angle_deg(0.05, 0.05 * math.tan(math.radians(-0.6))) == pytest.approx(-0.6, abs=1e-3)
    assert lab.rotation_angle_deg(0.0, 0.0) is None


def test_state_programs_never_open_the_laser_gate_and_move_nothing(lab):
    golden = (Path(__file__).resolve().parents[1] / "golden" / "binary_grating_ifov_63x.txt").read_text().splitlines()
    for lines in (lab.STATE_SETTER, lab.STATE_NEUTRAL, lab.STATE_DEFAULT_SETUP):
        assert lines[-1] == "END PROGRAM"
        assert not [line for line in lines if re.match(r"(RAPID|LINEAR|MOVE|\$AO)", line)]
        assert all(line.endswith("OFF") for line in lines if "LASEROVERRIDE" in line)
    # every mode line of the setter appears in a generated IFOV layer program (gate AUTO written as OFF)
    for line in lab.STATE_SETTER[1:-2]:
        if "LASEROVERRIDE" not in line:
            assert any(g.strip().startswith(line.split(" -")[0]) for g in golden), line


@pytest.mark.parametrize("root", [r"C:\Users\Nanofactory\nfs_lab", r"C:\a", r"C:\Users\someone_with_a_long_name\nfs_lab"])
def test_padded_program_paths_have_the_requested_length(lab, root):
    for length in lab.PATH_LIMIT_LENGTHS:
        path = lab.padded_program_path(Path(root), length)
        assert len(str(path)) == length and path.suffix == ".pgm"
        assert all(len(part) <= 41 for part in path.parts)
    base = len(root) + 1 + len("plim_0.pgm")
    for length in range(base + 4, base + 90):                 # every remainder, incl. the one-character case
        assert len(str(lab.padded_program_path(Path(root), length))) == length
    with pytest.raises(ValueError):
        lab.padded_program_path(Path(root), 10)
