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

from kqcircuits.elements.double_res import DoubleRes
from kqcircuits.simulations.post_process import PostProcess
from kqcircuits.simulations.single_element_simulation import get_single_element_sim_class
from kqcircuits.util.export_helper import (
    create_or_empty_tmp_directory,
    get_active_or_new_layout,
    open_with_klayout_or_default_application,
)

# Parse command-line arguments
parser = argparse.ArgumentParser(description="Run Q3D capacitance simulations on double resonator")
parser.add_argument("--no-gui", action="store_true",
                    help="Don't open KLayout to view results (default: open KLayout)")
parser.add_argument("--sweep-override", type=str, default=None,
                    help="Override sweep parameters as JSON (e.g., '{\"cap_wide_gap\": [1, 2, 3]}')")
args = parser.parse_args()

# Prepare output directory
dir_path = create_or_empty_tmp_directory(Path(__file__).stem + "_output")

# Create custom simulation class that adds a port to the capacitor center plate
BaseSimClass = get_single_element_sim_class(DoubleRes)

class DoubleResQ3dSim(BaseSimClass):
    """Custom simulation class for Q3D capacitance measurement of double resonator.

    Adds internal ports to define signal nets for:
    - Left capacitor plate
    - Right capacitor plate
    - Feedline center conductor
    The center plate and ground planes will be ground nets.
    """

    def build(self):
        # Call parent build to create geometry
        super().build()

        # Clear default feedline ports
        self.ports = []

        # Calculate capacitor geometry
        ground_gap_bottom = -(self.a/2 + self.b + self.feedline_coupling_ground_spacing) - self.ground_cutout_height
        cap_bottom = ground_gap_bottom + self.l_ground_sep - self.l_width/2
        cap_center_y = cap_bottom + self.cap_wide_height/2

        # Calculate capacitor region dimensions
        cap_region_total_width = self.cap_inner_width + 2 * self.cap_outer_width + 2 * self.cap_wide_gap

        from kqcircuits.simulations.port import InternalPort

        # Port 1: Left capacitor plate
        left_cap_x = -cap_region_total_width/2 + self.cap_outer_width/2
        self.ports.append(
            InternalPort(
                number=1,
                signal_location=pya.DPoint(left_cap_x, cap_center_y),
                ground_location=None,
                net_name="left_capacitor",
            )
        )

        # Port 2: Right capacitor plate
        right_cap_x = cap_region_total_width/2 - self.cap_outer_width/2
        self.ports.append(
            InternalPort(
                number=2,
                signal_location=pya.DPoint(right_cap_x, cap_center_y),
                ground_location=None,
                net_name="right_capacitor",
            )
        )

        # Port 3: Feedline center conductor
        self.ports.append(
            InternalPort(
                number=3,
                signal_location=pya.DPoint(0, 0),
                ground_location=None,
                net_name="feedline",
            )
        )

SimClass = DoubleResQ3dSim

# Simulation parameters for Q3D capacitance measurement
sim_parameters = {
    "name": "double_res_q3d",
    "use_internal_ports": True,   # Use internal ports to define signal nets
    "use_ports": True,            # Enable port system
    "box": pya.DBox(pya.DPoint(-1200, -2000), pya.DPoint(1200, 100)),
    "face_stack": ["1t1"],

    # CRITICAL: Disable inductor to isolate capacitor from ground
    # This allows measurement of capacitor capacitance without inductor connection
    "include_inductor": False,

    # Enable mesh layers for accurate capacitance calculation
    "enable_mesh_layers": True,

    # Custom net names for Q3D results and plots
    "extra_json_data": {
        "net_names": {
            1: "left_capacitor",
            2: "right_capacitor",
            3: "feedline",
        }
    },
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
    "use_floating_islands": False,  # Explicitly define signal nets via internal ports
    # Custom mesh refinement for accurate results in capacitor gaps
    "mesh_size": {
        "1t1_mesh_1": 1,    # Fine mesh in capacitor gaps (1 µm)
    },
}

# Get layout
logging.basicConfig(level=logging.WARN, stream=sys.stdout)
layout = get_active_or_new_layout()

# Parameter sweeps
simulations = []

# Define base sweep parameters (can be overridden via --sweep-override)
import json
sweep_params = {
    "cap_wide_gap": [2, 3, 4],          # Gap spacing (dominant)
    "cap_wide_height": [75, 100, 125, 150, 200, 250],  # Overlap area
    #"cap_inner_width": [10, 15, 20, 25, 30],   # Plate width
    #"cap_outer_width": [10, 15, 20, 25, 30],   # Plate width
}

# Apply sweep overrides if provided
if args.sweep_override:
    try:
        sweep_overrides = json.loads(args.sweep_override)
        sweep_params.update(sweep_overrides)
        print(f"Applied sweep overrides: {sweep_overrides}")
    except json.JSONDecodeError as e:
        print(f"Warning: Could not parse sweep overrides: {e}")

# Sweep capacitor parameters to characterize capacitance
simulations += cross_sweep_simulation(
    layout,
    SimClass,
    sim_parameters,
    sweep_params,
)

# Register simulations with database
db = SimulationDB()
db_folders = db.register_simulations(
    simulations=simulations,
    design_name='double_resonator',
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
print(f"Next step:")
print(f"  Run ANSYS simulations: {dir_path}\\simulation.bat")
print(f"  (Results will be automatically saved to database)")
print(f"{'='*60}\n")

# Optionally open in KLayout
if not args.no_gui:
    open_with_klayout_or_default_application(oas_file)
else:
    print("Skipping KLayout GUI (--no-gui flag set)")
