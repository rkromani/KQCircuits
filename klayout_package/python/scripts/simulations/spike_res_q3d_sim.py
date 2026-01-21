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
)

# Import simulation database manager
sys.path.insert(0, str(Path(__file__).parents[4]))  # Add repo root to path
from simulations_database.tools.simulation_db import SimulationDB

from kqcircuits.elements.resonator_spike import ResonatorSpike
from kqcircuits.simulations.post_process import PostProcess
from kqcircuits.simulations.single_element_simulation import get_single_element_sim_class
from kqcircuits.util.export_helper import (
    create_or_empty_tmp_directory,
    get_active_or_new_layout,
    open_with_klayout_or_default_application,
)

# Parse command-line arguments
parser = argparse.ArgumentParser(description="Run Q3D capacitance simulations on spike resonator")
parser.add_argument("--no-gui", action="store_true",
                    help="Don't open KLayout to view results (default: open KLayout)")
args = parser.parse_args()

# Prepare output directory
dir_path = create_or_empty_tmp_directory(Path(__file__).stem + "_output")

# Create custom simulation class that adds a port to the center spike region
BaseSimClass = get_single_element_sim_class(ResonatorSpike)

class ResonatorSpikeQ3dSim(BaseSimClass):
    """Custom simulation class for Q3D capacitance measurement of spike regions.

    Adds an internal port to the center spike region to make it a signal net.
    The outer spike regions (physically separated) will be ground.
    Q3D measures capacitance between center (SignalNet) and outer (GroundNet).
    """

    def build(self):
        # Call parent build to create geometry
        super().build()

        # Clear default feedline ports
        self.ports = []

        # Add internal port to CENTER spike region (makes it a signal net)
        # Port placed in the center end box region
        # Calculate position from parameters (center box is at l_coupling_length/2)
        center_x = 0  # Centered horizontally

        # Calculate y position: end_box_bottom + half height
        # end_box_bottom = end_box_spacing + ground_gap_bottom
        ground_gap_bottom = -(self.l_height + self.l_coupling_distance + self.feedline_spacing +
                              self.b + self.a/2)
        end_box_height = self.end_box_height
        end_box_bottom = self.end_box_spacing + ground_gap_bottom
        center_y = end_box_bottom + end_box_height / 2

        from kqcircuits.simulations.port import InternalPort
        self.ports.append(
            InternalPort(
                number=1,
                signal_location=pya.DPoint(center_x, center_y),
                ground_location=None,
            )
        )

SimClass = ResonatorSpikeQ3dSim

# Simulation parameters for Q3D capacitance measurement
sim_parameters = {
    "name": "resonator_spike_q3d",
    "use_internal_ports": True,   # Use internal port on center spike region
    "use_ports": True,            # Enable port system
    "box": pya.DBox(pya.DPoint(0, -700), pya.DPoint(1000, 3000)),
    "shadow_angle_1": 0,
    "shadow_angle_2": 0,
    #"spike_number": 1,
    "spike_height": 2,
    "spike_base_width": 2,
    "t_cut_number": 0,
    "end_box_height": 420, 
    "l_height": 1600,
    "spike_gap": 0.5,
    "face_stack": ["1t1"],

    # CRITICAL: Disable inductor to isolate spike system from ground
    # This allows measurement of spike capacitance without ground connection
    "include_inductor": False,

    # Disable junction for Q3D simulations (not needed for capacitance)
    "junction_bool": False,
}

# Q3D export parameters
export_parameters = {
    "path": dir_path,
    "ansys_tool": "q3d",
    "post_process": PostProcess("produce_cmatrix_table.py"),
    "exit_after_run": False,
    "percent_error": 0.3,  # Reasonable accuracy (0.2-0.5 typical for production)
    "minimum_converged_passes": 2,
    "maximum_passes": 20,
    "use_floating_islands": True,  # Treat isolated spike system as floating net
    # Custom mesh refinement for accurate results in spike regions
    "mesh_size": {
        "1t1_mesh_1": 0.25,    # Fine mesh around spike regions (0.25 µm)
        "1t1_mesh_3": 3,    # Fine mesh around cap regions (3 µm)
    },
}

# Get layout
logging.basicConfig(level=logging.WARN, stream=sys.stdout)
layout = get_active_or_new_layout()

# Parameter sweeps
simulations = []

# Sweep spike number to characterize capacitance vs number of fingers
simulations += cross_sweep_simulation(
    layout,
    SimClass,
    sim_parameters,
    {
        "spike_number": [0, 5, 10, 15, 20],
        #"spike_gap": [0.025, 0.05, 0.1, 0.15, 0.2,],
        #"spike_height": [2.0, 4.0, 10.0, 15.0, 20.0],
        #"spike_base_width": [0.125, 0.25, 0.5, 1.0, 2.0],
    },
)

# Additional parameter sweeps (commented out - uncomment as needed)

# Sweep spike gap to characterize capacitance vs spacing
# simulations += cross_sweep_simulation(
#     layout,
#     SimClass,
#     sim_parameters,
#     {
#         "spike_gap": [0.05, 0.1, 0.15, 0.2, 0.25],
#         "spike_number": [100, 200, 300],
#     },
# )

# Sweep spike height to characterize capacitance vs finger length
# simulations += cross_sweep_simulation(
#     layout,
#     SimClass,
#     sim_parameters,
#     {
#         "spike_height": [0.25, 0.5, 1.0, 1.5, 2.0],
#         "spike_number": [100, 200, 300],
#     },
# )

# Register simulations with database
db = SimulationDB()
db_folders = db.register_simulations(
    simulations=simulations,
    design_name='spike_resonator',
    sim_parameters=sim_parameters,
    export_parameters=export_parameters,
    output_folder=dir_path
)

# Export Ansys Q3D files
export_ansys(simulations, **export_parameters)

# Write oas file
oas_file = export_simulation_oas(simulations, dir_path)
print(f"Exported Q3D simulation files to: {dir_path}")
print(f"OAS file: {oas_file}")
print(f"Number of simulations: {len(simulations)}")

# Print next steps for database workflow
print(f"\n{'='*60}")
print(f"→ Next step:")
print(f"  Run ANSYS simulations: {dir_path}/simulation.bat")
print(f"  (Results will be automatically saved to database)")
print(f"{'='*60}\n")

# Optionally open in KLayout
if not args.no_gui:
    open_with_klayout_or_default_application(oas_file)
else:
    print("Skipping KLayout GUI (--no-gui flag set)")
