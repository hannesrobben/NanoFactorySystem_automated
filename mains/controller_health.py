"""Check the A3200 controller before a print, optionally with a recovery level (T133).

Reads the ASCII interface, the task states of tasks 1 and 2, the axis faults and states, the
memory of the PC and of the A3200 processes. Recovery levels (docs/design/PROGRAM_LOADING.md section 8):

- ``--r0`` stops tasks 1 and 2, removes the programs this package loads under fixed names and acknowledges
  faults; nothing moves.
- ``--r1`` restarts the ASCII interface (``A3200AsciiInterface.exe``, about 1 s); tasks, programs and axes stay.
- ``--r2`` resets the controller (``~RESETCONTROLLER``): every axis is disabled and unhomed, every program
  removed. Only between experiments; asks in a message box first.
- ``--r3`` restarts the service ``A3200CommService`` (administrator PowerShell); asks in a message box first.

Usage (any working directory):

    python mains/controller_health.py
    python mains/controller_health.py --r0
    python mains/controller_health.py --r2          # after the confirmation in the message box
    python mains/controller_health.py --dry-run     # on the simulated controller
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from nanofactorysystem.aerobasic.ascii import AerotechAsciiInterface, AerotechError  # noqa: E402
from nanofactorysystem.devices.aerotech.health import (controller_health, recover_r0, recover_r1,  # noqa: E402
                                                       reset_controller, restart_a3200_service,
                                                       terminate_ascii_interface)

R2_QUESTION = ("Recovery level R2 resets the controller: every axis is disabled and loses its home, every program "
               "is removed. Only between experiments; move the objective to a safe Z first.\n\nReset the controller now?")
R3_QUESTION = ("Recovery level R3 restarts the A3200 service (administrator rights needed). No task may run and the "
               "laser must be off.\n\nRestart the A3200 service now?")


def main(argv=None, *, confirm=None) -> int:
    """ Print the health report; exit code 0 if the controller is ready to print, 1 otherwise.

    Parameters
    ----------
    argv : list of str, optional
        Command line arguments.
    confirm : callable, optional
        ``confirm(question) -> bool`` before R2 and R3 (default: a message box; a console prompt is too easy
        to miss, maintainer decision 2026-11-26).

    Returns
    -------
    int
        Exit code.
    """

    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--r0", action="store_true", help="run recovery level R0 first")
    group.add_argument("--r1", action="store_true", help="restart the ASCII interface first (R0 before)")
    group.add_argument("--r2", action="store_true", help="reset the controller first (asks first)")
    group.add_argument("--r3", action="store_true", help="restart the A3200 service first (asks first)")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--dry-run", action="store_true", help="use the simulated controller")
    args = parser.parse_args(argv)
    if confirm is None:
        from nanofactorysystem.experiment_spec import messagebox_confirm
        confirm = messagebox_confirm

    factory, restart = None, terminate_ascii_interface
    if args.dry_run:
        from nanofactorysystem.backends.dummy import FakeA3200Transport, SimulatedWorld
        transport = FakeA3200Transport(SimulatedWorld())
        factory = lambda: transport  # noqa: E731
        restart = lambda: "simulated"  # noqa: E731
    if args.r3:
        if not confirm(R3_QUESTION):
            print("R3 not confirmed.")
            return 1
        if args.dry_run:
            print("R3: simulated")
        else:
            try:
                print(f"R3: {restart_a3200_service()}")
            except AerotechError as error:
                print(error)
                return 1
    api = AerotechAsciiInterface(args.host, args.port, transport_factory=factory, response_timeout=30.0)
    try:
        api.connect()
    except OSError as error:
        print(f"ASCII interface not reachable ({error}): is the A3200 software running?")
        return 1
    try:
        if args.r0 or args.r1:
            for step in recover_r0(api):
                print(f"R0: {step}")
        if args.r1:
            for step in recover_r1(api, restart):
                print(f"R1: {step}")
        if args.r2:
            if not confirm(R2_QUESTION):
                print("R2 not confirmed.")
                return 1
            for step in reset_controller(api):
                print(f"R2: {step}")
        report = controller_health(api, check_processes=not args.dry_run)
        print(report.text())
        return 0 if report.ok else 1
    finally:
        api.close()


if __name__ == "__main__":
    sys.exit(main())
