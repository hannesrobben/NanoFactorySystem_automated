"""Expected printing time of layer programs (T28)."""
import pytest

from nanofactorysystem.time_estimate import TimeEstimate, estimate_program_s, format_duration


def test_linear_moves_take_length_over_speed():
    program = "\n".join([
        "' comment LINEAR X100",
        "ABSOLUTE",
        "LINEAR X0 Y0 Z20 F2",   # start position: unknown before, takes no time
        "LINEAR X2",              # 2 mm at 2 mm/s
        "LINEAR X2 Y1.5 F0.5",    # 1.5 mm at 0.5 mm/s
    ])
    assert estimate_program_s(program) == pytest.approx(1.0 + 3.0)


def test_rapid_default_speed_incremental_and_dwell():
    program = "\n".join([
        "LINEAR X0 Y0 Z0 F1",
        "RAPID X10",              # 10 mm at the rapid speed (10 mm/s)
        "F 5",                    # default speed, also for RAPID
        "RAPID X0",               # 10 mm at 5 mm/s
        "INCREMENTAL",
        "LINEAR Y1",              # 1 mm at 5 mm/s (F statement is modal)
        "DWELL 0.250",
    ])
    assert estimate_program_s(program) == pytest.approx(1.0 + 2.0 + 0.2 + 0.25)


def test_galvo_and_stage_add_up():
    program = "\n".join(["LINEAR X1 Y1 Z0 A0 B0 F1", "LINEAR A0.003 B0.004"])  # 5 um at 1 mm/s
    assert estimate_program_s(program) == pytest.approx(0.005)


def test_time_estimate_record():
    estimate = TimeEstimate(5.0, {"a": [6.0, 7.5], "b": [5.0]})
    assert estimate.total_s == 18.5 and estimate.structure_s("a") == 13.5
    assert TimeEstimate.from_dict(estimate.to_dict()) == estimate
    assert [format_duration(s) for s in (12, 185, 3720, None)] == ["12 s", "3 min 05 s", "1 h 02 min", "-"]
