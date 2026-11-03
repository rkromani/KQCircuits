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

from kqcircuits.elements.met_rfs import MetRfs
from kqcircuits.simulations.post_process import PostProcess
from kqcircuits.simulations.single_element_simulation import get_single_element_sim_class
from kqcircuits.util.export_helper import (
    create_or_empty_tmp_directory,
    get_active_or_new_layout,
    open_with_klayout_or_default_application,
)

# Parse command-line arguments
parser = argparse.ArgumentParser(
    description="Run Q3D capacitance simulation of the extra planar capacitor at the end of the MetRfs inductor"
)
parser.add_argument("--no-gui", action="store_true",
                    help="Don't open KLayout to view results (default: open KLayout)")
parser.add_argument("--sweep-override", type=str, default=None,
                    help="Override sweep parameters as JSON (e.g., '{\"extra_cap_height\": [40, 80, 120]}')")
args = parser.parse_args()

# Prepare output directory
dir_path = create_or_empty_tmp_directory(Path(__file__).stem + "_output")

# Create custom simulation class that adds an internal port on the extra planar capacitor.
# MetRfs.include_inductor=False leaves the inductor out entirely, so the capacitor pad and
# its connecting wire are a genuinely floating conductor, isolated from everything else and
# coupled to ground only through their own local geometry (the ground plane and the cutout
# around the pad are still fully present). No RLC/junction geometry is involved either way -
# enable_rlc=True (the default) only adds a marker shape on the unused lumped_rlc layer.
BaseSimClass = get_single_element_sim_class(MetRfs)


class MetRfsExtraCapQ3dSim(BaseSimClass):
    """Q3D capacitance measurement of the extra planar capacitor at the end of the MetRfs inductor.

    With include_inductor=False, the only metal left is the extra capacitor pad, its
    connecting wire, and the surrounding ground plane. Q3D reports the self-capacitance
    of this floating island, i.e. the geometric capacitance to ground of the extra
    planar capacitor alone.
    """

    def build(self):
        # Call parent build to create geometry
        super().build()

        # Clear default feedline ports (no feedline metal exists with include_inductor=False)
        self.ports = []

        from kqcircuits.simulations.port import InternalPort

        # Port on the extra capacitor pad. Ground is auto-detected from the nearest
        # ground metal (the walls of the cutout the pad sits in).
        self.ports.append(
            InternalPort(
                number=1,
                signal_location=self.refpoints["extra_cap_signal"],
                ground_location=None,
            )
        )


SimClass = MetRfsExtraCapQ3dSim

# Simulation parameters for Q3D capacitance measurement
sim_parameters = {
    "name": "met_rfs_extra_cap_q3d",
    "use_internal_ports": True,
    "use_ports": True,
    "face_stack": ["1t1"],

    # Leave the inductor out entirely, isolating the extra planar capacitor as its own
    # floating conductor (see MetRfs.include_inductor).
    "include_inductor": False,

    # No RLC/junction geometry either way (default), kept explicit for clarity.
    "enable_rlc": True,

    "enable_mesh_layers": True,

    # Auto-size the simulation box from the (now small) MetRfs geometry, with a generous
    # margin of surrounding ground plane for the Q3D field solution.
    "auto_size_box": True,
    "box_margin": 300,
}

# Q3D export parameters
export_parameters = {
    "path": dir_path,
    "ansys_tool": "q3d",
    "post_process": PostProcess("produce_cmatrix_table.py"),
    "exit_after_run": False,
    "percent_error": 0.3,
    "minimum_converged_passes": 2,
    "maximum_passes": 20,
    "use_floating_islands": True,  # Treat the isolated capacitor island as a floating net
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
     "extra_cap_height": [0.0, 10.0, 20.0, 40.0, 60.0, 80.0],
    # "extra_cap_spacing": [2, 5, 10, 15],
    # "met_ground_cutout_width": [30, 40, 50, 60],
}

# Apply sweep overrides if provided
if args.sweep_override:
    try:
        sweep_overrides = json.loads(args.sweep_override)
        sweep_params.update(sweep_overrides)
        print(f"Applied sweep overrides: {sweep_overrides}")
    except json.JSONDecodeError as e:
        print(f"Warning: Could not parse sweep overrides: {e}")

# Sweep extra capacitor parameters to characterize its capacitance to ground
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
    design_name='met_rfs_extra_cap',
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
