# Drawings Module - Modular Structure

> **Note (2026-11-17, translation):** this README was translated from German without changing its
> content. It describes how the modular structure was originally installed. The current tree differs:
> `height_functions.py` lives in this folder (`height_function_structures/`), not at the `drawings/`
> level; `apertures.py`, `laser_segments.py`, `hatch_generator.py` and `tile_manager.py` are at the
> `drawings/` level. The installation steps below are historical.

## Overview

The new modular structure separates reusable components from specific structure implementations.

```
drawings/
├── __init__.py                  # Main init with all imports
├── base.py                      # DrawableObject, etc. (existing)
├── lines.py                     # PolyLine, Rectangle3D, etc. (existing)
│
├── tile_manager.py              # ✓ STANDALONE - stays as it is
├── apertures.py                 # ★ NEW STANDALONE - for all structures!
├── laser_segments.py            # ★ NEW STANDALONE - for all structures!
├── hatch_generator.py           # ★ NEW STANDALONE - for all structures!
├── height_functions.py          # ★ NEW STANDALONE - mathematical functions
│
└── height_function_structures/  # Grating structures
    ├── __init__.py
    ├── slicer.py
    └── structures.py
```

## Installation

### Step 1: Copy the new files

```bash
cd nanofactorysystem/aerobasic/programs/drawings/

# Add the new standalone modules
cp drawings_modular/apertures.py .
cp drawings_modular/laser_segments.py .
cp drawings_modular/hatch_generator.py .
cp drawings_modular/height_functions.py .

# Add the height function structures folder
cp -r drawings_modular/height_function_structures/ .

# Replace __init__.py (make a BACKUP!)
cp __init__.py __init__.backup.py
cp drawings_modular/__init__.py .
```

### Step 2: Adjust the imports

If you get import errors, adjust `__init__.py`:

```python
# Comment out what is missing:
# from .lines import XLines, YLines, ZLines  # if not available
```

## Advantages of the modular structure

### 1. Apertures for ALL structures

```python
from nanofactorysystem.aerobasic.programs.drawings import Apertures

# Now EVERY structure can use apertures!
aperture = Apertures.circular(radius=50)
aperture = Apertures.rectangular(width=100, height=80)
aperture = Apertures.annular(inner_radius=20, outer_radius=50)

# Combine
aperture = Apertures.subtract(
    Apertures.circular(radius=50),
    Apertures.rectangular(width=20, height=20)
)
```

### 2. HatchGenerator for arbitrary shapes

```python
from nanofactorysystem.aerobasic.programs.drawings import HatchGenerator, HatchConfig

# For Rectangle3D with an aperture (future)
hatch_gen = HatchGenerator(HatchConfig(hatch_size=0.3, hatch_angle_deg=45))

# Hatch with an aperture
segments = hatch_gen.hatch_with_aperture(
    x_min=-50, x_max=50,
    y_min=-50, y_max=50,
    z_level=0,
    aperture=Apertures.circular(radius=40),
    resolution=500
)
```

### 3. LaserSegments instead of PolyLines

```python
from nanofactorysystem.aerobasic.programs.drawings import (
    LaserSegments, LaserSegmentsConfig, SortingStrategy
)

# For discontinuous laser paths
config = LaserSegmentsConfig(
    velocity=10000,
    acceleration=100000,
    sorting_strategy=SortingStrategy.SERPENTINE
)

laser_segments = LaserSegments(segments=my_segments, config=config)
```

## Example: binary grating

```python
from nanofactorysystem.aerobasic.programs.drawings import (
    BinaryGrating, Apertures
)
from nanofactorysystem.devices.coordinate_system import Point3D

grating = BinaryGrating(
    center=Point3D(0, 0, -2),
    width=100,
    length=100,
    period=10,
    height=2,
    duty_cycle=0.5,           # or 5 for 5 µm
    grating_angle_deg=0.0,
    base_height=2.0,
    
    # Fabrication
    hatch_size=0.2,
    slice_size=0.2,
    velocity=10000,
    acceleration=100000,
    
    # Aperture (NEW: standalone module!)
    aperture=Apertures.circular(radius=50),
    
    # Hatching
    hatch_angle_deg=0.0,
    alternating_hatch=True,
    
    # Tiling
    fov_size=(150, 150),
    usable_fov_fraction=0.85,
    grid_resolution=500       # NOT 10000!
)

# Iteration with a choice of strategy
for program in grating.iterate_layers(cs, strategy="TILE_FIRST"):
    ...
```

## Strategy comparison

```python
# TILE_FIRST: one tile completely, then the next
for program in grating.iterate_layers(cs, strategy="TILE_FIRST"):
    ...

# LAYER_FIRST: layer 1 in all tiles, then layer 2, etc.
for program in grating.iterate_layers(cs, strategy="LAYER_FIRST"):
    ...
```

## Future extensions

With the modular structure you can easily:

1. extend **Rectangle3D with an aperture**
2. extend **Stair with an aperture**
3. add **new structures** that use all modules
4. implement **STL import** via `HeightFunctions.from_array()`

## File structure after installation

```
nanofactorysystem/aerobasic/programs/drawings/
├── __init__.py                  # Updated
├── base.py                      # Unchanged
├── lines.py                     # Unchanged
├── tile_manager.py              # Unchanged
│
├── apertures.py                 # ★ NEW
├── laser_segments.py            # ★ NEW
├── hatch_generator.py           # ★ NEW
├── height_functions.py          # ★ NEW
│
└── height_function_structures/  # ★ NEW
    ├── __init__.py
    ├── slicer.py
    └── structures.py
```
