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
from kqcircuits.simulations.export.ansys.ansys_solution import AnsysQ3dSolution
from kqcircuits.simulations.export.simulation_export import (
    cross_sweep_simulation,
    cross_sweep_solution,
    cross_combine,
    export_simulation_oas,
)

# Import simulation database manager
sys.path.insert(0, str(Path(__file__).parents[4]))  # Add repo root to path
from simulations_database.tools.simulation_db import SimulationDB

from kqcircuits.elements.resonator_spike import ResonatorSpike
from kqcircuits.simulations.post_process import PostProcess
from kqcircuits.simulations.single_element_simulation import get_acrl_sim_class
from kqcircuits.util.export_helper import (
    create_or_empty_tmp_directory,
    get_active_or_new_layout,
    open_with_klayout_or_default_application,
)

# Parse command-line arguments
parser = argparse.ArgumentParser(description="Run Q3D ACRL simulations on spike resonator (extracts C, L, and R matrices)")
parser.add_argument("--no-gui", action="store_true",
                    help="Don't open KLayout to view results (default: open KLayout)")
parser.add_argument("--sweep-override", type=str, default=None,
                    help="Override sweep parameters as JSON (e.g., '{\"l_coupling_distance\": [2, 5, 10]}')")
args = parser.parse_args()

# Prepare output directory
dir_path = create_or_empty_tmp_directory(Path(__file__).stem + "_output")

# Create ACRL simulation class using generic helper
# This automatically detects numbered ACRL refpoints (acrl_source_N, acrl_sink_N)
# from the ResonatorSpike element and stores them in extra_json_data
SimClass = get_acrl_sim_class(ResonatorSpike)

# Simulation parameters for Q3D ACRL measurement
sim_parameters = {
    "name": "resonator_spike_acrl",
    "use_internal_ports": True,   # Use internal port on center spike region
    "use_ports": True,            # Enable port system
    "box": pya.DBox(pya.DPoint(0, -3000), pya.DPoint(2000, 3000)),
    #"shadow_angle_1": 0,
    #"shadow_angle_2": 0,
    #"spike_number": 50,
    #"spike_height": 0.5,
    #"spike_base_width": 0.25,
    #"end_box_height": 50,
    #"l_height": 1600,
    #"spike_gap": 0.1,
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
    "exit_after_run": False,
    "percent_error": 0.3,  # Reasonable accuracy (0.2-0.5 typical for production)
    "minimum_converged_passes": 3,
    "maximum_passes": 20,
    "use_floating_islands": True,  # Treat isolated spike system as floating net

    "frequency_units": "GHz",

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

# Define base sweep parameters (can be overridden via --sweep-override)
import json
sweep_params = {
    #"l_coupling_length": [50, 100, 250, 500],
    #"feedline_length": [500, 750, 1000, 1250, 1500],
    #"feedline_spacing": [1, 2, 5, 10, 20],
    #"l_coupling_distance": [2, 5]
    "l_height": [1000, 1500, 2000, 2500],
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

# Create frequency sweep solutions
# Frequency parameter belongs to the solution, not the simulation
"""solutions = cross_sweep_solution(
    AnsysQ3dSolution,
    {
        "percent_error": export_parameters["percent_error"],
        "minimum_converged_passes": export_parameters["minimum_converged_passes"],
        "maximum_passes": export_parameters["maximum_passes"],
        "use_floating_islands": export_parameters["use_floating_islands"],
        "solve_acrl": export_parameters["solve_acrl"],
        "frequency_units": export_parameters["frequency_units"],
    },
    {
        "frequency": [5],  # 100 MHz, 1 GHz, 5 GHz
    },
)"""

# Combine simulations with solutions to create all combinations
#simulation_solution_pairs = cross_combine(simulations, solution)


# Register simulations with database
db = SimulationDB()
db_folders = db.register_simulations(
    simulations=simulations,
    design_name='spike_resonator',
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
#print(f"Number of frequency points: {len(solutions)}")
#print(f"Total simulations (geometry × frequency): {len(simulation_solution_pairs)}")
#print(f"\nACRL enabled: Will extract L-matrix, R-matrix, and C-matrix")
#print(f"Expected output files:")
#print(f"  - *_cmatrix_results.csv (capacitance matrix)")
#print(f"  - *_lmatrix_results.csv (inductance matrix)")
#print(f"  - *_rmatrix_results.csv (resistance matrix)")

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
