"""Tests for the library program loader, the memory budget and the task-alternating runner (T129)."""
from pathlib import Path

import pytest

from nanofactorysystem.aerobasic.ascii import AerotechAsciiInterface
from nanofactorysystem.backends.dummy import FakeA3200Transport, SimulatedWorld
from nanofactorysystem.backends.dummy.loader import DummyLoader
from nanofactorysystem.devices.aerotech import loader as loader_module
from nanofactorysystem.devices.aerotech.loader import (MemoryBudget, ProgramLoadError, ProgramRunError, ProgramRunner,
                                                       last_statement_line, max_part_lines)


@pytest.fixture
def world():
    return SimulatedWorld(seed=0)


@pytest.fixture
def transport(world):
    return FakeA3200Transport(world)


@pytest.fixture
def api(transport):
    api = AerotechAsciiInterface(transport_factory=lambda: transport)
    api.connect()
    return api


@pytest.fixture
def low_memory_use(monkeypatch):
    """ The PC uses 4 GB, whatever machine runs the tests. """

    monkeypatch.setattr(loader_module, "used_memory_gb", lambda: 4.0)


def layer_parts(folder: Path, n_layers: int, n_parts: int, lines: int = 5) -> list[tuple[int, list[Path]]]:
    items = []
    for layer in range(n_layers):
        parts = []
        for k in range(n_parts):
            path = folder / f"program_rect.{layer:03d}.part{k + 1:03d}.pgm"
            path.write_text("".join(f"LINEAR X{i} F1\n" for i in range(lines)) + "END PROGRAM\n")
            parts.append(path)
        items.append((layer, parts))
    return items


def runner(transport, api, tmp_path, **kwargs):
    return ProgramRunner(DummyLoader(transport), api, kwargs.pop("budget", MemoryBudget(budget_gb=1e6)),
                         exec_dir=tmp_path / "exec", poll_s=0.0, **kwargs)


def test_memory_budget():
    budget = MemoryBudget(budget_gb=22, reserve_gb=3, kb_per_line=19.7, safety=1.2)

    assert budget.peak_gb(400_000) == pytest.approx(400_000 * 19.7 * 1.2 / 1024 ** 2)
    # 22 - 3 - 8.8 GB in use (lab session 1) leaves about 450 000 lines
    assert 440_000 < budget.max_lines(8.8) < 460_000
    assert budget.part_lines(8.8) == 450_000
    assert budget.fits(400_000, 8.8) and not budget.fits(600_000, 8.8)
    with pytest.raises(ProgramLoadError, match="no room"):
        budget.max_lines(19.5)
    assert max_part_lines(budget, 19.5) == 10_000


def test_last_statement_line(tmp_path):
    path = tmp_path / "p.pgm"
    path.write_text("A\nB\nEND PROGRAM\n\n\n")

    assert last_statement_line(path) == 3


def test_parts_alternate_between_tasks_1_and_2(tmp_path, transport, api, world, low_memory_use):
    items = layer_parts(tmp_path, n_layers=2, n_parts=3)
    done = []

    records = runner(transport, api, tmp_path).run(items, done.append)

    loads = world.calllog.filter(device="loader")
    assert [load.args[1] for load in loads] == [1, 2, 1, 2, 1, 2]
    assert done == [0, 1]
    assert [r.task for r in records] == [1, 2, 1, 2, 1, 2]
    assert all(r.last_line == 6 for r in records)
    # Every program was removed under its loaded name and the execution copies are gone
    assert transport.loaded_programs == {} and transport.unknown_removals == []
    assert not list((tmp_path / "exec").iterdir())
    runs = world.calllog.filter(device="program")
    assert len(runs) == 6 and all(run.result["not_simulated"] == 0 for run in runs)


def test_next_part_is_loaded_while_the_current_one_runs(tmp_path, transport, api, world, low_memory_use):
    items = layer_parts(tmp_path, n_layers=1, n_parts=2)
    events = []
    original_start = DummyLoader.start

    def start(self, task_id):
        events.append(("start", task_id))
        original_start(self, task_id)

    loader = DummyLoader(transport)
    loader.start = start.__get__(loader)
    original_load = loader.load_async
    loader.load_async = lambda path, task_id: (events.append(("load", task_id)), original_load(path, task_id))[1]

    ProgramRunner(loader, api, MemoryBudget(budget_gb=1e6), exec_dir=tmp_path / "exec", poll_s=0.0).run(items)

    # Part 2 is loaded on task 2 right after part 1 started on task 1, before part 1 has ended
    assert events == [("load", 1), ("start", 1), ("load", 2), ("start", 2)]


def test_task_error_stops_and_cleans_up(tmp_path, transport, api, world, low_memory_use):
    items = layer_parts(tmp_path, n_layers=2, n_parts=2)
    transport.program_error_next(error_code=42, running_polls=1)
    done = []

    with pytest.raises(ProgramRunError, match="ended in state error") as error:
        runner(transport, api, tmp_path).run(items, done.append)

    assert error.value.key == 0 and done == []
    # The failed part and the prefetched part are removed, both tasks stopped
    assert transport.loaded_programs == {}
    assert world.task(1).state == world.task(2).state == 2


def test_early_end_is_a_failure(tmp_path, transport, api, low_memory_use):
    items = layer_parts(tmp_path, n_layers=1, n_parts=2)
    transport.program_incomplete_next(2)

    with pytest.raises(ProgramRunError, match="ended early: .* line 2 of 6"):
        runner(transport, api, tmp_path).run(items)
    assert transport.loaded_programs == {}


def test_load_failure_names_the_layer(tmp_path, transport, api, low_memory_use):
    items = layer_parts(tmp_path, n_layers=2, n_parts=1)
    run = runner(transport, api, tmp_path)
    original = run.loader.load_async
    calls = []

    def load(path, task_id):
        calls.append(path)
        if len(calls) == 2:  # the prefetch of layer 1 fails
            run.loader.fail_next_load("Compiler Error: out of memory")
        return original(path, task_id)

    run.loader.load_async = load
    done = []

    with pytest.raises(ProgramRunError, match="Could not load .* out of memory") as error:
        run.run(items, done.append)

    assert error.value.key == 1 and done == [0]
    assert transport.loaded_programs == {}


def test_prefetch_waits_when_the_budget_is_exhausted(tmp_path, transport, api, world, monkeypatch, caplog):
    # While a part runs the PC is near the budget: the next part is loaded after the current one has ended
    readings = iter([4.0, 4.0, 30.0, 4.0, 4.0])  # first check, memory log of part 1, prefetch check, ...
    monkeypatch.setattr(loader_module, "used_memory_gb", lambda: next(readings, 4.0))
    items = layer_parts(tmp_path, n_layers=1, n_parts=2)

    records = runner(transport, api, tmp_path, budget=MemoryBudget(budget_gb=22)).run(items)

    assert len(records) == 2 and "loaded afterwards" in caplog.text


def test_first_part_over_budget_is_refused(tmp_path, transport, api, monkeypatch):
    monkeypatch.setattr(loader_module, "used_memory_gb", lambda: 21.0)
    items = layer_parts(tmp_path, n_layers=1, n_parts=1, lines=100_000)

    with pytest.raises(ProgramLoadError, match="does not fit into the memory budget"):
        runner(transport, api, tmp_path, budget=MemoryBudget(budget_gb=22)).run(items)
