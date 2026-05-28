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

from kqcircuits.elements.double_res import DoubleRes
from kqcircuits.simulations.post_process import PostProcess
from kqcircuits.simulations.single_element_simulation import get_single_element_sim_class
from kqcircuits.util.export_helper import (
    create_or_empty_tmp_directory,
    get_active_or_new_layout,
    open_with_klayout_or_default_application,
)

# Parse command-line arguments
parser = argparse.ArgumentParser(description="Run HFSS eigenmode simulations on double resonator")
parser.add_argument("--no-gui", action="store_true",
                    help="Don't open KLayout to view results (default: open KLayout)")
parser.add_argument("--sweep-override", type=str, default=None,
                    help="Override sweep parameters as JSON (e.g., '{\"l_tot_length\": [10000, 12000]}')")
args = parser.parse_args()

# Prepare output directory
dir_path = create_or_empty_tmp_directory(Path(__file__).stem + "_output")

# Create custom simulation class
BaseSimClass = get_single_element_sim_class(DoubleRes)

class DoubleResHfssSim(BaseSimClass):
    """Custom simulation class for HFSS eigenmode analysis of double resonator.

    This performs eigenmode analysis to extract resonance frequencies and Q factors.
    """

    def build(self):
        # Call parent build to create geometry
        super().build()

        from kqcircuits.simulations.port import InternalPort

        # Set up net assignment ports for eigenmode
        self.ports = []

        # Port on feedline coupling region (center of feedline at y=0)
        signal_loc_feedline = pya.DPoint(0, 0)

        # Port on inductor - use ACRL source point if available
        try:
            signal_loc_inductor = self.refpoints['acrl_source_main_inductor']
        except KeyError:
            # Fallback to top center of ground gap
            signal_loc_inductor = pya.DPoint(0, self.ground_gap_top)

        # Both ports use number=1, telling ANSYS they're the same electrical net
        self.ports.append(
            InternalPort(
                number=1,
                signal_location=signal_loc_feedline,
                ground_location=None,
            )
        )

        self.ports.append(
            InternalPort(
                number=1,  # Same number = same net
                signal_location=signal_loc_inductor,
                ground_location=None,
            )
        )

SimClass = DoubleResHfssSim

# Simulation parameters for HFSS eigenmode analysis
sim_parameters = {
    "name": "double_res_eigenmode",
    "use_internal_ports": True,   # Use internal port to define signal net
    "use_ports": True,            # Enable port system for net assignment
    "box": pya.DBox(pya.DPoint(-1000, -1000), pya.DPoint(1000, 500)),
    "face_stack": ["1t1"],

    # DoubleRes parameters
    "include_inductor": True,
    "enable_mesh_layers": True,

    # CPW parameters
    "a": 10,
    "b": 6,
    "n": 24,  # number of points per circle
}

# HFSS eigenmode export parameters
export_parameters = {
    "path": dir_path,
    "ansys_tool": "eigenmode",
    "post_process": PostProcess("produce_epr_table.py"),  # Eigenmode post-processing
    "exit_after_run": False,

    # Eigenmode-specific parameters
    "n_modes": 1,  # Number of eigenmodes to solve for
    "min_frequency": 1,  # Minimum frequency in GHz
    "max_delta_f": 0.3,  # Convergence criterion: max frequency change (%)
    "maximum_passes": 20,
    "minimum_converged_passes": 2,

    # Custom mesh refinement for accurate results
    "mesh_size": {
        "1t1_mesh_1": 4,  # Fine mesh for capacitor gaps
        "1t1_mesh_2": 8,  # Coarse mesh for inductor
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
    # Example sweeps - adjust based on what you want to study
    # "l_tot_length": [10000, 12000, 14000],
    # "cap_wide_gap": [1, 2, 3],
    # "l_coupling_length": [60, 80, 100],
}

# Apply sweep overrides if provided
if args.sweep_override:
    try:
        sweep_overrides = json.loads(args.sweep_override)
        sweep_params.update(sweep_overrides)
        print(f"Applied sweep overrides: {sweep_overrides}")
    except json.JSONDecodeError as e:
        print(f"Warning: Could not parse sweep overrides: {e}")

# Generate simulations from parameter sweep
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

# Export Ansys HFSS eigenmode files
export_ansys(simulations, **export_parameters)

# Write oas file
oas_file = export_simulation_oas(simulations, dir_path)
print(f"Exported HFSS eigenmode simulation files to: {dir_path}")
print(f"OAS file: {oas_file}")
print(f"Number of simulations: {len(simulations)}")

# Print next steps for database workflow
print(f"\n{'='*60}")
print(f"-> Next step:")
print(f"  Run ANSYS simulations: {dir_path}\\simulation.bat")
print(f"  (Results will be automatically saved to database)")
print(f"{'='*60}\n")

# Optionally open in KLayout
if not args.no_gui:
    open_with_klayout_or_default_application(oas_file)
else:
    print("Skipping KLayout GUI (--no-gui flag set)")
