"""Check the A3200 controller before a print, optionally with recovery level R0 (T133).

Reads the ASCII interface, the task states of tasks 1 and 2, the axis faults and states, the
memory of the PC and of the A3200 processes. ``--r0`` first stops tasks 1 and 2, removes the
programs this package loads under fixed names and acknowledges faults; nothing moves.

Usage (any working directory):

    python mains/controller_health.py
    python mains/controller_health.py --r0
    python mains/controller_health.py --dry-run     # on the simulated controller

Recovery levels R1-R3 (restart the ASCII interface, controller reset, restart the A3200 software)
follow after lab session 2, see docs/design/PROGRAM_LOADING.md section 8.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from nanofactorysystem.aerobasic.ascii import AerotechAsciiInterface  # noqa: E402
from nanofactorysystem.devices.aerotech.health import controller_health, recover_r0  # noqa: E402


def main(argv=None) -> int:
    """ Print the health report; exit code 0 if the controller is ready to print, 1 otherwise. """

    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--r0", action="store_true", help="run recovery level R0 first")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--dry-run", action="store_true", help="use the simulated controller")
    args = parser.parse_args(argv)

    factory = None
    if args.dry_run:
        from nanofactorysystem.backends.dummy import FakeA3200Transport, SimulatedWorld
        transport = FakeA3200Transport(SimulatedWorld())
        factory = lambda: transport  # noqa: E731
    api = AerotechAsciiInterface(args.host, args.port, transport_factory=factory, response_timeout=30.0)
    try:
        api.connect()
    except OSError as error:
        print(f"ASCII interface not reachable ({error}): is the A3200 software running?")
        return 1
    try:
        if args.r0:
            for step in recover_r0(api):
                print(f"R0: {step}")
        report = controller_health(api, check_processes=not args.dry_run)
        print(report.text())
        return 0 if report.ok else 1
    finally:
        api.close()


if __name__ == "__main__":
    sys.exit(main())
