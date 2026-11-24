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
