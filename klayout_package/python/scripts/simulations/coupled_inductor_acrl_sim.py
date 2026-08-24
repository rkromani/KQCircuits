# This code is part of KQCircuits
# Copyright (C) 2025 Roger Romani
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

from kqcircuits.elements.coupled_inductor import CoupledInductor
from kqcircuits.simulations.post_process import PostProcess
from kqcircuits.simulations.single_element_simulation import get_acrl_sim_class
from kqcircuits.util.export_helper import (
    create_or_empty_tmp_directory,
    get_active_or_new_layout,
    open_with_klayout_or_default_application,
)

# Parse command-line arguments
parser = argparse.ArgumentParser(description="Run Q3D ACRL simulations on bias resonator 2 (extracts C, L, and R matrices)")
parser.add_argument("--no-gui", action="store_true",
                    help="Don't open KLayout to view results (default: open KLayout)")
parser.add_argument("--sweep-override", type=str, default=None,
                    help="Override sweep parameters as JSON (e.g., '{\"l_coupling_distance\": [24, 32, 40]}')")
args = parser.parse_args()

# Prepare output directory
dir_path = create_or_empty_tmp_directory(Path(__file__).stem + "_output")

# Create ACRL simulation class using generic helper
# This automatically detects ACRL refpoints (acrl_source_main_inductor, acrl_sink_main_inductor)
# from the CoupledInductor element and stores them in extra_json_data
SimClass = get_acrl_sim_class(CoupledInductor)

# Simulation parameters for Q3D ACRL measurement
sim_parameters = {
    "name": "coupled_inductor_acrl",
    "use_internal_ports": True,   # Use internal ports for ACRL
    "use_ports": True,            # Enable port system
    "box": pya.DBox(pya.DPoint(-2000, -2500), pya.DPoint(1000, 500)),
    "face_stack": ["1t1"],

    # Enable inductor for ACRL inductance measurement through inductor
    "include_inductor": True,
    "sim_gap": True, #used to separate inductor from ground plane

    # Disable mesh layers for ACRL (ANSYS bug deletes mesh geometry instead of keeping it)
    "enable_mesh_layers": False,
}

# Q3D ACRL export parameters
export_parameters = {
    "path": dir_path,
    "ansys_tool": "q3d",
    # Use new post-processing script that handles C, L, and R matrices
    "post_process": PostProcess("produce_matrix_tables.py"),
    "exit_after_run": False,
    "percent_error": 0.3,  # Reasonable accuracy (0.2-0.5 typical for production)
    "minimum_converged_passes": 3,
    "maximum_passes": 20,
    "use_floating_islands": True,  # Treat isolated system as floating net

    "frequency_units": "GHz",

    # NEW: Enable ACRL (AC Resistance and Inductance extraction)
    # Source/sink locations will be read from acrl_source/sink refpoints in geometry
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

# Define base sweep parameters (can be overridden via --sweep-override)
import json
sweep_params = {
    # Example sweeps - uncomment as needed
    "l_tot_length": [5000, 6000, 7000],
    "l_coupling_distance": [20],
    "l_width": [4],
    "l_ground_sep": [300],
    "l_middle_sep": [300], 
    "l_connection_spacing": [400],
    'ground_cutout_width': [1500],
    'ground_cutout_height': [1200], 

}

# Apply sweep overrides if provided
if args.sweep_override:
    try:
        sweep_overrides = json.loads(args.sweep_override)
        sweep_params.update(sweep_overrides)
        print(f"Applied sweep overrides: {sweep_overrides}")
    except json.JSONDecodeError as e:
        print(f"Warning: Could not parse sweep overrides: {e}")

# Create geometry simulations
simulations = cross_sweep_simulation(
    layout,
    SimClass,
    sim_parameters,
    sweep_params,
)

# Register simulations with database
db = SimulationDB()
db_folders = db.register_simulations(
    simulations=simulations,
    design_name='coupled_inductor',
    sim_parameters=sim_parameters,
    export_parameters=export_parameters,
    output_folder=dir_path
)

# Export Ansys Q3D files with ACRL enabled
export_ansys(simulations, **export_parameters)

# Write oas file
oas_file = export_simulation_oas(simulations, dir_path)
print(f"\nExported Q3D ACRL simulation files to: {dir_path}")
print(f"OAS file: {oas_file}")
print(f"Number of geometry variations: {len(simulations)}")

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
    print("\nSkipping KLayout GUI (--no-gui flag set)")
