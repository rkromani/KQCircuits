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


"""Q3D Capacitance Simulation for MetCircle

Extracts the C-matrix between two signal nets:
  Port 1 (cap island)   -- the circular MET capacitor disc
  Port 2 (coupler arc)  -- the arc-shaped coupling conductor

The readout resonator (include_res=False) is disabled.
The feedline (always at y=0) is excluded by the simulation box,
whose top boundary is set well below y=0.

The C-matrix output gives:
  C11: self-capacitance of the cap island to ground
  C22: self-capacitance of the coupler arc to ground
  C12: mutual (coupling) capacitance between cap island and coupler arc
"""

import argparse
import json
import logging
import sys
from pathlib import Path

from kqcircuits.pya_resolver import pya
from kqcircuits.simulations.export.ansys.ansys_export import export_ansys
from kqcircuits.simulations.export.simulation_export import (
    cross_sweep_simulation,
    export_simulation_oas,
)

sys.path.insert(0, str(Path(__file__).parents[4]))
from simulations_database.tools.simulation_db import SimulationDB

from kqcircuits.elements.met_circle import MetCircle
from kqcircuits.simulations.port import InternalPort
from kqcircuits.simulations.post_process import PostProcess
from kqcircuits.simulations.single_element_simulation import get_single_element_sim_class
from kqcircuits.util.export_helper import (
    create_or_empty_tmp_directory,
    get_active_or_new_layout,
    open_with_klayout_or_default_application,
)

parser = argparse.ArgumentParser(description="Run Q3D capacitance simulation on MetCircle")
parser.add_argument("--no-gui", action="store_true",
                    help="Don't open KLayout to view results (default: open KLayout)")
parser.add_argument("--sweep-override", type=str, default=None,
                    help="Override sweep parameters as JSON (e.g., '{\"cap_diameter\": [80, 100, 120]}')")
args = parser.parse_args()

dir_path = create_or_empty_tmp_directory(Path(__file__).stem + "_output")

BaseSimClass = get_single_element_sim_class(MetCircle)


class MetCircleQ3dSim(BaseSimClass):
    """Q3D simulation for MetCircle capacitance extraction.

    Port 1: inside the circular cap island (MET capacitor plate)
    Port 2: inside the coupler arc conductor (readout coupling structure)

    Both conductors are floating (not connected to ground) when include_res=False,
    so use_floating_islands=True is required in the export parameters.
    """

    def build(self):
        super().build()

        # Clear any auto-generated ports from get_sim_ports
        self.ports = []

        # Port 1: center of the circular cap island
        self.ports.append(InternalPort(
            number=1,
            signal_location=pya.DPoint(0, self.cap_center_y),
            ground_location=None,
        ))

        # Port 2: inside the coupler arc conductor at angle 0 (rightward from cap center)
        coupler_inner_ir = self.cap_diameter/2 + self.coupler_cap_spacing
        coupler_inner_or = coupler_inner_ir + self.coupler_width
        coupler_mid_r = (coupler_inner_ir + coupler_inner_or) / 2
        self.ports.append(InternalPort(
            number=2,
            signal_location=pya.DPoint(coupler_mid_r, self.cap_center_y),
            ground_location=None,
        ))


SimClass = MetCircleQ3dSim

# Simulation box: encloses the cap island and coupler arc, excludes the feedline.
# Default cap_center_y=-1500, cap outer gap radius ~70 um, coupler outer radius ~120 um.
# Box top at y=-1000 keeps the feedline (y=0) outside the simulation domain.
sim_parameters = {
    "name": "met_circle_q3d",
    "use_internal_ports": True,
    "use_ports": True,
    "box": pya.DBox(pya.DPoint(-600, -1900), pya.DPoint(600, -1000)),
    "face_stack": ["1t1"],
    "include_res": False,   # disable resonator waveguide; keeps coupler arc floating
    "enable_rlc": False,    # keep physical gap geometry, no lumped element overlay
}

export_parameters = {
    "path": dir_path,
    "ansys_tool": "q3d",
    "post_process": PostProcess("produce_cmatrix_table.py"),
    "exit_after_run": False,
    "percent_error": 0.3,
    "minimum_converged_passes": 2,
    "maximum_passes": 20,
    "use_floating_islands": True,   # cap island and coupler arc are both floating nets
}

logging.basicConfig(level=logging.WARN, stream=sys.stdout)
layout = get_active_or_new_layout()

simulations = []

sweep_params = {
    # "cap_diameter": [80, 100, 120],
    # "cap_gap": [15, 20, 25],
    # "coupler_angle": [45, 60, 75],
    # "coupler_width": [20, 30, 40],
    "coupler_cap_spacing": [5, 10, 15],  # distance between coupler and cap
}

if args.sweep_override:
    try:
        sweep_overrides = json.loads(args.sweep_override)
        sweep_params.update(sweep_overrides)
        print(f"Applied sweep overrides: {sweep_overrides}")
    except json.JSONDecodeError as e:
        print(f"Warning: Could not parse sweep overrides: {e}")

simulations += cross_sweep_simulation(
    layout,
    SimClass,
    sim_parameters,
    sweep_params,
)

db = SimulationDB()
db_folders = db.register_simulations(
    simulations=simulations,
    design_name="met_circle",
    sim_parameters=sim_parameters,
    export_parameters=export_parameters,
    output_folder=dir_path
)

export_ansys(simulations, **export_parameters)
oas_file = export_simulation_oas(simulations, dir_path)
print(f"Exported Q3D simulation files to: {dir_path}")
print(f"OAS file: {oas_file}")
print(f"Number of simulations: {len(simulations)}")

print(f"\n{'='*60}")
print(f"-> Next step:")
print(f"  Run ANSYS simulations: {dir_path}/simulation.bat")
print(f"  (Results will be automatically saved to database)")
print(f"{'='*60}\n")

if not args.no_gui:
    open_with_klayout_or_default_application(oas_file)
else:
    print("Skipping KLayout GUI (--no-gui flag set)")
