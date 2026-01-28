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

from kqcircuits.elements.finger_capacitor_ground_v3 import FingerCapacitorGroundV3
from kqcircuits.simulations.post_process import PostProcess
from kqcircuits.simulations.single_element_simulation import get_single_element_sim_class
from kqcircuits.util.export_helper import (
    create_or_empty_tmp_directory,
    get_active_or_new_layout,
    open_with_klayout_or_default_application,
)

# Parse command-line arguments
parser = argparse.ArgumentParser(description="Run Q3D capacitance simulations on grounded finger capacitor")
parser.add_argument("--no-gui", action="store_true",
                    help="Don't open KLayout to view results (default: open KLayout)")
parser.add_argument("--sweep-override", type=str, default=None,
                    help="Override sweep parameters as JSON (e.g., '{\"finger_length\": [5, 10, 20]}')")
args = parser.parse_args()

# Prepare output directory
dir_path = create_or_empty_tmp_directory(Path(__file__).stem + "_output")

# Create custom simulation class that adds a port to the center spike region
BaseSimClass = get_single_element_sim_class(FingerCapacitorGroundV3)

class FingerCapacitorQ3dSim(BaseSimClass):
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

        # Add internal port to CENTER finger structure (makes it a signal net)
        # Use the signal_location reference point from the element geometry
        # This point is at the center of the structure, inside the center conductor
        signal_loc = self.refpoints['signal_location']

        from kqcircuits.simulations.port import InternalPort
        self.ports.append(
            InternalPort(
                number=1,
                signal_location=signal_loc,
                ground_location=None,
            )
        )

SimClass = FingerCapacitorQ3dSim

# Simulation parameters for Q3D capacitance measurement
sim_parameters = {
    "name": "finger_capacitor_q3d",
    "use_internal_ports": True,   # Use internal port on center spike region
    "use_ports": True,            # Enable port system
    "box": pya.DBox(pya.DPoint(0, 0), pya.DPoint(500, 1500)),
    "ground_cutout_bool": True, 
    "face_stack": ["1t1"],
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
        "1t1_mesh_4": 0.5,    # Fine mesh around spike regions (0.25 µm)
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
    #"finger_number": [2, 4, 6, 8, 10],
    #"finger_length": [5, 10, 20, 50, 100],
    #"finger_width": [1, 2, 3, 5, 10, 20],
    "finger_gap": [1, 2, 3, 5, 10, 20],
}

# Apply sweep overrides if provided
if args.sweep_override:
    try:
        sweep_overrides = json.loads(args.sweep_override)
        sweep_params.update(sweep_overrides)
        print(f"Applied sweep overrides: {sweep_overrides}")
    except json.JSONDecodeError as e:
        print(f"Warning: Could not parse sweep overrides: {e}")

# Sweep spike number to characterize capacitance vs number of fingers
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
    design_name='finger_cap_grounded',
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
