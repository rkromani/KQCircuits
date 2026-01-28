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

from kqcircuits.chips.NIST_bias_spike_res import BiasSpikeResTest
from kqcircuits.simulations.post_process import PostProcess
from kqcircuits.simulations.single_element_simulation import get_single_element_sim_class
from kqcircuits.util.export_helper import (
    create_or_empty_tmp_directory,
    get_active_or_new_layout,
    open_with_klayout_or_default_application,
)

# Parse command-line arguments
parser = argparse.ArgumentParser(description="Run HFSS eigenmode simulations on bias spike resonator")
parser.add_argument("--no-gui", action="store_true",
                    help="Don't open KLayout to view results (default: open KLayout)")
parser.add_argument("--sweep-override", type=str, default=None,
                    help="Override sweep parameters as JSON (e.g., '{\"finger_length\": [5, 10, 20]}')")
args = parser.parse_args()

# Prepare output directory
dir_path = create_or_empty_tmp_directory(Path(__file__).stem + "_output")

# Create custom simulation class
BaseSimClass = get_single_element_sim_class(BiasSpikeResTest)

class BiasSpikeResHfssSim(BaseSimClass):
    """Custom simulation class for HFSS eigenmode analysis of bias spike resonator.

    This performs eigenmode analysis to extract resonance frequencies and Q factors.
    """

    def build(self):
        # Call parent build to create geometry
        super().build()

        # DON'T clear ports if using lumped models - they contain the lumped RLC definitions!
        # Instead, conditionally set up ports based on whether lumped models are used

        # Check if we're using lumped models
        using_lumped = getattr(self, 'use_lumped_models', False)

        from kqcircuits.simulations.port import InternalPort

        if not using_lumped:
            # FULL GEOMETRY MODE: Clear ports and add net assignment ports
            self.ports = []

            # Port on capacitor center conductor
            signal_loc_cap = self.refpoints['CAP_signal_location']

            # Port on inductor - use the ACRL source point which is in the inductor metal
            try:
                signal_loc_inductor = self.refpoints['RS_acrl_source_main_inductor']
            except KeyError:
                signal_loc_inductor = self.refpoints['RS_inductor_ground']

            # Both ports use number=1, telling ANSYS they're the same electrical net
            self.ports.append(
                InternalPort(
                    number=1,
                    signal_location=signal_loc_cap,
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
        else:
            # LUMPED MODEL MODE: Create lumped RLC port directly (like xmons example)
            # This bypasses the edge-finding requirement - we specify locations directly
            self.ports = []

            # Create lumped capacitor port directly from refpoints
            cap_signal_loc = self.refpoints['CAP_signal_location']
            cap_ground_loc = self.refpoints['CAP_ground_location']

            self.ports.append(
                InternalPort(
                    number=1,
                    signal_location=cap_signal_loc,
                    ground_location=cap_ground_loc,
                    capacitance=getattr(self, 'cap_lumped_value', 150.0) * 1e-15,  # fF to F
                    inductance=0,
                    resistance=0,
                    lumped_element=True,
                    rlc_type="parallel",
                )
            )

SimClass = BiasSpikeResHfssSim

# Simulation parameters for HFSS eigenmode analysis
sim_parameters = {
    "name": "bias_spike_res_eigenmode",
    "use_internal_ports": True,   # Use internal port to define signal net
    "use_ports": True,            # Enable port system for net assignment
    "box": pya.DBox(pya.DPoint(-500, -4500), pya.DPoint(1000, 1500)),
    "ground_cutout_bool": True,
    "face_stack": ["1t1"],

    "l_height": 2000,
    "spike_number": 0,
    "junction_bool": False,
    "use_lumped_models": True,

    #"finger_number": 40,
    "finger_length": 100,
    "finger_gap": 2, 
    "ground_cutout_bool": False, 

    "a": 4.6,
    "b": 10,
    "n": 24, #number of points per circle
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
        "1t1_mesh_2": 6,  # inductor
        "1t1_mesh_3": 6,  # capacitor gaps
        #"1t1_mesh_4": 4,  # grounding capacitor gaps

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
    #"finger_number": [25, 50],
    "cap_lumped_value": [100, 150, 200],
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
    design_name='bias_spike_resonator',
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
print(f"→ Next step:")
print(f"  Run ANSYS simulations: {dir_path}\\simulation.bat")
print(f"  (Results will be automatically saved to database)")
print(f"{'='*60}\n")

# Optionally open in KLayout
if not args.no_gui:
    open_with_klayout_or_default_application(oas_file)
else:
    print("Skipping KLayout GUI (--no-gui flag set)")
