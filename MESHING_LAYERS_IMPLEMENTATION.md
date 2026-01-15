# Custom Meshing Layers for ANSYS - Implementation Guide

**Date:** 2026-01-14
**Status:** Fully Implemented and Working

## Summary

Successfully implemented custom mesh control layers in KQCircuits that export to ANSYS for fine-grained mesh refinement control. The solution uses existing KQCircuits infrastructure (airbridge_pads and airbridge_flyover layers) with a custom simulation class to ensure proper export properties.

---

## Problem Statement

KQCircuits could export mesh control to ANSYS via the `1t1_gap` layer, but we needed:
1. Arbitrary shaped regions for mesh control (not just gap regions)
2. Multiple independent mesh control regions with different refinement levels
3. Regions that don't affect simulation physics (vacuum, zero thickness)
4. Proper export to ANSYS without boundary condition artifacts

---

## Initial Investigation

### KQCircuits Export Pipeline

The layer export process follows this flow:

```
Element geometry (KLayout layers)
    ↓
create_simulation_layers() - extracts regions via region_from_layer()
    ↓
insert_layer() - stores in self.layers with "bottom"/"top"/"material"
    ↓
produce_layers() - partitions/subtracts layers, converts to "z"/"thickness"
    ↓  (adds "layer" key if geometry is within simulation box)
    ↓
export_ansys_json() - writes layers with "layer" key to GDS
    ↓
import_simulation_geometry.py - ANSYS imports GDS
    ↓
mesh_size parameter - applies refinement to matching layers
```

### Key Discovery: Layer Export Requirements

For a layer to be exported to ANSYS, it must:
1. Be created during `create_simulation_layers()` via `insert_layer()`
2. Survive `produce_layers()` partitioning (not become empty)
3. Be within the simulation box boundaries
4. Receive a "layer" key from `produce_layers()` (line 1095 of simulation.py)
5. Be written to GDS file (only happens if "layer" key exists)

---

## Solution Architecture

### Approach: Option 2 + Custom Simulation Class

We used the existing "airbridge_pads" and "airbridge_flyover" layers that KQCircuits already processes (simulation.py:812-815), combined with a custom simulation class to fix their export properties.

### Why This Works

1. **KQCircuits already extracts these layers**: No need to modify core code
2. **Automatic processing**: Geometry from ResonatorSpike flows through naturally
3. **Custom override**: We intercept `produce_layers()` to fix properties before export
4. **Region preservation**: Save original regions before partitioning, restore after

---

## Implementation Details

### 1. Element Design (resonator_spike.py)

Created geometry on the appropriate layers:

```python
# Spike meshing regions (lines 117-120)
spikes_meshing_region = self._make_meshing_region()
self.cell.shapes(self.get_layer("airbridge_pads")).insert(
    spikes_meshing_region
)

# Inductor meshing region (lines 121-124)
self.cell.shapes(self.get_layer("airbridge_flyover")).insert(
    inductor_region
)
```

### 2. Custom Simulation Class (spike_res_sim.py)

Created `ResonatorSpikeMeshingSim` class that overrides `produce_layers()`:

```python
class ResonatorSpikeMeshingSim(BaseSimClass):
    def produce_layers(self, parts):
        # 1. Save original regions before partitioning
        original_regions = {}
        for face_id in self.face_ids:
            for layer_type in ["airbridge_pads", "airbridge_flyover"]:
                layer_name = f"{face_id}_{layer_type}"
                if layer_name in self.layers:
                    original_regions[layer_name] = self.layers[layer_name]["region"].dup()
                    # Set to vacuum, infinitely thin at conductor surface
                    self.layers[layer_name]["material"] = "vacuum"
                    self.layers[layer_name]["bottom"] = 0.0
                    self.layers[layer_name]["top"] = 0.0

        # 2. Call parent (may partition/remove layers)
        super().produce_layers(parts)

        # 3. Restore original regions
        for layer_name, original_region in original_regions.items():
            if layer_name in self.layers:
                # Layer survived - restore original region
                # Remove boundary condition properties
                self.layers[layer_name].pop("excitation", None)
                self.layers[layer_name].pop("background", None)
            else:
                # Layer was removed - re-add it manually
                self.layers[layer_name] = {
                    "z": 0.0,
                    "thickness": 0.0,
                    "layer": sim_layer.layer,
                    "material": "vacuum",
                }
            # Write region to GDS layer
            shapes.insert(original_region)
```

### Key Fixes Applied

#### Fix 1: Position and Thickness
- **Before**: `airbridge_pads` at z=0, thickness=3.4µm; `airbridge_flyover` at z=3.4µm
- **After**: Both at z=0, thickness=0 (infinitely thin sheets at conductor surface)

#### Fix 2: Material
- **Before**: Both were PEC (perfect electrical conductor)
- **After**: Both are vacuum (no effect on simulation physics)

#### Fix 3: Region Preservation
- **Before**: Regions got clipped by gap intersection during partitioning
- **After**: Original rectangular regions restored after partitioning

#### Fix 4: Boundary Conditions
- **Before**: `airbridge_pads` had `excitation: 0` causing perfect E boundary
- **After**: Both layers have no `excitation` or `background` properties (unassigned)

#### Fix 5: Layer Survival
- **Before**: `airbridge_flyover` was removed by `produce_layers()` (subtracted by ground)
- **After**: Manually re-added removed layers after partitioning

### 3. Simulation Parameters (spike_res_sim.py)

```python
sim_parameters = {
    "box": pya.DBox(pya.DPoint(0, -700), pya.DPoint(1000, 2000)),
    # Extended box to include inductor region
}

export_parameters = {
    "mesh_size": {
        "1t1_airbridge_pads": 1,      # Fine mesh around spikes (1 µm)
        "1t1_airbridge_flyover": 6,   # Coarse mesh for inductor (6 µm)
    },
}
```

---

## Technical Challenges Solved

### Challenge 1: Python 3.14 Incompatibility
**Problem**: klayout package had no binary wheels for Python 3.14 on Windows
**Solution**: Created new virtual environment with Python 3.12.8

```bash
py -3.12 -m venv env-kqcircuits-py312
pip install -e klayout_package/python
```

### Challenge 2: Layer Partitioning
**Problem**: `produce_layers()` partitions layers by subtracting overlapping regions
**Solution**: Save original regions before partitioning, restore after

### Challenge 3: Layer Removal
**Problem**: Some layers become empty after partitioning and are removed
**Solution**: Detect removed layers and manually re-add with proper format

### Challenge 4: Boundary Conditions
**Problem**: `excitation` property caused ANSYS to apply perfect E boundaries
**Solution**: Remove `excitation` and `background` properties from layer dict

---

## Verification Process

### Test Script (test_spike_output.py)

Created automated test script to verify:
1. JSON contains both airbridge layers with correct properties
2. OAS file contains geometry on both layers
3. Mesh size parameters are correctly set
4. No unwanted properties (excitation, background)

### Expected Output

**JSON (resonator_spike_*.json):**
```json
"1t1_airbridge_pads": {
    "z": 0.0,
    "thickness": 0.0,
    "layer": 1002,
    "material": "vacuum"
},
"1t1_airbridge_flyover": {
    "z": 0.0,
    "thickness": 0.0,
    "layer": 1005,
    "material": "vacuum"
}
```

**OAS (simulation.oas):**
- `1t1_airbridge_pads`: 2 shapes (spike regions)
- `1t1_airbridge_flyover`: 1 shape (inductor region)

---

## Usage Instructions

### Running Simulations

```bash
# Activate Python 3.12 environment
source env-kqcircuits-py312/Scripts/activate

# Run simulation without opening KLayout
python klayout_package/python/scripts/simulations/spike_res_sim.py --no-gui

# Run with KLayout viewer (default)
python klayout_package/python/scripts/simulations/spike_res_sim.py

# Verify output
python klayout_package/python/scripts/simulations/test_spike_output.py
```

### Adding New Meshing Regions

1. **In your element class** (e.g., resonator_spike.py):
   ```python
   meshing_region = self._make_custom_region()
   self.cell.shapes(self.get_layer("airbridge_pads")).insert(meshing_region)
   ```

2. **In simulation script**:
   ```python
   export_parameters = {
       "mesh_size": {
           "1t1_airbridge_pads": desired_mesh_size_in_um,
       },
   }
   ```

3. **Ensure simulation box encompasses geometry**:
   ```python
   sim_parameters = {
       "box": pya.DBox(pya.DPoint(min_x, min_y), pya.DPoint(max_x, max_y)),
   }
   ```

---

## Alternative Approaches Considered

### Option 1: Custom Simulation Class (More Flexible)
**Pros**: Clean separation, reusable, multiple custom layers
**Cons**: More code, requires understanding simulation internals
**Status**: Partially implemented (we used this for fixing export properties)

### Option 2: Use Existing Layers (Implemented)
**Pros**: No core code changes, works immediately
**Cons**: Limited to two layer types (airbridge_pads, airbridge_flyover)
**Status**: ✓ Chosen solution

### Option 3: Modify Core KQCircuits
**Pros**: Available system-wide, proper design
**Cons**: Requires modifying/maintaining core code, testing
**Status**: Rejected (avoided core modifications)

### Option 4: Simulation Parameters
**Pros**: Flexible per-simulation
**Cons**: Less intuitive, geometry separate from element
**Status**: Not pursued

---

## Key Learnings

### KQCircuits Layer System

1. **Internal vs Export Format**:
   - Internal: `{"bottom": z0, "top": z1, "region": region, "material": mat}`
   - Export: `{"z": z, "thickness": t, "layer": layer_num, "material": mat}`

2. **Layer Key Determines Export**:
   - Only layers with `"layer"` key are written to GDS
   - `produce_layers()` adds this key at line 1095 if geometry is within box

3. **Partitioning Logic**:
   - `produce_layers()` subtracts overlapping regions
   - Metal layers subtract from vacuum/dielectric
   - Can completely remove layers if subtraction leaves nothing

4. **Material Property Effects**:
   - `material=None`: Non-model object, won't be partitioned
   - `material="vacuum"`: Can be partitioned by other layers
   - `material="pec"`: Metal, won't be partitioned

5. **Excitation Property**:
   - `excitation: 0` tells ANSYS to treat as conductor boundary
   - Must be removed for unassigned mesh control regions

### ANSYS Import (import_simulation_geometry.py)

1. **Mesh Size Matching** (lines 519-540):
   ```python
   for mesh_name, mesh_length in mesh_size.items():
       mesh_layers = [n for n in layers if match_layer(n, mesh_name)]
       mesh_objects = [o for l in mesh_layers if l in objects for o in objects[l]]
   ```

2. **Pattern Matching**:
   - Uses glob-style patterns via `match_layer()`
   - `"1t1_airbridge_pads"` matches exactly
   - `"1t1_*"` matches all 1t1 face layers
   - `"*pads"` matches layers ending in "pads"

3. **Object Collection**:
   - Only layers with "layer" key in JSON are imported
   - Objects named as `{layer_name}_*` in ANSYS
   - Mesh refinement applied to matched objects

---

## Future Enhancements

### Potential Improvements

1. **Multiple Mesh Regions Per Layer**:
   - Currently limited to one region type per airbridge layer
   - Could add more layer types (e.g., "mesh_fine", "mesh_coarse")

2. **Per-Face Conductor Z-Coordinates**:
   - Currently hardcoded `conductor_z = 0.0`
   - Could extract from face stack configuration

3. **Automatic Box Extension**:
   - Detect meshing region bounds and auto-extend simulation box
   - Warn if regions are outside box

4. **Mesh Size Validation**:
   - Check if mesh_size layers exist in export
   - Warn about typos or missing layers

5. **Contribute to KQCircuits**:
   - Propose adding generic mesh control layers to core
   - Make this a first-class feature for all users

---

## Files Modified/Created

### Modified Files
1. `spike_res_sim.py` - Added custom simulation class, --no-gui flag, extended box
2. `resonator_spike.py` - Already had meshing regions on airbridge layers

### Created Files
1. `test_spike_output.py` - Verification script for JSON/OAS output
2. `MESHING_LAYER_OPTIONS.md` - Original options analysis document
3. `MESHING_LAYERS_IMPLEMENTATION.md` - This document

### New Environment
1. `env-kqcircuits-py312/` - Python 3.12 virtual environment

---

## Troubleshooting Guide

### Layer Not Appearing in ANSYS

**Check 1**: JSON file has layer with "layer" key
```bash
grep "1t1_airbridge_pads" resonator_spike_*.json
```

**Check 2**: OAS file has geometry on layer
```bash
python test_spike_output.py
```

**Check 3**: Geometry within simulation box
- Compare layer bbox with simulation box in JSON

**Check 4**: mesh_size pattern matches layer name
- Use exact name or glob pattern

### Perfect E Boundary on Mesh Layer

**Problem**: Layer has `excitation: 0` in JSON
**Solution**: Ensure custom simulation class removes this property (line 103-104)

### Rectangular Regions Got Clipped

**Problem**: Regions partitioned by gap intersection
**Solution**: Custom class saves/restores original regions (lines 72, 98, 118)

### Layer Removed After produce_layers

**Problem**: Layer completely subtracted by metal layers
**Solution**: Custom class re-adds removed layers manually (lines 106-117)

---

## Performance Notes

- Export time: ~2-5 seconds for 5 simulations
- OAS file size: ~13 KB per simulation
- JSON file size: ~7 KB per simulation
- No significant performance impact from custom layer handling

---

## References

### KQCircuits Source Code
- `simulation.py:696-901` - create_simulation_layers()
- `simulation.py:913-1098` - produce_layers()
- `simulation.py:465-473` - insert_layer()
- `ansys_export.py:42-80` - export_ansys_json()

### ANSYS Import
- `import_simulation_geometry.py:519-540` - mesh_size application
- `import_simulation_geometry.py:146` - layer object collection

### Project Documentation
- `CLAUDE.md` - Project workflow instructions
- `MESHING_LAYER_OPTIONS.md` - Alternative approaches analysis

---

---

## UPDATE: Core KQCircuits Integration (2026-01-14)

### New Robust Solution Implemented

The mesh control functionality has been integrated into core KQCircuits, replacing the workaround approach. This provides a cleaner, more maintainable solution available to all simulations.

### What Changed

**1. New Dedicated Mesh Layers (default_layer_config.py:87-94)**

Added five dedicated mesh control layers to the standard layer set:
```python
"mesh_1": (27, 1),  # Mesh refinement region 1
"mesh_2": (28, 1),  # Mesh refinement region 2
"mesh_3": (29, 1),  # Mesh refinement region 3
"mesh_4": (31, 1),  # Mesh refinement region 4
"mesh_5": (32, 1),  # Mesh refinement region 5
```

These layers are now available in all faces (1t1, 2b1, etc.) just like airbridge layers.

**2. Automatic Processing (simulation.py:817-832)**

Modified `create_simulation_layers()` to automatically extract and export mesh layers:
```python
# Insert custom mesh control regions (vacuum, zero thickness, no partitioning)
for mesh_num in range(1, 6):
    mesh_layer_name = f"mesh_{mesh_num}"
    mesh_region = (
        self.simplified_region(self.region_from_layer(face_id, mesh_layer_name)) & face_box_region
    )
    if not mesh_region.is_empty():
        self.insert_layer(
            f"{face_id}_{mesh_layer_name}",
            mesh_region,
            z[face_id][0],  # At conductor surface
            z[face_id][0],  # Zero thickness
            material=None   # Non-model object, skips partitioning
        )
```

**Key Design Choices:**
- `material=None` - Makes layers non-model objects that skip partitioning in `produce_layers()`
- This eliminates the need to save/restore regions (unlike airbridge workaround)
- Original rectangular regions are preserved automatically
- No boundary conditions applied (no excitation/background properties)

**3. Validation and Warnings (simulation.py:1133-1179)**

Added `warn_mesh_layer_issues()` method to catch common problems:
- Mesh regions outside simulation box
- Mesh regions extending beyond box boundaries
- Unused mesh_size entries (typos/missing layers)
- Provides helpful error messages with available mesh layers

Automatically called during ANSYS export (ansys_export.py:190-193).

**4. Element Design Updates (resonator_spike.py:117-126)**

Changed from airbridge layers to dedicated mesh layers:
```python
# mesh_1: Fine mesh around spike regions
spikes_meshing_region = self._make_meshing_region()
self.cell.shapes(self.get_layer("mesh_1")).insert(spikes_meshing_region)

# mesh_2: Coarse mesh for inductor region
self.cell.shapes(self.get_layer("mesh_2")).insert(inductor_region)
```

**5. Simulation Script Simplification (spike_res_sim.py)**

Removed 70+ lines of custom simulation class code. Now just:
```python
SimClass = get_single_element_sim_class(ResonatorSpike)

export_parameters = {
    "mesh_size": {
        "1t1_mesh_1": 1,   # Fine mesh around spikes (1 µm)
        "1t1_mesh_2": 6,   # Coarse mesh for inductor (6 µm)
    },
}
```

### Benefits Over Previous Approach

| Aspect | Old (Airbridge Workaround) | New (Core Integration) |
|--------|---------------------------|------------------------|
| **Semantic Clarity** | Confusing reuse of airbridge layers | Dedicated mesh layers with clear purpose |
| **Code Complexity** | 70+ line custom simulation class | Standard simulation class, zero custom code |
| **Region Preservation** | Manual save/restore in produce_layers | Automatic via material=None |
| **Boundary Conditions** | Manual removal of excitation property | Never applied (non-model objects) |
| **Layer Management** | Manual detection/re-add of removed layers | Automatic handling |
| **Availability** | Per-simulation workaround | Available system-wide |
| **Maintainability** | Fragile override of internal method | Clean integration with layer pipeline |
| **Validation** | None | Automatic warnings for common issues |

### Verified Functionality

Tested with `spike_res_sim.py --no-gui`:
- ✅ Mesh layers automatically extracted from element geometry
- ✅ Exported to JSON with correct properties (material: N/A, z: 0.0, thickness: 0.0)
- ✅ Written to OAS file with simulation layer IDs
- ✅ Validation warnings correctly catch layers outside simulation box
- ✅ No custom simulation class needed

**Sample JSON Output:**
```json
"1t1_mesh_2": {
    "z": 0.0,
    "thickness": 0.0,
    "layer": 1000
}
```

### Usage for New Elements

```python
# In your element class (e.g., my_element.py)
class MyElement(Element):
    def build(self):
        # Create geometry
        fine_mesh_region = pya.Region(...)
        coarse_mesh_region = pya.Region(...)

        # Add to mesh layers
        self.cell.shapes(self.get_layer("mesh_1")).insert(fine_mesh_region)
        self.cell.shapes(self.get_layer("mesh_2")).insert(coarse_mesh_region)

# In your simulation script
SimClass = get_single_element_sim_class(MyElement)

export_parameters = {
    "mesh_size": {
        "1t1_mesh_1": 0.5,  # Very fine mesh
        "1t1_mesh_2": 5,    # Medium mesh
    },
}
```

### Files Modified

**Core KQCircuits:**
1. `kqcircuits/layer_config/default_layer_config.py` - Added mesh layer definitions
2. `kqcircuits/simulations/simulation.py` - Added mesh layer extraction and validation
3. `kqcircuits/simulations/export/ansys/ansys_export.py` - Added validation call

**Project Files:**
1. `elements/resonator_spike.py` - Changed airbridge→mesh layers
2. `scripts/simulations/spike_res_sim.py` - Removed custom class, updated mesh_size
3. `scripts/simulations/test_spike_output.py` - Updated to check mesh layers

### Migration Path for Existing Code

If you have existing elements using the airbridge workaround:

1. Change layer names in element:
   - `airbridge_pads` → `mesh_1`
   - `airbridge_flyover` → `mesh_2`

2. Update mesh_size in simulation scripts:
   - `"1t1_airbridge_pads"` → `"1t1_mesh_1"`
   - `"1t1_airbridge_flyover"` → `"1t1_mesh_2"`

3. Remove custom simulation class
   - Delete `ResonatorSpikeMeshingSim` or similar
   - Use standard `get_single_element_sim_class()`

4. Run and verify:
   - Check warnings for layers outside simulation box
   - Adjust simulation box if needed

---

## Key Technical Learnings

This section documents important insights gained during implementation that are valuable for future development.

### 1. KQCircuits Layer Pipeline Architecture

**Two-stage layer system:**
- **Element layers** (e.g., 155/1, 156/1) - Lithography layers where geometry is drawn during `build()`
- **Simulation layers** (1000+/0) - Export layers created by `create_simulation_layers()` via `region_from_layer()` extraction

**Critical insight**: Geometry exists in BOTH places unless explicitly cleared, causing duplication in exports. The implementation now clears element layers after extraction (simulation.py:833-835) to prevent this.

### 2. GDS vs OAS Export Behavior

| Format | Behavior | Layer Filtering | Result |
|--------|----------|-----------------|--------|
| **GDS** | Only exports layers with geometry | Uses `get_layers()` - filters by "layer" key in `self.layers` | Clean export, no duplicates |
| **OAS** | Exports all layer definitions (even empty) | Uses `save_layout()` without filtering | Shows empty element layer definitions alongside simulation layers |

**Practical impact**:
- GDS automatically avoids duplication (only shows simulation layers with geometry)
- OAS shows empty element layer definitions (155/1, 156/1) alongside simulation layers (1000/0, 1001/0)
- The empty layers are harmless (0 shapes) but appear in the layer list

### 3. The `material=None` Design Pattern

Using `material=None` in `insert_layer()` makes layers **non-model objects** that:
- Skip partitioning in `produce_layers()` (simulation.py:944: `can_modify()` returns False)
- Preserve original rectangular regions automatically (no clipping by gap intersection)
- Never receive boundary condition properties (`excitation`, `background`)
- Are subtracted from vacuum/dielectric only if explicitly specified in `subtract_keys`

**Why this matters**: This eliminates the need for the 70+ line save/restore/re-add hack from the airbridge workaround. The regions naturally preserve their shape throughout the export pipeline.

**Implementation location**: simulation.py:831
```python
material=None,  # Non-model object, skips partitioning in produce_layers()
```

### 4. Layer Name Export Limitations

**GDSII Format Limitation**: The GDSII specification (used by .gds files) does not support layer names - only layer numbers and datatypes. Layer names are a KLayout extension available in OAS format.

**Original bug**: The `get_layers()` method was creating LayerInfo objects without names:
```python
return [pya.LayerInfo(d["layer"], 0) for d in self.layers.values() if "layer" in d]
```

**Fix applied** (simulation.py:1497):
```python
return [get_simulation_layer_by_name(name) for name, d in self.layers.items() if "layer" in d]
```

**Result**:
- OAS files: Layer names visible (1t1_mesh_1, 1t1_mesh_2, etc.)
- GDS files: Only layer numbers visible (1000/0, 1001/0, etc.)
- Functionality: Both formats export geometry correctly for ANSYS

### 5. Validation System Architecture

The `warn_mesh_layer_issues()` method (simulation.py:1133-1179) provides three levels of validation:

1. **Geometry outside simulation box**
   - Detects mesh layers not exported (no "layer" key)
   - Reports the simulation box bounds for debugging

2. **Geometry extending beyond box**
   - Checks each shape's region against simulation box
   - Warns only once per layer (avoids spam)

3. **Unused mesh_size entries**
   - Pattern-matches mesh_size keys against exported layers
   - Lists available mesh layers when no match found
   - Helps catch typos and configuration errors

**Real-world value**: Immediately caught `mesh_1` (spike regions) being outside simulation box in initial testing, saving significant debugging time.

### 6. Element Layer Clearing Strategy

**Problem**: After `region_from_layer()` extracts geometry to create simulation layers, the original element layer still contains the geometry, causing duplication in exports.

**Solution** (simulation.py:833-835):
```python
# Clear the original element layer to avoid duplication in exports
element_layer_idx = self.get_layer(mesh_layer_name, face_id)
self.cell.shapes(element_layer_idx).clear()
```

**Result**:
- Element layers (155/1, 156/1): 0 shapes
- Simulation layers (1000/0, 1001/0): Contains geometry
- GDS export: Automatically excludes empty layers
- OAS export: Shows empty layer definitions (harmless) but no duplicate geometry

### 7. Why Core Integration Works

The key architectural insight: **By processing mesh layers in `create_simulation_layers()` with `material=None`, they flow through the normal simulation pipeline but skip the problematic partitioning step** that was causing issues in the airbridge approach.

**Design advantages**:
1. **Timing**: Extraction happens at the right point (after element build, before layer finalization)
2. **Non-interference**: `material=None` prevents physics simulation interference
3. **Preservation**: Regions automatically preserved without manual save/restore
4. **Boundary conditions**: Never applied (non-model objects don't get excitation properties)
5. **Availability**: Works for all simulations system-wide

**Code simplification**:
| Aspect | Airbridge Workaround | Core Integration |
|--------|---------------------|------------------|
| Lines of code | 70+ in custom class | 20 in core + 0 per simulation |
| Region handling | Manual save/restore in produce_layers | Automatic via material=None |
| Layer survival | Manual detection/re-add | Automatic |
| Boundary conditions | Manual property removal | Never applied |
| Maintenance burden | Per-simulation fragile override | Centralized robust integration |

### 8. Export Pipeline Flow

**Complete mesh layer journey**:

```
1. Element design (resonator_spike.py:121)
   └─> self.cell.shapes(self.get_layer("mesh_1")).insert(region)
       └─> Draws to element layer 1t1_mesh_1 (155/1)

2. Simulation initialization calls create_simulation_layers() (simulation.py:820-835)
   └─> region_from_layer(face_id, "mesh_1") extracts from layer 155/1
   └─> insert_layer("1t1_mesh_1", region, z, z, material=None)
       └─> Creates simulation layer 1t1_mesh_1 (1000/0) with geometry
   └─> self.cell.shapes(element_layer_idx).clear()
       └─> Clears element layer 155/1 (now has 0 shapes)

3. Export validation (ansys_export.py:190-193)
   └─> warn_mesh_layer_issues(mesh_size_dict)
       └─> Checks layers are within box
       └─> Checks mesh_size patterns match exported layers

4. GDS export (ansys_export.py:63)
   └─> save_layout(gds_file, layout, [cell], simulation.get_layers())
       └─> get_layers() returns only layers with "layer" key
       └─> Only exports simulation layers 1000/0, 1001/0 with geometry

5. OAS export (simulation_export.py:102)
   └─> save_layout(oas_file, layout, cells)
       └─> No layer filtering - exports all layer definitions
       └─> Shows empty element layers (155/1) + simulation layers (1000/0)

6. ANSYS import (import_simulation_geometry.py:519-540)
   └─> Reads GDS, finds layers by number (1000, 1001, etc.)
   └─> Matches to mesh_size patterns ("1t1_mesh_1", "1t1_mesh_2")
   └─> Applies mesh refinement to matched objects
```

### 9. Remaining Minor Issues

**Empty layer definitions in OAS**: Element layers (155/1, 156/1) appear in OAS layer list with 0 shapes.

**Why it happens**: `save_layout()` without layer filtering exports all layer definitions from the layout object, regardless of whether they contain geometry.

**Impact**: Visual clutter in layer list, but functionally harmless. KLayout doesn't display empty layers in the view by default.

**Why not fixed**: Would require filtering all exports or modifying core KLayout save behavior. The benefit doesn't justify the complexity since:
- No duplicate geometry (layers are empty)
- GDS export works correctly (automatically filters)
- ANSYS imports correctly (ignores empty layers)
- Visual impact minimal (empty layers don't show in default view)

---

## Contact & Maintenance

**Last Updated**: 2026-01-14 (Core Integration Complete)
**Python Version**: 3.12.8
**KQCircuits Version**: 4.9.7.post8+git.f5161578.dirty (with core mesh layer support)
**KLayout Version**: 0.30.5

**Status**: Production-ready. Core mesh layer support fully implemented and tested.

For questions or improvements, refer to this document and the referenced source code locations.
