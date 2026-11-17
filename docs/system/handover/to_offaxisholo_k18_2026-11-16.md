# Input from NanoFactorySystem_automated for the planning session K18 (2026-11-16)

For: the cross-repository planning session OffAxisHolo K18 (reference mask, averaging, stitching; global
decision G10, SA1–SA7). Prepared in T100; to be reviewed by the maintainer before the session.

Basis on this side: `docs/design/OPERATING_MODES.md` (draft, T72: `LayerTarget`, §4.4 reference mask),
`docs/design/DHM_SERVICE_INTEGRATION.md` (draft, T71: `CaptureContext`, recipe), `INFORMATION_MODEL.md`
(approved: material snapshot). Both drafts wait for approval, so everything below is a proposal.

## 1. What this side knows, and when

| Information | Known when | Where |
|---|---|---|
| Footprint of a structure after layer n (sliced: union of the design cross-sections of the printed layers; drawn: laser-on toolpath dilated by the voxel width) | before the print (computed from the programs, no images needed); recomputable at any time | computed on the Working-PC (`LayerTarget`, T89); not stored per layer, reproducible from the stored slicer job and layer programs |
| Footprints of the other structures of the experiment that are printed already (grid neighbours, corner markers, QR code) | before each capture | same; the layout is stored in `/layout` |
| Areas of earlier experiments on the substrate | before the experiment | substrate index (`area_um`, rectangles only) |
| Commanded and actual stage position of the capture | at the capture | `CaptureContext` (`commanded_um`, `actual_um`), already planned |
| Substrate height (plane fit) | before the print | `/plane_fit`; `LayerTarget.substrate_z_um` |

So the a priori information is available **before the capture on the Working-PC**, but **not in the
service** unless it travels with the request.

## 2. Coordinate system

- Footprints in **absolute stage coordinates in µm** (X, Y as the A3200 axis positions, the same frame as
  `commanded_um` / `actual_um`), as polygons (list of rings, outer ring counter-clockwise, holes
  clockwise).
- Heights (target maps) are relative to the substrate surface along the build direction; the reference
  mask needs only the 2-D footprint.
- The mapping stage µm → DHM camera pixel (scale, rotation, flip, offset; per objective) is **not** known
  here and must not be taken from the device parameters (finding B17: the Koala pixel size of
  configuration 180 is wrong for 63x). It is a calibration owned by MIRA (MI-41, MI-50) and stored here
  with the experiment (`/calibration/dhm/mapping`, proposal).

## 3. Proposals

**SA1 — source of the mask:** a priori from the print job, by default; the a posteriori detection of MIRA
(Otsu on a first reconstruction, SA3) runs as a **check**: if the a priori reference region shows
structure (e.g. phase variance above a limit), the result gets a warning, and the recipe may ask for the
a posteriori mask instead (`reference_mask.source = "a_posteriori"`).

**Occupied region instead of one footprint:** the reference region must exclude everything that is
printed inside the DHM field of view, not only the structure being measured: the printed part of the
current structure, the printed neighbours, corner markers and QR code, and rectangles of earlier
experiments. This side sends the union of these as `occupied_um`.

**SA2 — format and coordinates:** in `CaptureContext` (not the recipe, because it changes with every
layer):

```json
"reference_mask": {
  "occupied_um": [[[x, y], …], …],
  "frame": "stage_um",
  "pose_tolerance_um": null,
  "source": "a_priori"
}
```

The service rasterises it into a pixel mask with the mapping of §2 and the actual stage position of the
capture. `pose_tolerance_um` has no proposed value yet (see below).

**Margin / pose tolerance (who sets it):** split in two parts:
- `pose_tolerance_um` (this side, in the context): stage repeatability plus the uncertainty of the stage ↔
  pixel mapping — process and calibration data, measured, not assumed;
- `optical_margin_um` (recipe, OffAxisHolo default): the zone around an edge in which the reconstructed
  phase is disturbed (diffraction, defocus) — an optical property that OffAxisHolo knows best.

The mask is the complement of `occupied_um` dilated by the sum of both. A minimum reference fraction
(`min_reference_fraction`, recipe) below which the result is flagged keeps honest noise numbers.

**SA5 — levelling:** agreed with the OffAxisHolo proposal: OffAxisHolo only aligns the frames of one
measurement; MIRA removes the absolute offset of a product and the offsets between tiles. This side stores
the products as delivered (aligned, not levelled) and stores MIRA's levelled results as analysis results
(`OPERATING_MODES.md` §5).

**Stitching (SA6):** each tile gets its own `occupied_um` from the same source; this side plans the raster
(T85) and can send the planned tile positions with the group, so the mask of every tile is known before
the tiles are taken.

## 4. What this side needs from MIRA (and OffAxisHolo)

1. The stage µm ↔ DHM pixel mapping per objective (MI-41, MI-50): how it is calibrated (target, corner
   markers?), its uncertainty, how often it must be repeated, and a serialisable form so that this side can
   store it and send it (or its id) with the context.
2. The resampling of a `LayerTarget` grid onto the product grid after registration (MI-50, MI-53), and a
   confirmation of the proposed target grid (`OPERATING_MODES.md` §4: half the hatch distance, 0.1–1 µm).
3. From OffAxisHolo: the default `optical_margin_um` per objective and the minimal useful reference area.

## 5. Questions for the session

1. Does the service rasterise the mask (proposal), or does this side send a pixel mask (needs the mapping
   here and the exact crop of the reconstruction)?
2. Are the frames of one measurement aligned with the a priori mask before the first reconstruction, or is
   a first pass without mask acceptable (SA3/SA4)?
3. Where is the stage ↔ pixel mapping stored as master — MIRA's calibration store, the experiment file, or
   the DHM service's parameter set?
4. Which `pose_tolerance_um` is realistic for the 20x and 63x objectives — who measures it, and when?
