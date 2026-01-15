#!/usr/bin/env python
"""Test script to verify spike_res_sim.py output."""

import json
from pathlib import Path
from kqcircuits.pya_resolver import pya

# Paths
output_dir = Path(__file__).parent.parent.parent.parent.parent / "tmp" / "spike_res_sim_spike_length_output"
json_file = output_dir / "resonator_spike_0.125.json"
oas_file = output_dir / "simulation.oas"

print("=" * 80)
print("SPIKE RESONATOR SIMULATION OUTPUT TEST")
print("=" * 80)

# Check JSON
if json_file.exists():
    print(f"\n1. JSON FILE: {json_file}")
    with open(json_file) as f:
        data = json.load(f)

    print(f"\n  Simulation box: {data['box']}")
    box_p1_y = data['box']['p1']['y']
    box_p2_y = data['box']['p2']['y']
    print(f"  Y-range: {box_p1_y} to {box_p2_y}")

    print(f"\n  Mesh size settings:")
    for layer_name, size in data.get('mesh_size', {}).items():
        print(f"    {layer_name}: {size} µm")

    print(f"\n  Layers with 'layer' key (will be exported to GDS/ANSYS):")
    mesh_layers_found = []
    for name, info in data['layers'].items():
        if 'layer' in info:
            print(f"    {name}:")
            print(f"      material: {info.get('material', 'N/A')}")
            print(f"      z: {info.get('z')}")
            print(f"      thickness: {info.get('thickness')}")
            print(f"      layer: {info.get('layer')}")
            if 'mesh_' in name:
                mesh_layers_found.append(name)

    print(f"\n  Mesh control layers found: {mesh_layers_found if mesh_layers_found else 'NONE'}")
else:
    print(f"\nERROR: JSON file not found: {json_file}")

# Check OAS
if oas_file.exists():
    print(f"\n2. OAS FILE: {oas_file}")
    layout = pya.Layout()
    layout.read(str(oas_file))

    print(f"\n  Top cells: {[cell.name for cell in layout.top_cells()]}")

    cell = layout.top_cells()[0]
    print(f"\n  Checking cell '{cell.name}' for layers:")

    mesh_layers = []
    all_layers_list = []
    for layer_info in layout.layer_infos():
        layer_idx = layout.layer(layer_info)
        shapes = cell.shapes(layer_idx)
        all_layers_list.append(layer_info.name)
        if not shapes.is_empty():
            print(f"    {layer_info.name} ({layer_info.layer}/{layer_info.datatype}): {shapes.size()} shapes")
            if 'mesh_' in layer_info.name.lower():
                mesh_layers.append(layer_info.name)
                print(f"      *** MESH CONTROL LAYER FOUND ***")

    print(f"\n  All layer names in layout: {all_layers_list}")
    print(f"\n  Mesh control layers in OAS: {mesh_layers if mesh_layers else 'NONE'}")
else:
    print(f"\nERROR: OAS file not found: {oas_file}")

print("\n" + "=" * 80)
print("TEST COMPLETE")
print("=" * 80)
