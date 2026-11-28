"""Continue a layer that stopped in the middle, without exposing its printed part twice (T170).

Case of 2026-11-28: layer 69 of ``surface_16bit`` stopped in part 6 of 11 after an axis fault of X.
``restart_experiment.py`` would print layer 69 again from its start, which exposes about 419 000
already written lines a second time. This script continues the layer behind the point where it stopped:

1. ``plan`` (no hardware): reads the controller command log of the experiment file, finds the
   part that stopped and the last program line the controller reported, maps it to the layer
   program and writes the rest of the layer to ``<experiment>/resume/``:
   ``<layer>.resume_from_<line>.txt`` (whole program) and ``split/`` (parts of at most 80 000 lines,
   each with the full layer setup, as the normal print). Prints what was printed and what is skipped.
2. ``run``: checks the controller (every axis enabled and homed, task 1 not in error), asks, runs the
   parts on task 1 one after another and then records the layer as printed in the experiment file.
3. ``mark``: only records the layer as printed (if you ran the parts yourself, e.g. in the Femtika
   software). After ``run`` or ``mark``, ``restart_experiment.py`` continues with the next layer.

Why nothing is exposed twice: the controller cannot execute a line it has not read, so the stage is
never ahead of the reported line. The rest starts at the first laser-off move (``RAPID``) behind the
reported line plus ``--margin-lines`` (default 1). If the lookahead was ahead of the motion, a short
piece stays unexposed (a gap), never a double exposure. ``--next-column`` also skips the rest of the
hatch line in which the fault happened (about 100 lines, one 0.25 µm line).

Before ``run``: the sample has not been moved since the original print (the program holds the absolute
coordinates of its plane fit), all axes are enabled and homed (homing does not change the absolute
coordinates), and nothing else runs on the controller.

Usage (``mains/`` as working directory)::

    python resume_layer.py plan --experiment "C:\\...\\DOE_circle_V2-A_20261128-1302"
    python resume_layer.py run  --experiment "C:\\...\\DOE_circle_V2-A_20261128-1302"
    python resume_layer.py mark --experiment "C:\\...\\DOE_circle_V2-A_20261128-1302"
    python restart_experiment.py ...      # continues with layer 68

Options: ``--next-column``, ``--margin-lines N``, ``--part-line N`` (instead of the line from the log),
``--stem program_surface_16bit.069.part06of11`` (instead of the last part loaded in the log),
``--dry-run`` (``run`` on the simulated controller, the experiment file is not changed).
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from nanofactorysystem.aerobasic.programs.split import MAX_PROGRAM_LINES  # noqa: E402
from nanofactorysystem.resume_layer import (failure_point, layer_program_for_part, mark_layer_printed,  # noqa: E402
                                            plan_resume, write_resume_program)


def find_failure(experiment: Path, stem=None):
    """ The failure point from the newest session log that contains a part load. """

    from nanofactorysystem.storage import ExperimentStore

    logs = ExperimentStore.open(experiment).read_logs("a3200")
    for session in sorted(logs, reverse=True):
        try:
            return session, failure_point(logs[session], stem)
        except ValueError:
            continue
    raise SystemExit(f"No program part load in the controller logs of {experiment / 'experiment.h5'}")


def make_plan(options):
    """ Find the stop, write the rest of the layer and print a summary. Returns everything ``run`` needs. """

    experiment = Path(options.experiment)
    session, point = find_failure(experiment, options.stem)
    layer_path, part, n_parts = layer_program_for_part(experiment, point.stem)
    reported = options.part_line if options.part_line is not None else point.last_line
    lines = layer_path.read_text().splitlines()
    plan = plan_resume(lines, part, n_parts, reported, max_lines=options.max_lines,
                       margin_lines=options.margin_lines, next_column=options.next_column)
    program, parts = write_resume_program(lines, plan, experiment / "resume", layer_path.name,
                                          max_lines=options.max_lines)
    structure = layer_path.parent.parent.name
    layer_id = int(layer_path.name.split(".")[-2])
    print(f"Session {session}: {point.stem} stopped on task {point.task_id}; last reported line {point.last_line}"
          f" (error state at line {point.error_line}); used line {reported}")
    print(f"Layer program {layer_path.name}: {plan.layer_lines} lines, body {plan.header_end + 1}-{plan.footer_start}")
    print(f"  printed (not written again): body lines {plan.header_end + 1}-{plan.stop_index + 1} "
          f"({plan.printed_body_lines} lines), stop line: {lines[plan.stop_index]}")
    print(f"  skipped (never written):     {plan.skipped_lines} lines")
    print(f"  rest from line {plan.resume_index + 1}: {lines[plan.resume_index]} ({plan.remaining_body_lines} lines)")
    print(f"Rest of the layer: {program}")
    for p in parts:
        print(f"  part: {p}")
    note = (f"Rest of layer {layer_id} of {structure} after the stop of {point.stem} (session {session}, reported "
            f"line {reported}): layer lines {plan.resume_index + 1}-{plan.footer_start} printed from {program.name}; "
            f"lines {plan.stop_index + 2}-{plan.resume_index} skipped (T170)")
    return experiment, structure, layer_id, parts, note


def run_parts(parts, dry_run: bool) -> None:
    """ Check the controller, ask, and run the parts on task 1 one after another. """

    from nanofactorysystem.aerobasic.ascii import AerotechError
    from nanofactorysystem.devices.aerotech import Aerotech3200
    from nanofactorysystem.devices.aerotech.health import controller_health

    if dry_run:
        from nanofactorysystem.backends.dummy import FakeA3200Transport, SimulatedWorld
        transport = FakeA3200Transport(SimulatedWorld(seed=0))
        controller = Aerotech3200(transport_factory=lambda: transport, program_dir=Path(parts[0]).parent)
    else:
        controller = Aerotech3200()
    controller.connect()
    try:
        report = controller_health(controller.api, tasks=(1,), check_processes=not dry_run)
        print(report.text())
        if not report.ok:
            raise SystemExit("The controller is not ready (see above): enable and home every axis, then try again.")
        if not dry_run and input(f"Run {len(parts)} part(s) on task 1 now? Type yes: ").strip().lower() != "yes":
            raise SystemExit("Not started.")
        for k, part in enumerate(parts, start=1):
            print(f"Part {k} of {len(parts)}: {Path(part).name}")
            task = controller.run_program_as_task(part, task_id=1)
            try:
                task.wait_to_finish()
                task.finish()
            except AerotechError:
                task.abort()
                print(f"Part {k} failed. The layer is NOT recorded as printed. Run 'plan' again: it reads the new "
                      f"stop from the log of this run only if you pass --part-line and --stem by hand; the "
                      f"controller log of this run is {controller.save_log(Path(parts[0]).parent)}")
                raise
    finally:
        controller.save_log(Path(parts[0]).parent)
        controller.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Continue a stopped layer without exposing its printed part twice")
    parser.add_argument("action", choices=("plan", "run", "mark"))
    parser.add_argument("--experiment", required=True, help="experiment folder (with experiment.h5)")
    parser.add_argument("--stem", default=None, help="part that stopped (default: last part loaded in the log)")
    parser.add_argument("--part-line", type=int, default=None, help="reported line instead of the one in the log")
    parser.add_argument("--margin-lines", type=int, default=1, help="lines skipped behind the stop in any case")
    parser.add_argument("--next-column", action="store_true", help="also skip the rest of the hatch line")
    parser.add_argument("--max-lines", type=int, default=MAX_PROGRAM_LINES, help="part size of the original split")
    parser.add_argument("--dry-run", action="store_true", help="run on the simulated controller, file unchanged")
    options = parser.parse_args(argv)

    experiment, structure, layer_id, parts, note = make_plan(options)
    if options.action == "plan":
        print("Nothing was run. Check the lines above, then use 'run' (or 'mark' after running the parts yourself).")
        return
    if options.action == "run":
        run_parts(parts, options.dry_run)
    if options.dry_run:
        print("Dry run: the experiment file is not changed.")
        return
    session = mark_layer_printed(experiment, structure, layer_id, note)
    print(f"Layer {layer_id} of {structure} recorded as printed (session {session}). "
          f"restart_experiment.py continues with the next layer.")


if __name__ == "__main__":
    main()
