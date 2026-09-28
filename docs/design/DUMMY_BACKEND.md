# Design: Dummy Hardware Backend

Status: **proposed. Waiting for maintainer approval (T2).**
Date: 2026-09-28. Basis: `docs/reviews/CODE_REVIEW_2026-09-28.md` (T1).

## 1. Goals and non-goals

**Goals**
- The whole package (`System`, `tools/`, `Experiment`, and the experiment scripts) runs on any machine
  against simulated devices. It must work without `~/nanofactory.json`, without `mvIMPACT` or
  `OffAxisHolo`, without network access, and without sleeping.
- The code path under test stays **the real code path**. The fakes replace only the thin layer
  where Python touches the hardware: the TCP socket, the camera driver, the DHM client and the
  calibration file. All facades (`A3200`, `Aerotech3200`, `AerotechAsciiInterface`, `Camera`,
  `Dhm`, `Attenuator`) run unchanged. This means the AeroBasic command strings that reach the
  controller can be asserted in tests.
- Real hardware remains the default. The dummy backend is opt-in, and it logs a warning when active.

**Non-goals**
- Physical accuracy. The simulation only needs to be *plausible enough* that the existing
  algorithms (exposure optimisation, focus/layer detection, plane fit, OPL scan) converge, and
  to be deterministic.
- Changing behaviour on the real hardware, including the galvo move in `System.__init__`. Fixing
  the defects listed in the review is left to T10, T11 and T13.

## 2. Where the seams are

```
System ──┬─ A3200 (old facade) ─────┐
         │                          ├─ ControllerTransport ── real: socket.socket (TCP 8000)
         ├─ Aerotech3200 ─ AerotechAsciiInterface ┘            dummy: FakeA3200Transport ─┐
         ├─ Attenuator ─────────────── calibration file ─ real: lab path │ dummy: synthetic file (tmp)
         ├─ Camera ────────────────── CameraDriver ─ real: CameraDevice (mvIMPACT)  │ dummy: DummyCameraDriver ─┤
         └─ Dhm ───────────────────── DhmDriver ─ real: DhmClient (TCP 27182)       │ dummy: DummyDhmClient ────┤
                                                                                     SimulatedWorld ◄──────────┘
                                                              (stage, laser, sample, exposures, clock, rng, call log)
```

- Both controller facades talk ASCII over **one** transport object, just as `System` does today
  (`system.py:82` shares the socket). The fake transport is a socket-like object. It parses the
  bytes it receives as AeroBasic immediate commands and answers with protocol-correct frames
  (`%data\n`, `!\n`, `#\n`, see `ReturnCode`). As a result, `AerotechAsciiInterface.send()`
  (encoding, `recv`, return-code handling, `~LASTERROR` follow-up) and the old `A3200.run()` are
  both exercised.
- All fakes share one `SimulatedWorld`. For example, a `LINEAR` sent to the controller moves the
  stage the camera renders from, and a z-line exposure crossing the resin interface leaves a spot
  that later camera images show.

## 3. Protocols (one per device role)

These go in `nanofactorysystem/backends/protocols.py` as `typing.Protocol` classes with
`@runtime_checkable`. They are derived from the call sites found in T1: `system.py`, `experiment.py`,
`tools/*`, `dhm/optimage.py`, `dhm/motorscan.py` and `camera/optexpose.py`. The *role* protocols
document what consumers rely on. The *seam* protocols are what a backend has to provide.

### 3.1 Motion controller

```python
class ControllerTransport(Protocol):          # seam, shared by both facades
    def connect(self, address: tuple[str, int]) -> None: ...
    def send(self, data: bytes) -> int: ...
    def recv(self, bufsize: int) -> bytes: ...
    def settimeout(self, value: float | None) -> None: ...
    def close(self) -> None: ...

class LegacyMotionController(Protocol):       # role: devices.A3200 as used by System/tools/Experiment
    socket: ControllerTransport
    attenuator: "Attenuator"
    def __getitem__(self, key: str) -> Any: ...            # "zMax", "host", ...
    def parameters(self) -> dict[str, Any]: ...
    def moveabs(self, speed: float, **axes: float) -> None: ...
    def position(self, axes: str) -> float | list[float]: ...
    def wait(self, axes: str, pause: float | None = None) -> None: ...
    def power(self, power: float) -> None: ...
    def laseron(self, power: float) -> None: ...
    def laseroff(self) -> None: ...
    def pulse(self, power: float, duration: float) -> None: ...
    def init_zline(self, fn: str | None = None) -> int | None: ...
    def zline(self, power: float, fast: float, slow: float, dz: float) -> None: ...
    def close(self) -> None: ...

class TaskController(Protocol):               # role: devices.aerotech.Aerotech3200 as used by Experiment
    api: "AerotechAsciiInterface"             # LINEAR, AXISSTATUS, STATUS, PROGRAM_LOAD/START/STOP/ASSOCIATE, REMOVE_PROGRAM, send, __call__
    @property
    def xyz(self) -> Point3D: ...
    def run_program_as_task(self, program: PathLike | AeroBasicProgram, *, task_id: int | None = None,
                            program_ready_timeout: float = 10, program_start_running_timeout: float = 10) -> "Task": ...
    def save_log(self, folder: Path | str = ".") -> str: ...
    def connect(self) -> None: ...
    def close(self) -> None: ...
```

### 3.2 Attenuator

```python
class AttenuatorRole(Protocol):               # role: devices.Attenuator
    data: np.ndarray                          # (n, 2): attenuator value, power in mW
    def ptoa(self, power: float) -> float: ...
    def atop(self, value: float) -> float: ...
    def __getitem__(self, key: str) -> Any: ...            # "powerMin", "powerMax", "valueMin", "valueMax"
    def parameters(self) -> dict[str, Any]: ...
```

The seam is the binary calibration file (pairs of little-endian `double`s). The dummy backend
writes a synthetic file and passes it in as `attenuator.calibrationFile`. `Attenuator` itself
stays unchanged.

### 3.3 Camera

```python
class CameraDriver(Protocol):                 # seam, replaces camera.CameraDevice
    opened: bool
    def __getitem__(self, key: str) -> Any: ...            # ExposureTime, Width, Height, OffsetX, family, product, serial, deviceID, ...
    def __setitem__(self, key: str, value: Any) -> None: ...
    def keys(self) -> list[str]: ...
    def property(self, name: str) -> "PropertyInfo": ...    # .minValue / .maxValue (/ .choices)
    def getimage(self) -> np.ndarray: ...                   # 2-D uint8
    def close(self) -> None: ...

class CameraRole(Protocol):                   # role: devices.Camera as used by System/Experiment/tools
    opened: bool
    def getimage(self) -> np.ndarray: ...
    def optexpose(self, level: int = 127) -> tuple[np.ndarray, float]: ...
    def container(self, loc=None, config=None, **kwargs) -> ImageContainer: ...
    def parameters(self) -> dict[str, Any]: ...
    def __setitem__(self, key: str, value: Any) -> None: ...
    def close(self) -> None: ...
```

### 3.4 DHM

```python
class DhmDriver(Protocol):                    # seam, replaces dhm.DhmClient
    # Attribute access mirrors DhmClient._commands (read, and write where a set-command exists):
    ConfigList: list[tuple[int, str]]; Config: int
    CameraImage: np.ndarray; CameraBitPerPixel: int
    CameraShutter: int; CameraMinShutter: int; CameraMaxShutter: int; CameraShutterUs: float
    MotorPos: float; MotorMinPos: float; MotorMaxPos: float
    def set_keys(self) -> list[str]: ...
    def keys(self) -> list[str]: ...
    def parameters(self) -> dict[str, Any]: ...
    def close(self) -> None: ...

class DhmRole(Protocol):                      # role: devices.Dhm
    device: DhmDriver
    opened: bool
    def getimage(self, opt: bool = True) -> tuple[np.ndarray, int | None]: ...
    def motorscan(self, m0: float | None = None) -> float: ...
    def container(self, opt=True, loc=None, config=None, image_count=0, **kwargs) -> HoloContainer: ...
    def parameters(self) -> dict[str, Any]: ...
    def close(self) -> None: ...
```

Contract tests in T3 check with `isinstance` that the real classes and the dummies satisfy these
protocols. When a consumer starts using a new device method, the protocol has to be extended as well.

## 4. The backend switch

The switch is one keyword-only argument, and real hardware stays the default:

```python
System(user, objective, logger=None, *, backend: Backend | str | None = None, **kwargs)
Experiment(..., backend: Backend | str | None = None)          # forwarded to System
```

- `backend=None` resolves as follows: `NANOFACTORY_BACKEND` environment variable if set, otherwise
  `"real"`. An explicit argument **always** wins over the environment variable. The variable is only
  a convenience override, e.g. `NANOFACTORY_BACKEND=dummy python mains/main.py` dry-runs any
  experiment script without editing it.
- `backend="dummy"` builds a `DummyBackend` with default settings. `backend=DummyBackend(seed=…,
  world=…, workdir=…)` passes a configured instance, which is what tests use.
- An unknown value raises `ValueError`. Selecting the dummy backend logs
  `WARNING: SIMULATED HARDWARE (dummy backend) — nothing is printed`.
- `system.backend` exposes the active backend. For the dummy backend, `system.backend.world` and
  `system.backend.calllog` are what tests assert on.

A backend is a small factory object that `System` asks for its dependencies:

```python
class Backend(Protocol):
    name: str
    def controller_transport(self) -> ControllerTransport: ...
    def camera_driver(self, product: str | None, device_id: int | None) -> CameraDriver: ...
    def dhm_driver(self, host: str, port: int) -> DhmDriver: ...
    def attenuator_args(self) -> dict[str, Any]: ...     # e.g. {"calibrationFile": <path>}
    def program_dir(self) -> Path | None: ...            # None = current behaviour (cwd / home)
```

`RealBackend` returns exactly what the code creates today: `socket.socket(AF_INET, SOCK_STREAM)`,
`CameraDevice(product, deviceID)`, `DhmClient(host, port)`, the configured calibration file, and
`None`.

### Required, minimal changes to existing classes

Each change adds an optional, keyword-only injection parameter. When it is omitted, the current
behaviour stays byte-for-byte the same.

| Class | New keyword-only parameter | Used for |
|---|---|---|
| `A3200.__init__` | `transport: ControllerTransport \| None = None`, `program_dir: Path \| None = None` | fake socket; where `__zline__.pgm` is written |
| `AerotechAsciiInterface.__init__`, `Aerotech3200.__init__` | `transport_factory: Callable[[], ControllerTransport] \| None = None`, `program_dir` (Aerotech3200 only) | fake socket in `connect()`; staging of `python_aerobasic_program.pgm` and temporary programs |
| `Camera.__init__` | `driver: CameraDriver \| None = None` | replaces `CameraDevice(product, deviceID)` |
| `Dhm.__init__` | `driver: DhmDriver \| None = None` | replaces `DhmClient(host, port)` |
| `System.__init__` | `backend=None` | builds the above from the backend |
| `Experiment.__init__` | `backend=None` | forwarded |

`Aerotech3200(dummy=True)` and `DummyAsciiInterface` stay for compatibility but are marked deprecated
in their docstrings. `dummy=True` is re-routed to the new fake transport, so it finally answers queries.

## 5. The simulated devices

### 5.1 `SimulatedWorld`: shared state

- **Stage**: positions for X, Y, Z (mm, controller units) and A, B (galvo), the programming mode
  (ABSOLUTE/INCREMENTAL), and the enabled axes. Moves complete instantly. A **virtual clock**
  advances by `distance / feedrate` (and by any simulated wait), so the timer queries
  (`SYSTEMSTATUS Timer`) return deterministic values. There is no wall clock anywhere.
- **Laser**: attenuator value (`$AO[0].A`), which gives the power through the synthetic
  calibration; the laser-override state; and the IFOV state.
- **Sample model**: `SampleModel(substrate_plane=(c, a, b), resin_thickness_um=75.0)`. The lower
  interface is `z_low(x, y) = c + a·x + b·y` (µm). The upper interface is `z_low + thickness`.
  The defaults put the interface inside the configured `zMax`, and a small tilt is used so that
  the plane fit has something to find.
- **Exposures**: each segment written with the laser on (a `LINEAR` while override is ON, a z-line
  task, or a `pulse`) is recorded as an `Exposure(x, y, z_from, z_to, power, t)`. An exposure that
  **crosses an interface** with power above a threshold becomes a visible `Spot(x, y, radius)`.
  This is the simplest rule that lets `Focus`/`Layer`/`Plane` converge on the configured plane.
- **Call log**: a single ordered `CallLog` of `CallRecord(device, call, args, result, t_virtual)`.
  It records every transport command (the raw ASCII line and the response frame), every camera or
  DHM driver access, and every program executed. It has helpers such as `commands()` (the controller
  command strings in order), `filter(device=…)` and `clear()`.
- **Randomness**: one `numpy.random.Generator(PCG64(seed))`, with default `seed=0`. It is used only
  for image noise. The same seed and the same calls give identical results.

### 5.2 `FakeA3200Transport`: controller at the ASCII level

- It buffers bytes until `\n`, dispatches each command line to a handler table, and queues the
  response frame for `recv()`. `recv()` never blocks. Calling it with nothing queued raises a clear
  error, because in the real code that would be a hang.
- It implements the commands that the code actually sends (collected in T1): `ACKNOWLEDGEALL`,
  `~VERSION`, `~LASTERROR`, `~TASK`, `~STOPTASK`, `~STATUS (...)` (axis, task and system data
  items), `AXISSTATUS(ax, DATAITEM_*)` (PositionFeedback, VelocityFeedback, DriveStatus with the
  InPosition bit, AccelerationRate), `TASKSTATUS(n, DATAITEM_TaskState)`, `ABSOLUTE`,
  `INCREMENTAL`, `LINEAR`/`RAPID` (with `F`), `ENABLE`, `HOME`, `VELOCITY`, `WAIT MODE`,
  `RAMP ...`, `$AO[0].A=`, `$global[i] =`, `GALVO LASEROVERRIDE A ON|OFF`,
  `PROGRAM n LOAD|ASSOCIATE|START|STOP`, `REMOVEPROGRAM`, `ERRORDECODE`, `IFOV ...`, and
  `SYSTEMSTATUS`.
- **Program tasks**: `LOAD` reads the `.pgm` file from disk and sets the task to `program_ready`.
  `START` runs it through a small **AeroBasic interpreter** for the subset that affects the world:
  `DVAR`, `$var =`/`$global[]`, `ABSOLUTE`/`INCREMENTAL`, `LINEAR`/`RAPID`,
  `GALVO LASEROVERRIDE`, `CRITICAL START|END`, comments and `END PROGRAM`. Other lines are
  counted as "not simulated" in the call log; they don't cause errors. The task then goes to
  `program_complete`, with `ProgramLineNumber` set to the file's line count, so `Task.wait_to_finish`
  sees a complete run. The z-line program (`ZLINE_PGM`) is covered by this generic interpreter;
  no special case is needed.
- **Configurable responses and fault injection**:
  `transport.respond(r"^~VERSION$", "4.9.0.0")` overrides a response;
  `transport.fail_next(r"^PROGRAM \d+ START$", code="FAULT", error="Task fault")` injects a fault;
  `strict=True` answers unknown commands with `!` (INVALID) instead of the default `%`
  (success, logged as unhandled).
- `decimal_comma=False` by default. With `True`, numbers are formatted as the German-locale
  controller does, which exercises the `.replace(",", ".")` paths.

### 5.3 `DummyCameraDriver`

- Properties: `Width`/`Height` (default 1280×1024; this is configurable, and T3 checks the real
  sensor size against the lab config), `OffsetX`/`OffsetY`, `ExposureTime`, `Gain`, the
  `AcquisitionMode` etc. from `Camera._defaults`, plus `family`, `product`, `serial` and
  `deviceID`. `property(name)` returns min/max values, so `setaoi` and `optExpose` work.
- `getimage()` renders a `uint8` image: a background (level ∝ `ExposureTime`, clipped at 255,
  so `optExpose` converges) plus seeded Gaussian noise plus every visible spot as a Gaussian disc.
  The spot position is taken from `Transform` (the objective's `cameraPitch`) relative to the
  current stage XY. There is no z-dependent defocus in v1.

### 5.4 `DummyDhmClient`

- Every key in `DhmClient._commands` is backed by a state dict with the real types.
  `ConfigList`/`Config` contain the objective ids from the config (178 for 20x, 180 for 63x),
  and the initial `Config` matches the objective, so `Dhm.__init__` does not `sleep(2)`.
- `CameraImage` is an off-axis hologram: carrier fringes, plus a phase taken from the height
  of the visible spots, plus seeded noise. Its intensity scales with `CameraShutter` and saturates,
  so `optImage` converges. Fringe contrast is `exp(-((MotorPos - opl_opt) / w)²)`, so
  `motorscan` finds `opl_opt`.

### 5.5 Attenuator

`DummyBackend.attenuator_args()` writes `calibration.dat` into the backend `workdir`. The file
has 101 points: attenuator value 0…10, power `P = P_max·(v/10)²` with `P_max = 20 mW`. It returns
`{"calibrationFile": path}`. The real `Attenuator` loads it unchanged.

### 5.6 No sleeping

The fakes never call `time.sleep` and never touch the network. Production code still sleeps in a
few places (`run_program_as_task` polling, `Task.wait_to_finish`, `A3200.pulse`, `A3200.wait`).
Because the fakes report completion on the first poll, these loops exit before sleeping, except
for `pulse` (the sleep equals the pulse duration). The `dummy_system` fixture in T4 additionally
patches `time.sleep` in those modules to advance the virtual clock instead, which keeps the tests
fast.

## 6. Operation without `~/nanofactory.json`

- **Config sources**, in order: (1) `config.use_config(path | dict)` (a context manager for
  tests), (2) `$NANOFACTORY_CONFIG`, (3) `~/nanofactory.json`, (4) the built-in
  `nanofactorysystem/data/default_config.json`, with a warning. The built-in default contains the
  `system`, `controller`, `camera` and `dhm` sections and the objectives `Zeiss 20x`/`Zeiss 63x`
  (values from `config/objective/*.yaml` and the lab file). It has **no users** and **no**
  attenuator calibration path.
- **Missing sections** return `{}` instead of raising `AttributeError`.
- **Class-level defaults become lazy.** `_defaults = sysConfig.<section> | {...}` is replaced by a
  descriptor, `_defaults = ConfigDefaults("<section>", {...})`, which merges the *current* config
  on access in the same order as today. Importing no longer reads config sections, and switching
  configs in tests takes effect. Affected: `System`, `A3200`, `Attenuator`, `Camera`, `Dhm`.
- Users stay mandatory: `Parameter` still calls `sysConfig.user(user)`. The `test_config`
  fixture (T4) activates a temporary config that contains `user:Test`. The real backend with no
  calibration file raises `RuntimeError("attenuator.calibrationFile is not configured")`.

## 7. Optional dependencies

- `mvIMPACT`: the module-level `try/except` plus warning in `camera/camera.py` becomes an import
  on first use inside `CameraDevice.__init__`. On failure it raises
  `ImportError("The real camera backend needs mvIMPACT (Balluff mvGenTL Acquire). Install it, or use System(..., backend='dummy').")`.
  Importing the package no longer emits a warning.
- `OffAxisHolo`, `PlotFont`: the package does not import them (T1). Tests that need them use
  `pytest.importorskip` (T5).
- The package `__init__` keeps its eager imports. Making them lazy is not needed for the dummy
  backend and would change the public import behaviour.

## 8. File layout

```
nanofactorysystem/
  backends/
    __init__.py          # Backend protocol, resolve_backend(), RealBackend, DummyBackend, BACKEND_ENV_VAR
    protocols.py         # role and seam protocols (§3)
    real.py              # RealBackend
    dummy/
      __init__.py        # DummyBackend (seed, world, workdir, strict, …)
      world.py           # SimulatedWorld, SampleModel, Exposure, Spot, VirtualClock
      calllog.py         # CallLog, CallRecord
      a3200.py           # FakeA3200Transport, AeroBasic interpreter
      camera.py          # DummyCameraDriver
      dhm.py             # DummyDhmClient
      attenuator.py      # synthetic calibration writer
  data/default_config.json
test/backends/           # T3: tests for the dummies (state, call log, determinism, protocol conformance)
```

## 9. Impact on the public API

- **Added**: `nanofactorysystem.backends` (`DummyBackend`, `RealBackend`, `resolve_backend`),
  `config.use_config`, the keyword-only injection parameters from §4, and `System.backend`.
- **Unchanged**: all existing positional and keyword signatures, the defaults, and the behaviour
  with `backend` omitted and `NANOFACTORY_BACKEND` unset. No `BREAKING CHANGE`.
- **Changed, but compatible**: a missing config section yields `{}` instead of `AttributeError`.
  `import nanofactorysystem` works without the config file (a warning instead of a crash).
  `Aerotech3200(dummy=True)` now answers queries.

## 10. Decisions needed from the maintainer

1. **`devices/aerotech_old.py` (T12).** The active `A3200` has to receive two keyword parameters
   and the lazy `_defaults`, but CLAUDE.md forbids modifying `*_old.py`. **Proposal:** implement
   T12 first as a pure `git mv devices/aerotech_old.py devices/a3200.py` plus the import update in
   `devices/__init__.py`, in a separate `refactor:` commit, then apply the T3 changes to
   `devices/a3200.py`. `aerotech_old_1.py` stays untouched and legacy. Alternatively, you allow
   a one-time edit of `aerotech_old.py`.
2. **Environment variable.** `NANOFACTORY_BACKEND` as a convenience override (explicit argument
   wins; loud warning), yes or no? Without it, T6 has to thread `backend=` through the experiment
   script's `print_file`/`testprint` function.
3. **Scope of T3.** The fidelity of the sample/spot model is aimed at making `plane_fit()`
   converge in T6. If `Focus`/`Layer` need more realism than §5.1 describes (e.g. defocus with z),
   T3 would add it. The alternative is that the T6 dry run seeds `planefit/plane.zdc` from the
   known plane (which `Experiment.plane_fit` already loads when present) and T3 keeps the simple
   model. **Proposal:** try the simple model first, and fall back to seeding only if it does not
   converge, with the reason recorded in WORKLOG.md.

## 11. Implementation plan (T3), as separate commits

1. `refactor(devices)`: rename `aerotech_old.py` → `a3200.py` (if decision 1 is approved).
2. `refactor(config)`: config sources, built-in default, `{}` for missing sections, the
   `ConfigDefaults` descriptor.
3. `refactor(devices)`: keyword-only injection parameters; lazy `mvIMPACT` import.
4. `feat(backends)`: protocols, `RealBackend`, `resolve_backend`, and `System`/`Experiment` wiring.
5. `feat(backends)`: `SimulatedWorld`, `CallLog`, `FakeA3200Transport` and the interpreter, plus tests.
6. `feat(backends)`: dummy camera, DHM and attenuator, plus tests (including determinism and
   protocol conformance).
7. `test(backends)`: `System(backend="dummy")` smoke test, and a check that the real backend
   constructs the same objects as before (by patching `socket.socket`, `CameraDevice` and `DhmClient`).
