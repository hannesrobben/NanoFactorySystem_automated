"""Hardware-free test suite for Model3D_Slicer (work order §3.7 + DoD §8)."""
import json
import re
import sys
import tempfile
from pathlib import Path

import numpy as np
import trimesh

from nanofactorysystem.devices.coordinate_system import (
    CoordinateSystem, Point3D, Unit)
from nanofactorysystem.aerobasic.programs.drawings.model3d import Model3D_Slicer
from nanofactorysystem.aerobasic.slicer import SlicingParameters, JobParameters

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


# Experiment-like coordinate system: µm in, mm out (matches the example
# program: 7.5 µm → 0.0075 mm on galvo axes).
def make_cs(offset_x=163_000.0, offset_y=104_000.0, z_off=9_800.0):
    return CoordinateSystem(offset_x=offset_x, offset_y=offset_y,
                            z_function=z_off, unit=Unit.um)


print("== T1: cube STL end-to-end ==")
# 20x20x2 µm cube written as an STL in mm (tests unit conversion too)
cube = trimesh.creation.box(extents=(0.020, 0.020, 0.002))  # mm
cube.apply_translation([0.5, 0.3, 0.7])  # deliberately off-centre in mm
tmp = Path(tempfile.mkdtemp())
stl_path = tmp / "cube.stl"
cube.export(stl_path)

structure = Model3D_Slicer(
    center=Point3D(0, 0, -1),
    source=stl_path,
    unit="mm",
    velocity=20_000,          # grating convention (µm/s band)
    power=None,               # avoid calibration-file dependency
    hatch_size=1.0,           # µm
    slice_size=0.5,           # µm
    hatch_strategy="alternating",
    ground_truth_path=tmp / "cube_gt.glb",
)

job = structure.toolpath_job
n_layers_expected = round(2.0 / 0.5)  # 2 µm height, 0.5 µm slices
check("job has groups", len(job.groups) > 0, f"{len(job.groups)} groups")
check("n_layers ≈ height/slice_size",
      abs(len(job.groups) - n_layers_expected) <= 1,
      f"{len(job.groups)} vs expected ~{n_layers_expected}")
check("job cached (same object)", structure.toolpath_job is job)

print("== T2: re-centering ==")
all_pts = np.vstack([e.points for g in job.groups for e in g.elements])
xy_center = (all_pts[:, :2].min(axis=0) + all_pts[:, :2].max(axis=0)) / 2
z_min_groups = min(g.z_um for g in job.groups)
check("footprint centred at (0,0)", np.allclose(xy_center, 0, atol=1e-6),
      f"centre={xy_center}")
check("first layer near base (z≈ε)", 0 <= z_min_groups <= 0.5 + 1e-6,
      f"z_min={z_min_groups:.4f} µm")
check("extent ≈ 20 µm (mm→µm conversion)",
      abs((all_pts[:, 0].max() - all_pts[:, 0].min()) - 20.0) < 1.5,
      f"x-extent={all_pts[:,0].max()-all_pts[:,0].min():.2f} µm")
off = structure.toolpath_job.meta["recenter_offset_um"]
check("recenter offset recorded (mm source → µm)",
      abs(off["x"] - 500.0) < 1e-6 and abs(off["z"] - 699.0) < 1.5,
      f"offset=({off['x']:.1f},{off['y']:.1f},{off['z']:.1f})")

print("== T3: iterate_layers → programs ==")
cs = make_cs()
programs = list(structure.iterate_layers(cs))
check("one program per non-empty layer", len(programs) == len(job.groups),
      f"{len(programs)} programs / {len(job.groups)} groups")
check("nothing skipped for pure-infill job",
      structure.skipped_elements_report() == {},
      str(structure.skipped_elements_report()))

text0 = programs[0].to_text(add_timestamp=False)
check("IFOV ON present", "IFOV ON" in text0)
check("IFOV OFF present", "IFOV OFF" in text0)
check("CRITICAL START present", "CRITICAL START" in text0)
check("LASEROVERRIDE AUTO present", "GALVO LASEROVERRIDE A AUTO" in text0)

# Galvo line pattern: RAPID to segment start (laser off), LINEAR to end.
rapid_ab = re.findall(r"RAPID A(-?\d+\.?\d*) B(-?\d+\.?\d*)", text0)
linear_ab = re.findall(r"LINEAR A(-?\d+\.?\d*) B(-?\d+\.?\d*)", text0)
check("RAPID = LINEAR + 1 (RESET_GALVO adds one RAPID A0 B0)",
      len(rapid_ab) == len(linear_ab) + 1 and len(linear_ab) >= 15,
      f"{len(rapid_ab)} RAPID / {len(linear_ab)} LINEAR (≈21 hatch lines expected)")

# µm→mm scaling on galvo: ±10 µm half-extent → ±0.010 mm
a_vals = np.array([float(a) for a, b in linear_ab + rapid_ab])
b_vals = np.array([float(b) for a, b in linear_ab + rapid_ab])
check("galvo coords scaled µm→mm (|A|,|B| ≤ ~0.010)",
      np.abs(a_vals).max() <= 0.0101 and np.abs(b_vals).max() <= 0.0101,
      f"max|A|={np.abs(a_vals).max():.4f} mm, max|B|={np.abs(b_vals).max():.4f} mm")

# Reference-point RAPID: world placement of stage axes (X/Y offsets + z_function)
m = re.search(r"RAPID X(-?\d+\.?\d*) Y(-?\d+\.?\d*) Z(-?\d+\.?\d*)", text0)
check("reference RAPID has stage offsets applied",
      m is not None and abs(float(m.group(1)) - 163.0) < 0.001
      and abs(float(m.group(2)) - 104.0) < 0.001,
      f"X={m.group(1)} Y={m.group(2)} Z={m.group(3)} (mm)" if m else "no match")
# Z = center.Z(-1) + layer_z + z_function(9800) in µm → ≈ 9.799 mm
z_val = float(m.group(3))
check("reference Z = center.Z + layer_z + z_offset",
      abs(z_val - (9_800.0 - 1.0 + job.groups[0].z_um) * 1e-3) < 1e-4,
      f"Z={z_val} mm")

print("== T4: alternating strategy across layers ==")
if len(programs) >= 2:
    t0, t1 = (programs[i].to_text(add_timestamp=False) for i in (0, 1))
    def dominant_dir(t):
        pairs = list(zip(re.findall(r"RAPID A(-?\d+\.?\d*) B(-?\d+\.?\d*)", t),
                         re.findall(r"LINEAR A(-?\d+\.?\d*) B(-?\d+\.?\d*)", t)))
        dx = np.mean([abs(float(l[0]) - float(r[0])) for r, l in pairs])
        dy = np.mean([abs(float(l[1]) - float(r[1])) for r, l in pairs])
        return "X" if dx > dy else "Y"
    d0, d1 = dominant_dir(t0), dominant_dir(t1)
    check("alternating hatch flips direction between layers", d0 != d1,
          f"layer0 along {d0}, layer1 along {d1}")

print("== T5: to_json serializable + provenance ==")
js = structure.to_json()
dumped = json.dumps(js)  # must not raise, no default=str
check("json.dumps without default=str", isinstance(dumped, str))
for key in ("params", "recipe", "time_estimate", "preprocess",
            "recenter_offset_um", "n_groups", "mark_length_um"):
    check(f"provenance key '{key}' present", key in js and js[key] is not None)
check("no bulk data embedded (compact provenance)",
      len(dumped) < 6000 and '"values"' not in dumped,  # counts ok, arrays not
      f"{len(dumped)} chars")

print("== T6: save_job (HDF5) ==")
h5_path = structure.save_job(tmp / "job")
import h5py
with h5py.File(h5_path) as f:
    check("job.h5 written with groups + time_estimate",
          "groups" in f and "time_estimate" in f and "metadata" in f,
          f"keys={list(f.keys())}")
check("estimated_print_time_s > 0", structure.estimated_print_time_s > 0,
      f"{structure.estimated_print_time_s:.2f} s")

print("== T7: experiment structure_program simulation (drop-in) ==")
# Mimics experiment.py: enumerate iterate_layers, write per-layer files, concat
prog_dir = tmp / "programs"; prog_dir.mkdir()
full_text = []
for layer_id, layer in enumerate(structure.iterate_layers(make_cs())):
    t = layer.to_text(add_timestamp=False)
    (prog_dir / f"program_model3d.{layer_id:03d}.txt").write_text(t)
    full_text.append(t)
combined = "\n".join(full_text)
(prog_dir / "program_model3d.txt").write_text(combined)
check("per-layer files written", len(list(prog_dir.glob("program_model3d.0*.txt"))) == len(programs))
check("combined program non-trivial", len(combined) > 2000, f"{len(combined)} chars")
check("center_point contract", structure.center_point.X == 0 and structure.center_point.Z == -1)

print("== T8: params object precedence (A5) ==")
import logging
logging.disable(logging.CRITICAL)  # silence expected warning
sp = SlicingParameters(layer_height_um=1.0, hatch_spacing_um=2.0)
s2 = Model3D_Slicer(center=Point3D(0, 0, 0), source=cube.copy(), unit="mm",
                    velocity=20000, params=sp, hatch_size=99.0)  # conflict
logging.disable(logging.NOTSET)
check("params wins over kwargs",
      s2.params.slicing.hatch_spacing_um == 2.0
      and s2.params.slicing.layer_height_um == 1.0)
check("in-memory Trimesh path works", len(s2.toolpath_job.groups) >= 2,
      f"{len(s2.toolpath_job.groups)} groups")
check("caller mesh not mutated by re-centering",
      abs(cube.bounds[0][2] - 0.699) < 1e-6, f"caller z_min={cube.bounds[0][2]}")

print("== T9: fail-fast validation ==")
def raises(fn, exc):
    try:
        fn(); return False
    except exc:
        return True
check("unknown unit", raises(lambda: Model3D_Slicer(
    center=Point3D(0,0,0), source=cube, velocity=20000, unit="parsec"), ValueError))
check("missing file", raises(lambda: Model3D_Slicer(
    center=Point3D(0,0,0), source="nope.stl", velocity=20000), FileNotFoundError))
check("velocity > 25000", raises(lambda: Model3D_Slicer(
    center=Point3D(0,0,0), source=cube, velocity=30000), ValueError))
check("slice_size <= 0", raises(lambda: Model3D_Slicer(
    center=Point3D(0,0,0), source=cube, velocity=20000, slice_size=0), ValueError))
check("bad params type", raises(lambda: Model3D_Slicer(
    center=Point3D(0,0,0), source=cube, velocity=20000, params={"x": 1}), TypeError))

print("== T10: stage-2 routing — contours now rendered via IFOV_PolyLines ==")
s3 = Model3D_Slicer(center=Point3D(0,0,0), source=cube.copy(), unit="mm",
                    velocity=20000,
                    hatch_size=1.0, slice_size=1.0, num_contour_lines=1)
progs3 = list(s3.iterate_layers(make_cs()))
check("nothing skipped anymore (contours rendered)",
      s3.skipped_elements_report() == {}, str(s3.skipped_elements_report()))
t3 = progs3[0].to_text(add_timestamp=False)
check("two IFOV blocks per layer (contour + infill)",
      t3.count("IFOV ON") == 2 and t3.count("ENCODER OUT Y OFF") == 2,
      f"{t3.count('IFOV ON')} IFOV ON blocks")
# Kontur-Block kommt VOR dem Infill-Block (docs/01 §6)
first_on = t3.index("IFOV ON")
block1 = t3[first_on:t3.index("IFOV OFF", first_on)]  # bis Blockende, ohne Header von Block 2
second_on = t3.index("IFOV ON", first_on + 1)
import re as _re
b1_rapids = _re.findall(r"RAPID A(-?\d+\.?\d*) B(-?\d+\.?\d*)", block1)
b1_linears = _re.findall(r"LINEAR A(-?\d+\.?\d*) B(-?\d+\.?\d*)", block1)
check("block 1 is the contour block (1 RAPID, ring of LINEARs)",
      len(b1_rapids) == 1 and len(b1_linears) >= 4,
      f"{len(b1_rapids)} RAPID / {len(b1_linears)} LINEAR")
# geschlossener Ring: letzter LINEAR == erster RAPID (Rückkehr zum Start)
check("ring closes back to its start vertex",
      b1_linears[-1] == b1_rapids[0],
      f"start={b1_rapids[0]} end={b1_linears[-1]}")
# Ring liegt außen: |A| des Konturstarts >= max |A| des Infills
block2 = t3[second_on:]
b2_all = _re.findall(r"(?:RAPID|LINEAR) A(-?\d+\.?\d*) B", block2)
check("contour ring lies outside the (inset) infill",
      abs(float(b1_rapids[0][0])) >= max(abs(float(a)) for a in b2_all) - 1e-9,
      f"contour|A|={abs(float(b1_rapids[0][0])):.4f} vs infill max|A|="
      f"{max(abs(float(a)) for a in b2_all):.4f}")

print("== T11: IFOV_PolyLines unit tests ==")
from nanofactorysystem.aerobasic.programs.drawings.model3d import IFOV_PolyLines
from nanofactorysystem.devices.coordinate_system import Point2D
ref = Point3D(0, 0, 5)
sq = [Point2D(-5,-5), Point2D(5,-5), Point2D(5,5), Point2D(-5,5)]
open_path = [Point2D(0,0), Point2D(3,0), Point2D(3,3)]
pl = IFOV_PolyLines(ref, [sq, open_path], velocity=20000,
                    closed=[True, False])
tp = next(iter(pl.iterate_layers(make_cs()))).to_text(add_timestamp=False)
ab_rapids = _re.findall(r"RAPID A(-?\d+\.?\d*) B(-?\d+\.?\d*)", tp)
ab_linears = _re.findall(r"LINEAR A(-?\d+\.?\d*) B(-?\d+\.?\d*)", tp)
check("RAPIDs: RESET_GALVO + one per path",
      len(ab_rapids) == 1 + 2, f"{len(ab_rapids)}")
check("LINEARs: ring 4 (3 edges + close) + open path 2",
      len(ab_linears) == 4 + 2, f"{len(ab_linears)}")
check("velocity heuristic inherited from IFOV_Lines (20000 -> 20 mm/s)",
      pl.velocity == 20.0, f"{pl.velocity}")
check("single closed flag broadcast",
      IFOV_PolyLines(ref, [sq], velocity=20000, closed=True).closed == [True])
def raises2(fn, exc):
    try:
        fn(); return False
    except exc:
        return True
check("empty polylines rejected",
      raises2(lambda: IFOV_PolyLines(ref, [], velocity=20000), ValueError))
check("1-vertex path rejected",
      raises2(lambda: IFOV_PolyLines(ref, [[Point2D(0,0)]], velocity=20000), ValueError))
check("closed 2-vertex path rejected",
      raises2(lambda: IFOV_PolyLines(ref, [sq[:2]], velocity=20000, closed=True), ValueError))
check("flag/path count mismatch rejected",
      raises2(lambda: IFOV_PolyLines(ref, [sq], velocity=20000, closed=[True, False]), ValueError))

print("== T12: PolyLines header identical to IFOV_Lines header (skeleton) ==")
from nanofactorysystem.aerobasic.programs.drawings.lines import IFOV_Lines
il = IFOV_Lines(ref, [[Point2D(0,0), Point2D(1,0)]], velocity=20000)
til = next(iter(il.iterate_layers(make_cs()))).to_text(add_timestamp=False)
def skel_header(t):
    out = []
    for ln in t.splitlines():
        ln = ln.strip()
        if not ln or ln.startswith("'"):
            continue
        out.append(_re.sub(r"-?\d+\.?\d*", "#", ln))
        if out[-1] == "IFOV ON":
            break
    return out
check("IFOV header skeletons identical",
      skel_header(tp) == skel_header(til),
      f"{len(skel_header(tp))} header commands")

print("== T13: two contour rings ordered outer -> inner ==")
s4 = Model3D_Slicer(center=Point3D(0,0,0), source=cube.copy(), unit="mm",
                    velocity=20000,
                    hatch_size=1.5, slice_size=1.0, num_contour_lines=2)
t4 = next(iter(s4.iterate_layers(make_cs()))).to_text(add_timestamp=False)
c_on = t4.index("IFOV ON")
c_block = t4[c_on:t4.index("IFOV OFF", c_on)]
c_rapids = _re.findall(r"RAPID A(-?\d+\.?\d*) B(-?\d+\.?\d*)", c_block)
check("two rings in the contour block", len(c_rapids) == 2, f"{len(c_rapids)} RAPIDs")
r_outer = max(abs(float(c_rapids[0][0])), abs(float(c_rapids[0][1])))
r_inner = max(abs(float(c_rapids[1][0])), abs(float(c_rapids[1][1])))
check("outer ring printed before inner ring", r_outer > r_inner,
      f"start radii {r_outer:.4f} > {r_inner:.4f} mm")

print("== T14: provenance reflects contours + regression of stage-1 json ==")
js4 = s4.to_json()
check("num_contour_lines in provenance",
      js4["params"]["slicing"]["num_contour_lines"] == 2)
check("contour elements counted in IR",
      js4["n_elements"] > 0 and json.dumps(js4) is not None)

print()
print(f"===== {len(PASS)} passed, {len(FAIL)} failed =====")
if FAIL:
    print("FAILED:", FAIL)

# Exit code only when run as a script; test_model3d.py runs this module with runpy
if __name__ == "__main__":
    sys.exit(1 if FAIL else 0)
