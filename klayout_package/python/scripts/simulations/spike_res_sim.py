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
dir_path = create_or_empty_tmp_directory(Path(__file__).stem + "_spike_number_output")

# Mesh control regions (mesh_1, mesh_2, etc.) are now automatically processed by KQCircuits core
SimClass = get_single_element_sim_class(ResonatorSpike)

use_latin_sampling = False
# Simulation parameters, using multiface interdigital as starting point
sim_parameters = {
    #"base_metal_addition_layers": "sis_shadow", 
    "name": "resonator_spike",
    #"basis_order": -1, 
    "use_internal_ports": True,
    "use_ports": True,
    "box": pya.DBox(pya.DPoint(0, -700), pya.DPoint(1000, 3000)),  # Extended to include inductor region
    "port_size": 200,
    "shadow_angle_1": 0, 
    "shadow_angle_2": 0, 
    "spike_number": 50, 
    "spike_height": 0.5,
    "spike_base_width": 0.25,
    "end_box_buffer": 100,
    "l_height": 1600,
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
    'max_delta_f': 1, #percent
    "minimum_converged_passes": 3,
    "maximum_passes": 30,
    #"mesh_size": {"1t1_gap": 15,},
    # Custom mesh refinement using dedicated mesh control layers
    # mesh_1 and mesh_2 are automatically extracted from ResonatorSpike geometry and exported to ANSYS
    # These layers are vacuum, zero-thickness sheets that only affect mesh refinement
    # To verify export is working:
    #   1. Check the generated .oas file in KLayout - look for mesh_1 and mesh_2 layers
    #   2. Check the .json file for "1t1_mesh_1" and "1t1_mesh_2" entries with "layer" key
    #   3. In ANSYS, check if 1t1_mesh_* objects exist in 3D Modeler
    #   4. Verify mesh refinement is applied in the solution setup
    "mesh_size": {"1t1_mesh_1": 1,    # Fine mesh around spike regions (1 µm)
                  "1t1_mesh_2": 6,   # Coarse mesh for inductor region (6 µm)
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
# Multi face finger (interdigital) capacitor sweeps
simulations += cross_sweep_simulation(
    layout,
    SimClass,
    sim_parameters,
    {
        # "l_height": inductor_heights,
        #"l_width": inductor_widths,
        #"spike_gap": spike_spacing,
        "spike_number": [50, 100, 200, 300, 400, 500], 
        #"l_coupling_distance": [10, 16, 20, 30, 50, 100], 
        #"spike_height": [0.125, 0.25, 0.5, 1, 2]
    },
)

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
