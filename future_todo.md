# Future todos

Ideas that are planned but not scheduled. They need more concept work or input from the maintainer.
IDs are F<number> and never reused. To schedule an item, the maintainer (or Claude on request) turns it
into one or more T-todos in `TODO.md` and marks it here as "→ T<n>".

Claude Code: do not implement anything from this file. If a todo in `TODO.md` names an extension point
for an item here, build only that extension point.

Each entry: **Goal** (what should be achieved), **Context**, **Prerequisites** (todos that must be done
first), **Watch out for** (pitfalls and constraints), **Open questions** (for the maintainer).

---

## F1: Restart an aborted print after an orientation check at the double corner
- **Goal:** Resume an aborted print, possibly after the substrate was removed and put back, by locating
  the double corner, checking position and rotation of the substrate, and correcting the coordinate
  system before printing continues.
- **Context:** The double corner marks the orientation of an experiment. Its position is stored from T50 on.
- **Prerequisites:** T47, T50 (stored double-corner position and orientation), T44 (single plane fit).
- **Watch out for:** Detection of the double corner in camera and/or DHM images; rotation and translation
  must be estimated from at least two features; the plane has to be fitted again; a wrong alignment
  prints into existing structures, so the user must confirm the estimated transform.
- **Open questions:** Which image source is used for detection? What accuracy is required? Manual or
  automatic confirmation?

## F2: Phase data as slicer input
- **Goal:** The slicer accepts phase data (e.g. from DHM or a DOE design) in addition to height data.
- **Context:** Today the slicer takes meshes and height maps (`aerobasic/slicer/pipeline.slice_geometry`).
  T51 introduces a program-source enum that can be extended.
- **Prerequisites:** T51, T54.
- **Watch out for:** Conversion phase → height needs wavelength and refractive index of the cured resin
  (depends on dose, see voxel database T53); phase wrapping; units and sign convention consistent with
  OffAxisHolo.
- **Open questions:** Is the conversion done in the slicer or before it? Which refractive-index model?

## F3: Camera video recording in a thread
- **Goal:** The camera records the printing process as video in a background thread.
- **Context:** Useful for illustration only, no value for production. Lowest priority.
- **Prerequisites:** T45 (camera capture only on request), T47.
- **Watch out for:** The camera must not be used by `measure()` at the same time (locking); the thread must
  stop cleanly on abort; file size (store video next to, not inside, the HDF5 file); timestamps to map
  frames to layers.
- **Open questions:** Frame rate, codec, storage location.

## F4: DHM reconstruction on the DHM PC and interplay of the two PCs
- **Goal:** Holograms are reconstructed on the fly on the GPU of the PC that controls the DHM, using the
  OffAxisHolo library; the printing PC receives reconstructed data (phase, amplitude, derived values)
  instead of or in addition to the raw holograms.
- **Context:** The DHM is controlled by another PC. T47 already provides a generic method to store named
  DHM products with metadata; this is the receiving side of the interface.
- **Prerequisites:** T46, T47. Needs a separate concept session with input from the maintainer.
- **Watch out for:** Only the printing PC writes the experiment file (T42); transport (network share,
  socket, message queue), latency and what happens when the DHM PC is slow or offline; versioning of the
  reconstruction parameters; the DHM PC also orchestrates multiple captures (F5) and their alignment.
- **Open questions:** Transport protocol; which products are sent; who triggers a capture; where are raw
  holograms kept, and for how long?

## F5: Multiple holograms at shifted positions for speckle reduction
- **Goal:** Several holograms of the same structure are taken at slightly shifted stage positions, aligned
  and averaged after reconstruction to reduce speckle noise.
- **Context:** T46 stores the stage position of every capture and allows a list of capture offsets.
- **Prerequisites:** T46, F4 (reconstruction, alignment and averaging run on the DHM PC).
- **Watch out for:** The stage position is the reference for alignment; sub-pixel registration; the raw
  holograms may be deleted after reconstruction and averaging, but only after the result is stored;
  capture time per structure grows with the number of positions.
- **Open questions:** Number and pattern of positions; shift amplitude; which averaging (complex field or
  phase)?

## F6: DHM stitching for structures larger than the DHM field of view
- **Goal:** Structures larger than the DHM FOV (which is smaller than the production FOV) are captured as
  a grid of holograms and stitched, so that large structures can be evaluated.
- **Context:** Capture grid = structure size / (DHM FOV × (1 − overlap)); T46 provides positions per
  capture. Existing code to reuse: `tools/Stitch` and `aerobasic/programs/drawings/tile_manager.py`.
- **Prerequisites:** T46, F4.
- **Watch out for:** Overlap of 10–20 % for registration; phase offsets and tilt between tiles must be
  equalised before stitching; capture time and data volume grow with the square of the structure size;
  the stitched result and the tiles should both be stored.
- **Open questions:** Stitching on the DHM PC or offline? Required overlap?

## F7: Slicing, hatching and adaptive printing strategies
- **Goal:** The slicer offers several slicing and hatching strategies and adaptive printing (e.g. power
  or spacing adapted per layer or line).
- **Context:** Includes the open slicer roadmap items (formerly T40, N095): contour as polyline, tilted
  slicing, shell strategy, experiment hierarchy, study framework, translator. T54 passes the voxel model to
  the hatching strategies; T31 enables power per layer and line.
- **Prerequisites:** T53, T54, T31.
- **Watch out for:** Strategies need a common interface (input: geometry + voxel model + laser
  parameters; output: toolpath IR); every strategy must be stored in the metadata to keep prints
  reproducible; compare strategies with the study framework.
- **Open questions:** Which strategies first? Which quality metric decides between them?

## F8: Dip-in as drop direction
- **Goal:** Besides drop direction UP and DOWN, the system supports dip-in lithography.
- **Context:** In dip-in the objective is immersed in the resin; interface detection, plane fitting and
  the z computation work differently. T43 documents all places that depend on the drop direction.
- **Prerequisites:** T43, T44.
- **Watch out for:** Different z sign and working distance; interface detection (focus/layer tools)
  sees the resin–substrate interface through the resin; zMax safety limits; objective-specific
  parameters in the config.
- **Open questions:** Which objective? Which substrates?
