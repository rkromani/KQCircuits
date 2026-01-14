# This code is part of KQCircuits
# Copyright (C) 2021 IQM Finland Oy
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public
# License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied
# warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with this program. If not, see
# https://www.gnu.org/licenses/gpl-3.0.html.
#
# The software distribution should follow IQM trademark policy for open-source software
# (meetiqm.com/iqm-open-source-trademark-policy). IQM welcomes contributions to the code.
# Please see our contribution agreements for individuals (meetiqm.com/iqm-individual-contributor-license-agreement)
# and organizations (meetiqm.com/iqm-organization-contributor-license-agreement).


import argparse
import logging
import sys
from pathlib import Path

from kqcircuits.pya_resolver import pya
from kqcircuits.simulations.export.ansys.ansys_export import export_ansys
from kqcircuits.simulations.export.simulation_export import (
    cross_sweep_simulation,
    export_simulation_oas,
    latin_hypercube_sampling,
    combine_sweep_simulation,
)

from kqcircuits.elements.resonator_spike import ResonatorSpike
from kqcircuits.simulations.post_process import PostProcess
from kqcircuits.simulations.single_element_simulation import get_single_element_sim_class
from kqcircuits.util.export_helper import (
    create_or_empty_tmp_directory,
    get_active_or_new_layout,
    open_with_klayout_or_default_application,
)

# Parse command-line arguments
parser = argparse.ArgumentParser(description="Run spike resonator simulations")
parser.add_argument("--no-gui", action="store_true",
                    help="Don't open KLayout to view results (default: open KLayout)")
args = parser.parse_args()

# Prepare output directory
dir_path = create_or_empty_tmp_directory(Path(__file__).stem + "_spike_length_output")

# Create custom simulation class that fixes airbridge_pads layer for meshing control
BaseSimClass = get_single_element_sim_class(ResonatorSpike)

class ResonatorSpikeMeshingSim(BaseSimClass):
    """Custom simulation class that sets airbridge layers as infinitely thin vacuum sheets for mesh control."""

    def produce_layers(self, parts):
        """Override to modify airbridge layers for mesh control and preserve their original regions."""
        # Save original regions for airbridge layers before produce_layers partitions them
        # This prevents the rectangular meshing regions from being clipped by gap intersections
        original_regions = {}

        for face_id in self.face_ids:
            # Get the conductor surface z-coordinate for this face
            conductor_z = 0.0  # For 1t1 face, conductor is at z=0

            # Fix airbridge_pads layer and save original region
            pads_layer_name = f"{face_id}_airbridge_pads"
            if pads_layer_name in self.layers:
                layer = self.layers[pads_layer_name]
                original_regions[pads_layer_name] = layer["region"].dup()  # Save original
                layer["material"] = "vacuum"
                layer["bottom"] = conductor_z
                layer["top"] = conductor_z  # Infinitely thin (thickness = 0)

            # Fix airbridge_flyover layer and save original region
            flyover_layer_name = f"{face_id}_airbridge_flyover"
            if flyover_layer_name in self.layers:
                layer = self.layers[flyover_layer_name]
                original_regions[flyover_layer_name] = layer["region"].dup()  # Save original
                layer["material"] = "vacuum"
                layer["bottom"] = conductor_z
                layer["top"] = conductor_z  # Infinitely thin (thickness = 0)

        # Call parent to finalize layers (this may partition the regions)
        super().produce_layers(parts)

        # Restore original regions for airbridge layers after partitioning
        # This ensures the full rectangular regions are exported for mesh control
        from kqcircuits.simulations.simulation import get_simulation_layer_by_name
        for layer_name, original_region in original_regions.items():
            if layer_name in self.layers:
                # Layer survived produce_layers - restore its original region
                sim_layer = get_simulation_layer_by_name(layer_name)
                shapes = self.cell.shapes(self.layout.layer(sim_layer))
                shapes.clear()
                shapes.insert(original_region)
            else:
                # Layer was removed by produce_layers (region became empty after partitioning)
                # Re-add it manually for mesh control
                sim_layer = get_simulation_layer_by_name(layer_name)
                shapes = self.cell.shapes(self.layout.layer(sim_layer))
                shapes.insert(original_region)
                # Re-add to self.layers with proper format
                self.layers[layer_name] = {
                    "z": 0.0,
                    "thickness": 0.0,
                    "layer": sim_layer.layer,
                    "material": "vacuum",
                }

SimClass = ResonatorSpikeMeshingSim

use_latin_sampling = False
# Simulation parameters, using multiface interdigital as starting point
sim_parameters = {
    #"base_metal_addition_layers": "sis_shadow", 
    "name": "resonator_spike",
    #"basis_order": -1, 
    "use_internal_ports": True,
    "use_ports": True,
    "box": pya.DBox(pya.DPoint(0, -700), pya.DPoint(1000, 2000)),  # Extended to include inductor region
    "port_size": 200,
    "shadow_angle_1": 0, 
    "shadow_angle_2": 0, 
    "spike_number": 50, 
    #"spike_height": 0.5,
    "spike_base_width": 0.25,
    "l_height": 600,
    "spike_gap": 0.1,
    "face_stack": ["1t1"],
}
# Parameters that differ from sim_parameters for gap type
gap_parameters = {
}
export_parameters = {
    "path": dir_path,
    "ansys_tool": "eigenmode",
    'min_frequency': 0.5,
    'n_modes': 1,
    #"post_process": PostProcess("produce_cmatrix_table.py"),
    "exit_after_run": True,
    #"percent_error": 3,
    'max_delta_f': 5,
    "minimum_converged_passes": 3,
    "maximum_passes": 30,
    #"mesh_size": {"1t1_gap": 15,},
    # Custom mesh refinement using airbridge_pads and airbridge_flyover layers
    # These layers are automatically extracted from ResonatorSpike geometry and exported to ANSYS
    # To verify export is working:
    #   1. Check the generated .oas file in KLayout - look for airbridge_pads layer
    #   2. Check the .json file for "1t1_airbridge_pads" entry with "layer" key
    #   3. In ANSYS, check if 1t1_airbridge_pads objects exist in 3D Modeler
    #   4. Verify mesh refinement is applied in the solution setup
    "mesh_size": {"1t1_airbridge_pads": 1,    # Fine mesh around spike regions (0.2 µm)
                  "1t1_airbridge_flyover": 6,   # Coarse mesh for inductor region (3 µm)
                  },
}

# Sweep ranges
#inductor_heights = [300, 400, 500, 600]
#inductor_widths = [1, 2, 3, 4, 5]
#spike_spacing = [0.02, 0.05, 0.1, 0.15, 0.2, 0.25]

# Get layout
logging.basicConfig(level=logging.WARN, stream=sys.stdout)
layout = get_active_or_new_layout()

# Cross sweep number of fingers and finger length
simulations = []
if use_latin_sampling:
    # Multi face finger (interdigital) capacitor sweeps
    keys = ["chip_distance", "finger_number", "finger_length"]
    l_bounds = [4, 2, 0]
    u_bounds = [22, 8, 100]
    samples = latin_hypercube_sampling(l_bounds, u_bounds, n=100, integers=True, add_edges=True).tolist()
    simulations += combine_sweep_simulation(layout, SimClass, sim_parameters, keys, samples)
else:
    # Multi face finger (interdigital) capacitor sweeps
    simulations += cross_sweep_simulation(
        layout,
        SimClass,
        sim_parameters,
        {
            # "l_height": inductor_heights,
            #"l_width": inductor_widths,
            #"spike_gap": spike_spacing,
            #"spike_number": [50, 100, 200, 300, 400, 500], 
            #"l_coupling_distance": [10, 16, 20, 30, 50, 100], 
            "spike_height": [0.125, 0.25, 0.5, 1, 2]
        },
    )

# Note: airbridge_pads layer from ResonatorSpike is automatically processed by KQCircuits
# during create_simulation_layers() and exported to ANSYS for mesh refinement.
# See mesh_size parameter in export_parameters for mesh control.

# Multi face gap capacitor sweeps
#simulations += cross_sweep_simulation(
#    layout,
#    SimClass,
#    {
#        **sim_parameters,
#        "name": sim_parameters["name"] + "_gap",
#        **gap_parameters,
#    },
#    {
#        "chip_distance": chip_distances,
#        "finger_gap_end": gap_lengths,
#    },
#)


# Single face finger (interdigital) capacitor sweeps
"""simulations += cross_sweep_simulation(
    layout,
    SimClass,
    {
        **sim_parameters,
        "name": sim_parameters["name"] + "_singleface",
        "face_stack": ["1t1"],
    },
    {
        "finger_number": finger_numbers,
        "finger_length": finger_lengths,
    },
)"""

# Single face gap capacitor sweeps
"""simulations += cross_sweep_simulation(
    layout,
    SimClass,
    {
        **sim_parameters,
        "name": sim_parameters["name"] + "_singleface_gap",
        "face_stack": ["1t1"],
        **gap_parameters,
    },
    {
        "finger_gap_end": gap_lengths,
    },
)
"""
# Export Ansys files
export_ansys(simulations, **export_parameters)

# Write oas file
oas_file = export_simulation_oas(simulations, dir_path)
print(f"Exported simulation files to: {dir_path}")
print(f"OAS file: {oas_file}")

# Optionally open in KLayout
if not args.no_gui:
    open_with_klayout_or_default_application(oas_file)
else:
    print("Skipping KLayout GUI (--no-gui flag set)")
