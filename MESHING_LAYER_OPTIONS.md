# Custom Meshing Layer Options for ANSYS Export

This document outlines options for creating custom geometry layers that control ANSYS mesh refinement in specific regions, without requiring the entire gap or conductor to be meshed finely.

## Problem Summary

KQCircuits can export mesh control layers to ANSYS, but by default only processes certain layers (like `1t1_gap`). We need to create arbitrary shaped regions on custom layers that get exported to ANSYS for fine-grained mesh control.

## Root Cause Analysis

The ANSYS export pipeline requires layers to:
1. Be created during `create_simulation_layers()` via `insert_layer()`
2. Pass through `produce_layers()` to receive a "layer" key
3. Have geometry within the simulation box boundary
4. Be written to the GDS file (only happens with "layer" key)
5. Be imported by ANSYS Python script as 3D objects
6. Match patterns in the `mesh_size` parameter

Layers added manually after initialization skip steps 2-4 and never reach ANSYS.

## Option 1: Modify Single Element Simulation Class (RECOMMENDED for Production)

**Description:** Create a custom simulation class that properly handles meshing layers during the normal layer creation pipeline.

**Pros:**
- Clean, follows KQCircuits patterns
- Reusable for future designs
- Proper integration with export pipeline
- Full control over multiple custom meshing layers

**Cons:**
- Requires understanding simulation class structure
- More code to write upfront

**Implementation:**
1. Subclass the result of `get_single_element_sim_class(ResonatorSpike)`
2. Override `create_simulation_layers()` method
3. Add custom meshing layers using `insert_layer()` before calling `super().create_simulation_layers()`
4. Ensure layers are within simulation box bounds
5. Reference by name in `mesh_size` parameter

**Example code structure:**
```python
class ResonatorSpikeSimWithMeshing(get_single_element_sim_class(ResonatorSpike)):
    def create_simulation_layers(self):
        # Extract custom meshing regions from element geometry
        for face_id in self.face_ids:
            meshing_region = self.simplified_region(
                self.region_from_layer(face_id, "custom_mesh_layer")
            )
            if not meshing_region.is_empty():
                self.insert_layer(
                    f"{face_id}_custom_mesh",
                    meshing_region,
                    z_bottom,
                    z_top,
                    material="vacuum"
                )

        # Continue with normal layer creation
        super().create_simulation_layers()
```

---

## Option 2: Use Existing airbridge_pads Layer (QUICK FIX - CURRENT IMPLEMENTATION)

**Description:** Leverage the fact that KQCircuits already processes "airbridge_pads" automatically in `create_simulation_layers()` (simulation.py:812-815).

**Pros:**
- No code changes to simulation system
- Works immediately if geometry is within simulation box
- Uses existing, tested pipeline
- Zero risk to core KQCircuits code

**Cons:**
- Semantically tied to "airbridge_pads" naming
- Must ensure geometry is within simulation box bounds
- Limited to single meshing region type per face

**Implementation:**
1. Create geometry on "airbridge_pads" layer in your element (e.g., `resonator_spike.py`)
2. Ensure geometry is within simulation box: `pya.DBox(pya.DPoint(0, 0), pya.DPoint(1000, 2000))`
3. Do NOT manually call `insert_layer()` in simulation script
4. Use `"1t1_airbridge_pads": mesh_size_value` in export parameters
5. KQCircuits automatically extracts and exports this layer

**Current status:** ✓ Implemented

---

## Option 3: Add Vacuum Meshing Layers to Core Simulation

**Description:** Modify `Simulation.create_simulation_layers()` to support arbitrary vacuum meshing regions as a first-class feature.

**Pros:**
- Makes this capability available system-wide
- Proper design pattern for KQCircuits
- Could contribute back to upstream KQCircuits project
- Future-proof for all users

**Cons:**
- Requires modifying core KQCircuits code
- Need to understand and follow KQCircuits layer naming conventions
- More extensive testing required
- Must maintain compatibility with existing code

**Implementation:**
1. Modify `klayout_package/python/kqcircuits/simulations/simulation.py`
2. Add support for layers like "mesh_fine", "mesh_coarse" in addition to existing layers
3. Process these layers similar to "airbridge_pads" in `create_simulation_layers()`
4. Update documentation
5. Submit PR to KQCircuits if desired

**Code location:** `simulation.py:812-815` (where airbridge_pads is currently processed)

---

## Option 4: Create Meshing-Only Layers with Special Parameter

**Description:** Add a simulation parameter to define custom meshing regions that get inserted at the right time in the pipeline.

**Pros:**
- Flexible per-simulation control
- No element-level changes needed
- Can define arbitrary shapes programmatically in simulation script
- Multiple named meshing regions possible

**Cons:**
- Requires modifying simulation base class
- Less intuitive than using element geometry
- Region definitions separated from visual element design

**Implementation:**
1. Add parameter `mesh_regions` to simulation initialization:
   ```python
   sim_parameters = {
       "mesh_regions": {
           "fine_mesh": {"z0": 0, "z1": 1, "shapes": [...], "material": "vacuum"},
           "coarse_mesh": {"z0": 0, "z1": 1, "shapes": [...], "material": "vacuum"}
       }
   }
   ```
2. Process in `create_simulation_layers()` to insert vacuum layers
3. Reference by name in `mesh_size`: `{"1t1_fine_mesh": 0.2}`

---

## Recommended Workflow

### Immediate Development (Option 2 - Current):
1. Use "airbridge_pads" layer for meshing control geometry
2. Verify exports work correctly
3. Iterate on designs quickly

### Long-term Production (Option 1):
1. Once the approach is validated, create custom simulation class
2. Add support for multiple meshing region types
3. Use descriptive names like "mesh_fine_spikes", "mesh_coarse_feedline"

### Contributing Back (Option 3):
1. If this becomes a common pattern, propose enhancement to KQCircuits
2. Add generic meshing layer support to core simulation class

---

## Key Technical Details

### Layer Export Pipeline:
```
Element geometry on KLayout layer
    ↓
create_simulation_layers() extracts via region_from_layer()
    ↓
insert_layer() stores in self.layers dict
    ↓
produce_layers() adds "layer" key if within simulation box
    ↓
export_ansys_json() writes layers with "layer" key to GDS
    ↓
import_simulation_geometry.py imports GDS into ANSYS
    ↓
mesh_size parameter applies refinement to matching layer patterns
```

### Critical Requirements:
- Geometry must be within simulation box bounds
- Layer must have "layer" key (only added by produce_layers())
- Layer must be in GDS file (only written if "layer" key exists)
- Layer name must match mesh_size pattern

### Mesh Size Pattern Matching:
Uses glob-style patterns via `match_layer()`:
- `"1t1_airbridge_pads"` → matches exactly
- `"1t1_*"` → matches all 1t1 face layers
- `"*pads"` → matches layers ending in "pads"

---

## Date: 2026-01-14
## Status: Option 2 implemented and ready for testing
