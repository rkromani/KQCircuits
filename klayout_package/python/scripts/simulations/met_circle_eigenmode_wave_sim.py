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


"""Eigenmode + Wave S21 Simulation for MetCircle

Eigenmode: RLC lumped element for the MET junction (parallel L+C) replaces
the physical bridge geometry. The lumped element port defines the resonator
circuit topology without needing a separate net assignment port.

Wave: Feedline edge ports (1, 2) for S21 measurement plus the same lumped
RLC port (3) for MET.
"""

import argparse
import logging
import sys
from pathlib import Path

from kqcircuits.pya_resolver import pya
from kqcircuits.simulations.export.ansys.ansys_solution import get_ansys_solution
from kqcircuits.simulations.export.ansys.ansys_export import export_ansys_json
from kqcircuits.simulations.export.simulation_export import (
    cross_sweep_simulation,
    export_simulation_oas,
)
from kqcircuits.simulations.post_process import PostProcess
from kqcircuits.util.export_helper import (
    create_or_empty_tmp_directory,
    get_active_or_new_layout,
    open_with_klayout_or_default_application,
)
from kqcircuits.defaults import ANSYS_EXECUTABLE

sys.path.insert(0, str(Path(__file__).parents[4]))
from simulations_database.tools.simulation_db import SimulationDB

from kqcircuits.elements.met_circle import MetCircle
from kqcircuits.simulations.port import InternalPort
from kqcircuits.simulations.single_element_simulation import get_single_element_sim_class


# ===========================
# Simulation Classes
# ===========================

BaseSimClass = get_single_element_sim_class(MetCircle)


class MetCircleEigenmodeSim(BaseSimClass):
    """HFSS eigenmode simulation for MetCircle.

    MET junction modeled as a lumped parallel L+C boundary on the lumped_rlc layer.
    No feedline ports needed for eigenmode.
    """

    def build(self):
        super().build()

        # Remove any auto-generated ports; eigenmode does not need feedline ports.
        self.ports = []

        # Lumped MET: parallel inductor and capacitor.
        # Always use refpoints, never recalculate geometry coordinates.
        self.ports.append(InternalPort(
            number=1,
            signal_location=self.refpoints["rlc_met_signal"],
            ground_location=self.refpoints["rlc_met_ground"],
            capacitance=self.rlc_met_c * 1e-15,
            inductance=self.rlc_met_l * 1e-9,
            resistance=0,
            lumped_element=True,
            rlc_type="parallel",
        ))


class MetCircleWaveSim(BaseSimClass):
    """HFSS wave simulation for MetCircle S-parameter measurement.

    Feedline edge ports (1, 2) for S21, plus lumped RLC port (3) for MET.
    """

    def build(self):
        super().build()

        # Remove any auto-generated ports before adding our own.
        self.ports = []

        # Feedline edge ports: waveguide stubs extend outward to the box edges.
        # feedline_a exits to the left (-x), feedline_b exits to the right (+x).
        feedline_a = self.refpoints["feedline_a"]
        feedline_b = self.refpoints["feedline_b"]

        self.produce_waveguide_to_port(
            feedline_a,
            feedline_a + pya.DVector(-100, 0),  # direction: outward (left)
            port_nr=1,
            side="left",
            use_internal_ports=False,
        )
        self.produce_waveguide_to_port(
            feedline_b,
            feedline_b + pya.DVector(100, 0),   # direction: outward (right)
            port_nr=2,
            side="right",
            use_internal_ports=False,
        )

        # Lumped MET: parallel L+C boundary.
        self.ports.append(InternalPort(
            number=3,
            signal_location=self.refpoints["rlc_met_signal"],
            ground_location=self.refpoints["rlc_met_ground"],
            capacitance=self.rlc_met_c * 1e-15,
            inductance=self.rlc_met_l * 1e-9,
            resistance=0,
            lumped_element=True,
            rlc_type="parallel",
        ))


# ===========================
# Command-line arguments
# ===========================

parser = argparse.ArgumentParser(description="MetCircle eigenmode + wave simulation workflow")
parser.add_argument("--no-gui", action="store_true", help="Don't open KLayout to view results")
parser.add_argument("--eigenmode-only", action="store_true",
                    help="Only run eigenmode simulations, skip wave/S21 simulations")
parser.add_argument("--sweep-width", type=float, default=1.0,
                    help="Frequency sweep width around eigenfrequency in GHz (default: 1.0)")
parser.add_argument("--eigenmode-mode", type=str, default="each", choices=["each", "shared"],
                    help="'each': eigenmode+wave per sweep point, 'shared': one eigenmode for all (default: each)")
args = parser.parse_args()

# ===========================
# Output directory
# ===========================

dir_path = create_or_empty_tmp_directory(Path(__file__).stem + "_output")

logging.basicConfig(level=logging.WARN, stream=sys.stdout)
layout = get_active_or_new_layout()

# ===========================
# Simulation Parameters
# ===========================

shared_params = {
    "face_stack": ["1t1"],
    "a": 10,
    "b": 6,
    "n": 64,
    "enable_rlc": True,
    "feedline_cutout_bool": False,
    # RLC values (adjust to match device)
    "rlc_met_c": 60,   # fF
    "rlc_met_l": 16.5,   # nH
}

eigenmode_sim_parameters = {
    "name": "met_circle_eigenmode",
    "use_internal_ports": True,
    "use_ports": True,
    "box": pya.DBox(pya.DPoint(-1000, -1700), pya.DPoint(1000, 300)),
    **shared_params,
}

eigenmode_solution_parameters = {
    "ansys_tool": "eigenmode",
    "n_modes": 3,
    "min_frequency": 5,
    "max_delta_f": 1,
    "maximum_passes": 20,
    "minimum_converged_passes": 2,
    "mesh_size": {
        "1t1_mesh_1": 7,
    },
}

eigenmode_export_parameters = {
    "path": dir_path,
    "post_process": PostProcess("produce_epr_table.py"),
    "exit_after_run": False,
}

wave_sim_parameters = {
    "name": "met_circle_wave",
    "use_internal_ports": False,
    "use_ports": True,
    "box": pya.DBox(pya.DPoint(-1500, -1700), pya.DPoint(1500, 300)),
    "port_size": 100,
    **shared_params,
}

wave_solution_parameters = {
    "ansys_tool": "hfss",
    "frequency": 6,
    "max_delta_s": 0.01,
    "sweep_start": 5.5,   # placeholder - updated by eigenmode result
    "sweep_end": 6.5,     # placeholder - updated by eigenmode result
    "sweep_count": 5001,
    "sweep_type": "interpolating",
    "maximum_passes": 10,
    "minimum_converged_passes": 1,
    "mesh_size": {
        "1t1_mesh_1": 3,
    },
}

wave_export_parameters = {
    "path": dir_path,
    "post_process": PostProcess("produce_s_matrix.py"),
    "exit_after_run": False,
}

# ===========================
# Parameter Sweeps
# ===========================

sweep_params = {
    # Example: sweep MET inductance to study frequency tuning
    # "rlc_met_l": [6.0, 8.1, 10.0],
    # Example: sweep resonator length
    # "res_length": [3800, 3950, 4200],
}

# ===========================
# Generate Simulations
# ===========================

print("\n" + "="*70)
print("MetCircle Eigenmode + Wave Simulation Workflow")
print("="*70)
print(f"Mode: {'eigenmode only' if args.eigenmode_only else args.eigenmode_mode}")
if not args.eigenmode_only:
    print(f"Sweep width: +/- {args.sweep_width/2} GHz around eigenfrequency")
print("="*70 + "\n")

if args.eigenmode_only or args.eigenmode_mode == "each":
    eigenmode_sims = cross_sweep_simulation(layout, MetCircleEigenmodeSim, eigenmode_sim_parameters, sweep_params)
    print(f"Creating {len(eigenmode_sims)} eigenmode simulations")
elif args.eigenmode_mode == "shared":
    eigenmode_sims = cross_sweep_simulation(layout, MetCircleEigenmodeSim, eigenmode_sim_parameters, {})
    print(f"Creating 1 shared eigenmode simulation (used for all sweep points)")

if not args.eigenmode_only:
    wave_sims = cross_sweep_simulation(layout, MetCircleWaveSim, wave_sim_parameters, sweep_params)
    print(f"Creating {len(wave_sims)} wave simulations")
else:
    wave_sims = []

# ===========================
# Register with Database
# ===========================

db = SimulationDB()
all_params = {**eigenmode_sim_parameters}
all_export_params = {**eigenmode_solution_parameters, **eigenmode_export_parameters}
if not args.eigenmode_only:
    all_params.update(wave_sim_parameters)
    all_export_params.update({**wave_solution_parameters, **wave_export_parameters})

db_folders = db.register_simulations(
    simulations=eigenmode_sims + wave_sims,
    design_name="met_circle",
    sim_parameters=all_params,
    export_parameters=all_export_params,
    output_folder=dir_path
)

# ===========================
# Export JSON Files
# ===========================

print("\nExporting simulation files...")

eigenmode_json_files = []
for sim in eigenmode_sims:
    solution = get_ansys_solution(**eigenmode_solution_parameters)
    json_path = export_ansys_json(sim, solution, dir_path)
    eigenmode_json_files.append(json_path)

wave_json_files = []
for sim in wave_sims:
    solution = get_ansys_solution(**wave_solution_parameters)
    json_path = export_ansys_json(sim, solution, dir_path)
    wave_json_files.append(json_path)

print(f"Exported {len(eigenmode_json_files)} eigenmode JSON files")
if not args.eigenmode_only:
    print(f"Exported {len(wave_json_files)} wave JSON files")

# ===========================
# Create Batch File
# ===========================

print("\nCreating batch file...")

bat_file = dir_path / "simulation.bat"
eigenmode_wave_script = Path(__file__).parent / "ansys" / "eigenmode_wave_batch.py"
batch_simulate_script = Path(__file__).parent / "ansys" / "batch_import_and_simulate.py"

if isinstance(db_folders, dict) and db_folders:
    first_sim_folder = list(db_folders.values())[0]
    sweep_folder = first_sim_folder.parent if hasattr(first_sim_folder, "parent") else Path(first_sim_folder).parent
elif db_folders:
    sweep_folder = Path(str(db_folders)).parent
else:
    sweep_folder = None

with open(bat_file, "w") as f:
    f.write("@echo off\n")
    f.write("set ANS_USE_ISOLATED_CLIPBOARD=1\n\n")

    if args.eigenmode_only:
        f.write("title MetCircle Eigenmode Simulations\n")
        f.write(f"echo Running {len(eigenmode_sims)} eigenmode simulation(s) in one ANSYS session...\n\n")
        all_jsons = ";".join(str(p) for p in eigenmode_json_files)
        f.write(f'"{ANSYS_EXECUTABLE}" -scriptargs "{all_jsons}" -RunScript "{batch_simulate_script}"\n')
    elif args.eigenmode_mode == "each":
        f.write("title MetCircle Eigenmode + Wave Simulations\n")
        f.write(f"echo Running {len(wave_sims)} eigenmode + wave pairs...\n")
        f.write(f"echo Sweep width: +/- {args.sweep_width/2} GHz\n\n")
        for i, (eigen_json, wave_json) in enumerate(zip(eigenmode_json_files, wave_json_files)):
            arg = f"{eigen_json};{wave_json};{args.sweep_width}"
            f.write(f"echo Simulation {i+1}/{len(wave_sims)}\n")
            f.write(f'"{ANSYS_EXECUTABLE}" -scriptargs "{arg}" -RunScript "{eigenmode_wave_script}"\n')
            f.write("echo.\n")
    elif args.eigenmode_mode == "shared":
        f.write("title MetCircle Eigenmode + Wave Simulations\n")
        f.write(f"echo Running 1 shared eigenmode + {len(wave_sims)} wave simulations...\n")
        f.write(f"echo Sweep width: +/- {args.sweep_width/2} GHz\n\n")
        shared_eigenmode_json = eigenmode_json_files[0]
        for i, wave_json in enumerate(wave_json_files):
            arg = f"{shared_eigenmode_json};{wave_json};{args.sweep_width}"
            f.write(f"echo Simulation {i+1}/{len(wave_sims)}\n")
            f.write(f'"{ANSYS_EXECUTABLE}" -scriptargs "{arg}" -RunScript "{eigenmode_wave_script}"\n')
            f.write("echo.\n")

    f.write("\necho ========================================\n")
    f.write("echo All ANSYS simulations complete!\n")
    f.write("echo ========================================\n\n")

    if not args.eigenmode_only and sweep_folder:
        for i, wave_sim in enumerate(wave_sims):
            wave_name = wave_sim.name
            eigen_name = eigenmode_sims[i].name if args.eigenmode_mode == "each" else eigenmode_sims[0].name
            src_file = f"{dir_path}\\{eigen_name}_and_{wave_name}_SMatrix.s2p"
            dst_folder = f"{sweep_folder}\\{wave_name}\\results"
            dst_file = f"{dst_folder}\\{wave_name}.s2p"
            f.write(f"echo Copying {wave_name}.s2p to database...\n")
            f.write(f'copy "{src_file}" "{dst_file}" >nul 2>&1\n')
            f.write("if %ERRORLEVEL% EQU 0 (\n")
            f.write(f"    echo   [OK] {wave_name}.s2p\n")
            f.write(") else (\n")
            f.write(f"    echo   [SKIP] {wave_name}.s2p not found\n")
            f.write(")\n")

        python_exe = sys.executable
        finalize_script = Path(__file__).parents[4] / "simulations_database" / "tools" / "finalize_and_fit.py"
        f.write(f'\n"{python_exe}" "{finalize_script}" "{sweep_folder}"\n')

    f.write("\ntimeout /t 30\n")

print(f"Created batch file: {bat_file}")

# ===========================
# Export OAS
# ===========================

oas_file = export_simulation_oas(eigenmode_sims + wave_sims, dir_path)

print(f"\n{'='*70}")
print(f"EXPORT COMPLETE")
print(f"{'='*70}")
print(f"Output: {dir_path}")
if args.eigenmode_only:
    print(f"Eigenmode sims: {len(eigenmode_sims)} (eigenmode only)")
else:
    print(f"Eigenmode sims: {len(eigenmode_sims)}, Wave sims: {len(wave_sims)}")
print(f"Next step: cd {dir_path} && simulation.bat")
print(f"{'='*70}\n")

if not args.no_gui:
    open_with_klayout_or_default_application(oas_file)
else:
    print("Skipping KLayout GUI (--no-gui flag set)")
