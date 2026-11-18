# Design: Camera live feed and recording

Status: approved 2026-11-18 (decision session 2026-11-17/18, with the additions of §8.1). Implementation
todos: T93–T95; **T102 (camera timeout in µs vs ms) is a hard prerequisite of T93.**

Context: F3 (video recording, scheduled as T73/T93–T95); maintainer wish of 2026-11-16 (with
`INFORMATION_MODEL.md` M6): a video of each structure while it prints; camera snapshots per structure only
before and after it. The stitched overview before and after printing exists (T28, `overview.py`) and keeps
working through the camera service.

## 1. Goals and non-goals

Goals:
- One owner of the camera driver, so that a live feed, a recording, `measure()`, the overview and the
  measurement tools (`Focus`, `Layer`, `Grid`) never use the device at the same time.
- A live feed with timestamps that consumers (recording, later the GUI F15) can subscribe to while an
  experiment prints.
- A recording of the print per structure (or per experiment), next to the experiment file, with a table
  in `experiment.h5` that maps frames to structures and layers.
- No behaviour change while the feed is off (the default): same device calls, same images.

Non-goals: image analysis of the feed, the GUI itself (F15), stage positions per feed frame (§4).

## 2. As-is (2026-11-16)

- `devices/camera.Camera` wraps `camera/camera.CameraDevice` (mvIMPACT Acquire). Every image is one
  `imageRequestSingle()` + `imageRequestWaitFor(timeout)` with `timeout = max(50, round(2000 ×
  ExposureTime))` in ms (default `ExposureTime` 20 000 µs, `AcquisitionMode = SingleFrame`). Because
  `ExposureTime` is in µs, the timeout is 4·10⁷ ms (about 11 h) for a 20 ms exposure instead of a few
  tens of ms; a stalled frame blocks practically forever. Found during T73 → T102; the stop bound in §3
  relies on its fix.
- Consumers, all through `System.getimage()` (an `ImageContainer` with the current stage position) or
  `System.optexpose()`: `Experiment.measure()` (T45, only with `camera_capture`), `overview.py` (T28),
  `tools/focus.py`, `tools/layer.py`, `tools/grid.py`, the plane fit (through `Focus`/`Layer`).
- `optexpose()` (`camera/optexpose.py`) changes `ExposureTime` on the device (bisection, up to 500 ms) and
  leaves the result set — later images use it.
- All calls run in the main thread; nothing else touches the camera. The dummy backend provides
  `DummyCameraDriver`.

## 3. Camera service (T93)

`nanofactorysystem/camera/service.py`:

```python
class CameraService:
    def snapshot(self, settings: dict | None = None, timeout_s: float | None = None) -> Frame: ...
    def optimise_exposure(self, level: int = 127) -> float: ...        # sets the measurement exposure
    def apply(self, settings: dict) -> None: ...                       # measurement settings (exposure, AOI, gain)
    def start_feed(self, settings: FeedSettings) -> None: ...
    def stop_feed(self) -> None: ...
    def latest(self) -> Frame | None: ...
    def subscribe(self, max_fps: float | None = None, queue_size: int = 8) -> Subscription: ...
    def close(self) -> None: ...
```

`Frame`: `image` (ndarray), `index` (per service, increasing), `time_utc` (ISO 8601), `monotonic_s`,
`exposure_us`, `gain`, `kind` (`feed` or `snapshot`), `requested_by` (e.g. `measure`, `overview`, `focus`).

**Two modes of the same class:**
- **Direct (feed off, default):** no thread; every call runs in the caller's thread on the driver, exactly
  the device calls of today. `System.getimage()` / `optexpose()` call the service instead of `Camera`
  directly; command sequences and images do not change.
- **Threaded (feed on):** one camera thread owns the driver. Calls from other threads become requests in
  a priority queue; the thread serves them between feed frames.

**Snapshots win over the feed:** a snapshot request is served after the current feed frame; the thread
applies the snapshot's (measurement) settings, takes the image, restores the feed settings and resumes the
feed. The caller blocks until its frame is there, so `measure()`, the overview and the tools keep their
synchronous semantics; the added latency is at most one feed frame plus a settings change.

**Exposure conflicts:** the service keeps two setting sets:
- *measurement settings* — what `optimise_exposure()` and `apply()` set; used for every snapshot, so
  images of `measure()`, overview and tools stay comparable with today's images;
- *feed settings* — from `FeedSettings` (`exposure`: `follow` the measurement exposure (default) or a
  fixed value, `fps`, `aoi`, `binning`/downscale for subscribers).
A feed never changes the measurement settings.

**Subscriptions:** each subscriber has a bounded queue (`queue_size`, drop-oldest) and an optional
`max_fps`; a slow consumer loses frames (counted in `Subscription.dropped`) but never slows the camera
thread or the print.

**Stop and abort:** the camera thread checks a stop event between frames. `Experiment.__exit__` (also on
`KeyboardInterrupt` and exceptions) calls `stop_feed()` / `close()` in a `finally`; the thread is joined
with a timeout bounded by one frame (`imageRequestWaitFor` timeout of the current exposure, once T102
has fixed its unit). Recordings
are closed before the driver (§5). A failing driver in the feed stops the feed with a logged error; it
does not stop the print, and later snapshots raise as today.

**Thread safety of the other devices:** the camera thread never calls the controller or the DHM. Positions
for snapshots are read by the requesting (main) thread as today.

## 4. Mapping frames to the print

Feed frames carry no stage position (the controller is only used by the main thread). The mapping comes
from times: the print loop already stores start and end time per layer (`/progress`, T59), and the
service stores the time of every frame. A recording stores the frame times; the table `segments` (§5)
is computed at the end of each recording from both.

## 5. Recording (T94)

- A recording is a subscriber that writes frames in its own writer thread (encoding never runs in the
  camera thread).
- **Scope** (setting `camera_recording`, per experiment with override per structure, as the other
  structure settings of `INFORMATION_MODEL.md` §4): `off` (default), `structure` (one recording per
  structure from the start of its first printed layer to the end of its last layer — the maintainer's
  wish), `experiment` (from the first to the last structure).
- **Files:** `<experiment folder>/recordings/<structure or "experiment">_s<session>.<ext>`; never inside
  `experiment.h5` (size, F3).
- **Table in `experiment.h5`:** `/recordings/<id>`: attributes `file` (relative path), `scope`,
  `structure`, `container`, `codec`, `fps_requested`, `fps_actual`, `width`, `height`, `exposure_us`,
  `started`, `ended`, `frames`, `dropped`, `end_reason` (`finished`, `aborted`, `size_limit`, `disk_space`,
  `error`); datasets `frame_time_utc` (one per written frame) and `segments` (table: `structure`,
  `layer_id`, `first_frame`, `last_frame`, from `/progress` times).
- **Limits:** a recording stops at `max_size_mb` and when the free disk space of the experiment folder
  drops below `min_free_mb`; both with an `end_reason`, the print goes on.
- **Raw data rate (fact, not a measurement):** a full 1280 × 1024 8-bit frame is 1.3 MB, so 5 fps
  uncompressed are 6.5 MB/s. The compressed rate depends on codec and image content and is measured in
  T94 on the lab PC before defaults for the limits are fixed.

## 6. Live feed interface (T95)

`experiment.camera.subscribe(max_fps=…)` (or `System.camera_service`) gives a `Subscription` that yields
`Frame`s with timestamps while the experiment prints; the GUI (F15) and tests use it. The feed is started
by `Experiment(camera_feed=FeedSettings(...))` or by a running recording; without either, no thread runs.
A headless dummy test subscribes during a dry run and receives frames with increasing times.

## 7. Dummy backend

`DummyCameraDriver` is used by the threaded service unchanged; its images may encode the frame index (as a
small pattern) so that tests can check ordering and drops. Tests use a short feed with a real thread and a
bounded number of frames; the virtual clock of `SimulatedWorld` is used for the `time_utc` values.

## 8. Decisions

The table below is the proposal of the draft (2026-11-16); §8.1 records what was decided.

| ID | Question | Options | Proposal |
|---|---|---|---|
| C1 | Frame rate of feed and recording | fixed value; as fast as the exposure allows | 5 fps default, configurable; the actual rate is stored (`fps_actual`). |
| C2 | Container and codec | (a) MP4 with OpenCV's built-in `mp4v` (lossy, small, plays on Windows); (b) AVI with MJPG (lossy, larger, plays everywhere); (c) lossless HDF5 file per recording (uint8 frames, gzip; large, for analysis) | (a) as default for the "video of the structure"; (c) selectable (`container = "h5"`) when the frames are wanted for analysis. OpenCV is already a dependency; no new package. |
| C3 | Resolution | full sensor; AOI around the structure; downscaled | Full sensor at the measurement AOI (what snapshots see); optional `downscale` factor in `FeedSettings`. |
| C4 | Storage location and size limit | inside / next to the experiment folder; limits | `recordings/` in the experiment folder; `max_size_mb` and `min_free_mb` configurable, defaults fixed after the measurement in T94 (until then: no size limit, `min_free_mb` = 1024). |
| C5 | Feed exposure | follow the measurement exposure; own fixed value | Follow by default; a fixed value can be set when the laser light saturates the image during printing. |

### 8.1 Decided 2026-11-18

| ID | Decision |
|---|---|
| prerequisite | T102 (the camera image timeout uses the exposure in µs as if it were ms) is fixed before T93 starts. |
| C1 | 5 fps default, configurable up to the exposure limit; the actual rate is stored (`fps_actual`). |
| C2 | **MP4 `mp4v` default** (the video is for documentation only, not for analysis); lossless `h5` opt-in (`container = "h5"`); **AVI / MJPG dropped**. Export to H.264 MP4 for talks, or `avc1` directly if T94 shows it works (the Work-PC has an Intel QuickSync H.264 encoder). |
| C3 | Full sensor at the measurement AOI; optional `downscale` factor in `FeedSettings`. |
| C4 | `recordings/` in the experiment folder; `max_size_mb` and `min_free_mb` configurable; defaults after the measurement in T94 (until then no size limit, `min_free_mb` = 1024). The Work-PC has ≈ 205 GB free (2026-11-18). |
| C5 | Follow the measurement exposure by default; a fixed value can be set. |
| overview | The stitched camera overview before / after the print (T28, `overview_capture=True`) keeps running as snapshots through the camera service and gets an optional **downscale factor** for the stored mosaic. |

## 9. Tests

- Direct mode: command sequence and images of the existing dry runs unchanged (T93).
- Threaded mode: a snapshot during the feed returns a `snapshot` frame with the measurement exposure and
  the feed resumes with its own settings; a slow subscriber drops frames without slowing the feed; stop on
  exception and on `KeyboardInterrupt` joins the thread (T93, T95).
- Recording on the dummy backend: one file per structure, `/recordings` table with frame times and
  segments matching `/progress`; size and disk limits end the recording, not the print (T94).

## 10. Mapping to the todos

| Todo | Sections |
|---|---|
| T93 Camera service | §3, §7, C5 |
| T94 Recording | §4, §5, C1–C4 |
| T95 Live feed interface | §6 |

## 11. Approval

Waiting for maintainer approval. Implementation (T93–T95) starts only when this line reads
`Status: approved <date>` at the top of the document, with the answers to C1–C5. **Done 2026-11-18** (§8.1).
