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
import numpy as np

from kqcircuits.pya_resolver import pya
from kqcircuits.simulations.export.ansys.ansys_export import export_ansys
from kqcircuits.simulations.export.simulation_export import (
    cross_sweep_simulation,
    export_simulation_oas,
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
parser = argparse.ArgumentParser(description="Run Q3D ACRL simulations on spike resonator (extracts C, L, and R matrices)")
parser.add_argument("--no-gui", action="store_true",
                    help="Don't open KLayout to view results (default: open KLayout)")
args = parser.parse_args()

# Prepare output directory
dir_path = create_or_empty_tmp_directory(Path(__file__).stem + "_output")

# Create custom simulation class that adds a port to the center spike region
BaseSimClass = get_single_element_sim_class(ResonatorSpike)

class ResonatorSpikeACRLSim(BaseSimClass):
    """Custom simulation class for Q3D ACRL measurement through inductor.

    ACRL source/sink locations are stored in extra_json_data (not as ports) to avoid
    creating unwanted excitations. Coordinates are used by ANSYS import script to find
    nearest edges for ACRL source/sink assignment.
    """

    def build(self):
        # Build element geometry WITHOUT calling super().build() to avoid get_sim_ports
        # Instead, manually add the element and set ports
        simulation_cell = self.add_element(
            ResonatorSpike, **{**self.get_parameters(), "junction_type": "Sim", "fluxline_type": "none"}
        )

        element_trans = pya.DTrans(0, False, self.box.center())
        _, refp = self.insert_cell(simulation_cell, element_trans, rec_levels=None)
        self.refpoints = refp

        # Create ONE InternalPort to designate inductor/end_box as Net1 (SignalNet)
        # ACRL source/sink locations are stored in extra_json_data to avoid port-based excitations
        from kqcircuits.simulations.port import InternalPort

        if self.include_inductor:
            # Calculate positions from geometry (same as in resonator_spike.py)
            ground_gap_bottom = -(self.l_height + self.l_coupling_distance + self.feedline_spacing +
                                  self.b + self.a/2)
            end_box_bottom = self.end_box_spacing + ground_gap_bottom
            end_box_far_left = (self.l_coupling_length/2 - self.end_box_width -
                               (self.spike_height * 2 + self.spike_gap +
                                self.resist_thickness * (np.sin(np.radians(self.shadow_angle_1)) -
                                np.sin(np.radians(self.shadow_angle_2)))) - self.end_box_width)

            source_x = (self.l_coupling_length/2 - self.end_box_width +
                       self.l_coupling_length/2 + self.end_box_width) / 2
            source_y = end_box_bottom

            sink_x = end_box_far_left - 1.5 * self.l_grounding_distance
            sink_y = ground_gap_bottom

            # Transform coordinates from element-local to simulation box coordinates
            # by applying the element_trans transformation
            source_point_transformed = element_trans.trans(pya.DPoint(source_x, source_y))
            sink_point_transformed = element_trans.trans(pya.DPoint(sink_x, sink_y))

            # Create single port in middle of conductor to designate as Net1
            mid_x = (source_x + sink_x) / 2
            mid_y = (source_y + sink_y) / 2
            mid_point_transformed = element_trans.trans(pya.DPoint(mid_x, mid_y))
            self.ports = [InternalPort(number=1, signal_location=mid_point_transformed, ground_location=None)]

            # Store actual ACRL source/sink locations separately (in transformed coordinates)
            self.extra_json_data = {
                "acrl_port_locations": {
                    "source": [source_point_transformed.x, source_point_transformed.y, 0.0],
                    "sink": [sink_point_transformed.x, sink_point_transformed.y, 0.0]
                }
            }
        else:
            self.ports = []

SimClass = ResonatorSpikeACRLSim

# Simulation parameters for Q3D ACRL measurement
sim_parameters = {
    "name": "resonator_spike_acrl",
    "use_internal_ports": True,   # Use internal port on center spike region
    "use_ports": True,            # Enable port system
    "box": pya.DBox(pya.DPoint(0, -700), pya.DPoint(1000, 3000)),
    "shadow_angle_1": 0,
    "shadow_angle_2": 0,
    "spike_number": 50,
    "spike_height": 0.5,
    "spike_base_width": 0.25,
    "end_box_height": 50,
    "l_height": 1600,
    "spike_gap": 0.1,
    "face_stack": ["1t1"],

    # Enable inductor for ACRL inductance measurement through inductor
    "include_inductor": True,

    # Disable junction for Q3D simulations (not needed for capacitance/inductance)
    "junction_bool": False,

    # Disable mesh layers for ACRL (ANSYS bug deletes mesh geometry instead of keeping it)
    "enable_mesh_layers": False,
}

# Q3D ACRL export parameters
export_parameters = {
    "path": dir_path,
    "ansys_tool": "q3d",
    # Use new post-processing script that handles C, L, and R matrices
    "post_process": PostProcess("produce_matrix_tables.py"),
    "exit_after_run": True,
    "percent_error": 0.3,  # Reasonable accuracy (0.2-0.5 typical for production)
    "minimum_converged_passes": 2,
    "maximum_passes": 20,
    "use_floating_islands": True,  # Treat isolated spike system as floating net

    # NEW: Enable ACRL (AC Resistance and Inductance extraction)
    # Source/sink locations will be read from Net1_source and Net1_sink ports in geometry
    "solve_acrl": True,

    # Mesh refinement disabled for ACRL due to ANSYS bug
    # (Enable mesh_layers and uncomment this for non-ACRL simulations)
    # "mesh_size": {
    #     "1t1_mesh_2": 5,    # Mesh over inductor region for accurate inductance calculation
    # },
}

# Get layout
logging.basicConfig(level=logging.WARN, stream=sys.stdout)
layout = get_active_or_new_layout()

# Parameter sweeps
simulations = []

# Single test configuration to visualize ACRL port placement
simulations += cross_sweep_simulation(
    layout,
    SimClass,
    sim_parameters,
    {
        "spike_number": [50],  # Single test case for visualization
    },
)

# Additional parameter sweeps (commented out - uncomment as needed)

# Sweep spike gap to characterize impedance vs spacing
# simulations += cross_sweep_simulation(
#     layout,
#     SimClass,
#     sim_parameters,
#     {
#         "spike_gap": [0.05, 0.1, 0.15, 0.2, 0.25],
#         "spike_number": [100, 200],
#     },
# )

# Sweep spike height to characterize impedance vs finger length
# simulations += cross_sweep_simulation(
#     layout,
#     SimClass,
#     sim_parameters,
#     {
#         "spike_height": [0.25, 0.5, 1.0, 1.5],
#         "spike_number": [100, 200],
#     },
# )

# Export Ansys Q3D files with ACRL enabled
export_ansys(simulations, **export_parameters)

# Write oas file
oas_file = export_simulation_oas(simulations, dir_path)
print(f"\nExported Q3D ACRL simulation files to: {dir_path}")
print(f"OAS file: {oas_file}")
print(f"Number of simulations: {len(simulations)}")
print(f"\nACRL enabled: Will extract L-matrix, R-matrix, and C-matrix")
print(f"Expected output files:")
print(f"  - *_cmatrix_results.csv (capacitance matrix)")
print(f"  - *_lmatrix_results.csv (inductance matrix)")
print(f"  - *_rmatrix_results.csv (resistance matrix)")

# Optionally open in KLayout
if not args.no_gui:
    open_with_klayout_or_default_application(oas_file)
else:
    print("\nSkipping KLayout GUI (--no-gui flag set)")
