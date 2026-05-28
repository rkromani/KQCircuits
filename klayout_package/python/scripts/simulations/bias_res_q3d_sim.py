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

from kqcircuits.elements.bias_resonator import BiasResonator
from kqcircuits.simulations.post_process import PostProcess
from kqcircuits.simulations.single_element_simulation import get_single_element_sim_class
from kqcircuits.util.export_helper import (
    create_or_empty_tmp_directory,
    get_active_or_new_layout,
    open_with_klayout_or_default_application,
)

# Parse command-line arguments
parser = argparse.ArgumentParser(description="Run Q3D capacitance simulations on bias resonator")
parser.add_argument("--no-gui", action="store_true",
                    help="Don't open KLayout to view results (default: open KLayout)")
parser.add_argument("--sweep-override", type=str, default=None,
                    help="Override sweep parameters as JSON (e.g., '{\"cap_center_width\": [100, 200, 300]}')")
args = parser.parse_args()

# Prepare output directory
dir_path = create_or_empty_tmp_directory(Path(__file__).stem + "_output")

# Create custom simulation class that adds a port to the capacitor paddle region
BaseSimClass = get_single_element_sim_class(BiasResonator)

class BiasResQ3dSim(BaseSimClass):
    """Custom simulation class for Q3D capacitance measurement of capacitor paddle.

    Adds internal ports:
    - Port 1: Feedline center conductor (signal net 2 - isolated by cutout)
    - Port 2: Capacitor paddle center (signal net 1 - isolated by include_inductor=False)
    Q3D measures capacitance between capacitor paddle and ground plane.
    """

    def build(self):
        # Call parent build to create geometry
        super().build()

        # Clear default feedline ports (we'll recreate them as internal ports)
        self.ports = []

        from kqcircuits.simulations.port import InternalPort

        # Port 1: Feedline center conductor (signal net 2 - isolated by cutout)
        feedline_y = 0  # Feedline is centered at y=0
        feedline_x = 0  # Place port in the middle of feedline
        self.ports.append(
            InternalPort(
                number=1,
                signal_location=pya.DPoint(feedline_x, feedline_y),
                ground_location=None,
            )
        )

        # Port 2: Capacitor paddle center (signal net 1 - isolated by include_inductor=False)
        # Calculate position based on BiasResonator geometry formulas
        import numpy as np

        # Recalculate geometry (from BiasResonator.build())
        l_height = 0.5 * (self.l_length - self.l_coupling_length + 6*self.l_radius*(np.pi/2 - 2) +
                         self.cap_inside_ground_distance - 2 * (self.l_coupling_distance - self.l_junction_distance))

        cap_x = self.l_coupling_length/2
        ground_gap_top = -(self.b + self.a/2 + self.feedline_spacing)
        ground_gap_bottom = ground_gap_top - l_height - self.l_coupling_distance - self.l_width

        # Center of capacitor paddle
        center_x = cap_x
        center_y = ground_gap_bottom - self.cap_inside_ground_distance - self.cap_center_length/2

        self.ports.append(
            InternalPort(
                number=2,
                signal_location=pya.DPoint(center_x, center_y),
                ground_location=None,
            )
        )

        # Ground net will be automatically assigned to the ground plane (all other metal)

SimClass = BiasResQ3dSim

# Simulation parameters for Q3D capacitance measurement
sim_parameters = {
    "name": "bias_resonator_q3d",
    "use_internal_ports": True,   # Use internal port on capacitor paddle
    "use_ports": True,            # Enable port system
    "box": pya.DBox(pya.DPoint(-1000, -5600), pya.DPoint(2000, 500)),
    "face_stack": ["1t1"],

    # CRITICAL: Disable inductor to isolate capacitor from ground
    # This allows measurement of capacitor capacitance without ground connection
    "include_inductor": False,
    "include_capacitor": True,
    "enable_mesh_layers": True,  # Enable mesh layers for capacitor refinement
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
    "use_floating_islands": True,  # Treat isolated capacitor system as floating net
    # Custom mesh refinement for accurate results in capacitor regions
    "mesh_size": {
        "1t1_mesh_3": 2,    # Fine mesh around capacitor regions (2 um)
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
    # Example sweeps - uncomment as needed
    # "cap_center_width": [100, 150, 200, 250, 300],
    # "cap_center_length": [400, 500, 600, 700, 800],
    # "cap_gap": [10, 15, 20, 25, 30],
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
    design_name='bias_resonator',
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
print(f"  Run ANSYS simulations: {dir_path}/simulation.bat")
print(f"  (Results will be automatically saved to database)")
print(f"{'='*60}\n")

# Optionally open in KLayout
if not args.no_gui:
    open_with_klayout_or_default_application(oas_file)
else:
    print("Skipping KLayout GUI (--no-gui flag set)")
