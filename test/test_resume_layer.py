"""Tests for continuing a stopped layer without exposing its printed part again (T170)."""
from pathlib import Path

import pytest

from nanofactorysystem.aerobasic.programs.split import split_program_file
from nanofactorysystem.resume_layer import (failure_point, layer_program_for_part, mark_layer_printed, plan_resume,
                                            write_resume_program)

HEADER = ["' Created on 2026-11-28 by (AeroBasicProgram)", "LINEAR X0.0000000000 Y19.0000000000",
          "' layer 69", "LOOKAHEAD FAST", "CRITICAL START", "ABSOLUTE", "GALVO LASEROVERRIDE A AUTO",
          "$AO[0].A=1.5441017413390339", "F5", "RAPID X0.0000000000 Y19.0000000000 Z25.3282578526",
          "RAPID A0.0000000000 B0.0000000000", "IFOV ON"]
FOOTER = ["CRITICAL END", "IFOV OFF", "END PROGRAM"]


def layer_program(columns=12, segments=5):
    """ Hatch lines along B, stepped along A (like HeightMap_IFOV with hatching X). """

    body = []
    for c in range(columns):
        a = -0.01 + c * 0.00025
        for s in range(segments):
            b0 = -0.5 + s * 0.1
            body += [f"RAPID A{a:.10f} B{b0:.10f}", f"LINEAR A{a:.10f} B{b0 + 0.05:.10f}"]
    return HEADER + body + FOOTER


def structure_record(name):
    from nanofactorysystem.storage import StructureRecord

    return StructureRecord(
        index=0, name=name, type="IFOV", grid_index=0, corner_position="", axes="XYZ", setup="IFOV_on",
        center_um=(0.0, 19000.0, 25300.0), reference_um=(0.0, 19000.0), power_mw=0.25, structure_class="x",
        config={}, layer_files=["a.000.txt", "a.001.txt"], program_file="a.txt", layer_order=-1,
        dhm_image_count=0)


def poll(state, line, task=1):
    return (f"[SUCCESS] '~STATUS ({task}, TaskMode) ({task}, TaskState) ({task}, TaskStatus0) ({task}, TaskStatus1) "
            f"({task}, TaskStatus2) ({task}, ProgramLineNumber)\\n' -> '2 {state} 0 0 0 {line}' <1.0 -> 1.1 ping=1ms>")


def load(stem, counter):
    return (f"[SUCCESS] 'PROGRAM 1 LOAD \"C:\\\\Users\\\\lab\\\\nfs_8b3a25_{counter:04d}_{stem}.pgm\"\\n' -> '' "
            f"<1.0 -> 1.1 ping=1ms>")


def test_failure_point_takes_the_last_load_and_the_line_of_the_error_state():
    log = "\n".join([
        "Commands:", load("program_s.069.part05of11", 56), poll(4, 900), poll(3, 79992),
        load("program_s.069.part06of11", 57), poll(4, 100), poll(4, 19150), poll(4, 20000, task=2),
        "[SUCCESS] '~STATUS (1, ProgramLineNumber)\\n' -> '5' <1.0 -> 1.1 ping=1ms>",
        poll(8, 19200), "[INVALID] 'ERRORDECODE 51, 5\\n' -> '' (Compiler Error) <1.0 -> 1.1 ping=1ms>",
    ])

    point = failure_point(log)

    assert (point.stem, point.task_id, point.last_line, point.error_line) == ("program_s.069.part06of11", 1,
                                                                              19200, 19200)
    assert failure_point(log, "program_s.069.part05of11").last_line == 79992
    with pytest.raises(ValueError, match="No PROGRAM LOAD"):
        failure_point(log, "program_s.070.part01of02")


def test_the_reported_part_line_maps_to_the_same_layer_line(tmp_path):
    lines = layer_program()
    path = tmp_path / "program_s.069.txt"
    path.write_text("\n".join(lines) + "\n")
    parts = split_program_file(path, max_lines=50)
    part_lines = parts[1].read_text().splitlines()

    first, last = len(HEADER) + 2, len(part_lines) - len(FOOTER)  # 1-based body lines of the part
    for reported in (first, first + 1, (first + last) // 2, last - 2):
        plan = plan_resume(lines, 2, len(parts), reported, max_lines=50)
        assert lines[plan.stop_index] == part_lines[reported - 1]
        assert plan.resume_index >= plan.stop_index + 2  # one margin line for a 0-based counter
        assert lines[plan.resume_index].startswith("RAPID A")
    # A line in the footer of the part: its whole body was written, the stop is its last body line
    footer_line = len(part_lines) - 1
    plan = plan_resume(lines, 2, len(parts), footer_line, max_lines=50)
    assert lines[plan.stop_index] == part_lines[-len(FOOTER) - 1]


def test_a_stop_in_the_header_of_a_part_continues_at_the_start_of_its_body(tmp_path):
    lines = layer_program()
    path = tmp_path / "program_s.069.txt"
    path.write_text("\n".join(lines) + "\n")
    parts = split_program_file(path, max_lines=50)
    first_body_line = parts[1].read_text().splitlines()[len(HEADER) + 1]

    plan = plan_resume(lines, 2, len(parts), 3, max_lines=50, margin_lines=0)

    assert lines[plan.resume_index] == first_body_line


def test_next_column_skips_the_rest_of_the_hatch_line():
    lines = layer_program()
    stop_line = len(HEADER) + 2 * 5 * 3 + 4  # column 3, third segment (RAPID), 1-based
    plan = plan_resume(lines, 1, 1, stop_line, max_lines=10_000, next_column=True)

    assert " A-0.0092500000 " in f" {lines[plan.stop_index]} "
    assert lines[plan.resume_index] == "RAPID A-0.0090000000 B-0.5000000000"  # first move of column 4


def test_resume_program_writes_exactly_the_lines_behind_the_resume_point(tmp_path):
    lines = layer_program(columns=40)
    plan = plan_resume(lines, 1, 1, 200, max_lines=10_000)

    program, parts = write_resume_program(lines, plan, tmp_path / "resume", "program_s.069.txt", max_lines=120)

    written = program.read_text().splitlines()
    assert written[1:1 + len(HEADER)] == HEADER and written[-len(FOOTER):] == FOOTER
    body = written[1 + len(HEADER):-len(FOOTER)]
    assert body == lines[plan.resume_index:plan.footer_start]  # power and feed are set in the header
    printed = set(range(plan.header_end, plan.stop_index + 1))
    assert printed.isdisjoint(range(plan.resume_index, plan.footer_start))
    assert len(parts) > 1 and all(len(p.read_text().splitlines()) <= 120 for p in parts)


def test_wrong_part_count_is_refused():
    with pytest.raises(ValueError, match="splits into 1 parts"):
        plan_resume(layer_program(), 6, 11, 100)


def test_layer_program_for_part(tmp_path):
    programs = tmp_path / "structures" / "surface_16bit" / "programs"
    programs.mkdir(parents=True)
    (programs / "program_surface_16bit.069.txt").write_text("END PROGRAM\n")

    path, k, n = layer_program_for_part(tmp_path, "program_surface_16bit.069.part06of11")

    assert path == programs / "program_surface_16bit.069.txt" and (k, n) == (6, 11)


def test_mark_layer_printed_lets_the_restart_skip_the_layer(tmp_path):
    from nanofactorysystem.storage import ExperimentRecord, ExperimentStore

    record = ExperimentRecord(
        uuid="0f0e0d0c-0000-4000-8000-000000000170", parameters={"setup": "IFOV_on", "drop_direction": "DOWN"},
        user={"key": "Test"}, objective={"key": "Zeiss 63x"}, system={"backend": "dummy"},
        software={"package_version": "0", "git_commit": "abc"})
    store = ExperimentStore.create(tmp_path / "exp", record)
    store.add_structure(structure_record("rect"))
    store.update_progress("rect", 1, "failed", error="axis fault")
    store.end_session("exception")

    mark_layer_printed(tmp_path / "exp", "rect", 1, "rest of layer 1 printed by hand")

    data = ExperimentStore.open(tmp_path / "exp").read()
    assert [(e["layer_id"], e["status"]) for e in data.progress["rect"]] == [(1, "failed"), (1, "ok")]
    assert "printed by hand" in list(ExperimentStore.open(tmp_path / "exp").read_logs("console").values())[-1]


def test_script_plans_runs_on_the_dummy_and_marks_the_layer(tmp_path, capsys, monkeypatch):
    import importlib.util

    from nanofactorysystem.storage import ExperimentRecord, ExperimentStore

    folder = tmp_path / "exp"
    store = ExperimentStore.create(folder, ExperimentRecord(
        uuid="0f0e0d0c-0000-4000-8000-000000000171", parameters={}, user={"key": "Test"},
        objective={"key": "Zeiss 63x"}, system={"backend": "dummy"}, software={"package_version": "0"}))
    store.add_structure(structure_record("s"))
    programs = folder / "structures" / "s" / "programs"
    programs.mkdir(parents=True)
    layer = programs / "program_s.003.txt"
    layer.write_text("\n".join(layer_program(columns=40)) + "\n")
    parts = split_program_file(layer, max_lines=150)
    stem = parts[1].stem
    store.write_log("a3200", "\n".join([load(parts[0].stem, 1), poll(3, 150), load(stem, 2), poll(4, 40),
                                        poll(8, 60)]))
    store.end_session("exception")
    spec = importlib.util.spec_from_file_location("resume_script", Path(__file__).parents[1] / "mains" /
                                                  "resume_layer.py")
    script = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(script)
    monkeypatch.setattr("time.sleep", lambda s: None)

    script.main(["run", "--experiment", str(folder), "--max-lines", "150", "--dry-run"])
    out = capsys.readouterr().out
    assert f"{stem} stopped on task 1; last reported line 60" in out and "Controller health: ok" in out
    assert "Dry run: the experiment file is not changed." in out
    assert ExperimentStore.open(folder).read().progress.get("s", []) == []

    script.main(["mark", "--experiment", str(folder), "--max-lines", "150"])
    assert "recorded as printed" in capsys.readouterr().out
