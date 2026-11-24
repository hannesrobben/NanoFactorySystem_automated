"""Tests for the hardware-free helpers of mains/lab_checks/program_loading_lab.py (T129)."""
import importlib.util
import json
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
