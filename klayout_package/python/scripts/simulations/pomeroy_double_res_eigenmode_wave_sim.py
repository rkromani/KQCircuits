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


"""Eigenmode + Wave S21 Simulation for Pomeroy Double Resonator

PomeroyDoubleRes has four Manhattan-type capacitors (c1-c4) drawn on the
SIS_junction / lumped_rlc layer. Each is modeled as a lumped capacitor
boundary in ANSYS with capacitance set via cap_capacitance and zero resistance.
The feedline has two edge ports (left/right) for the wave S21 simulation.
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

from kqcircuits.elements.pomeroy_double_res import PomeroyDoubleRes
from kqcircuits.simulations.port import InternalPort
from kqcircuits.simulations.single_element_simulation import get_single_element_sim_class
from kqcircuits.util.parameters import Param, pdt


# ===========================
# Simulation Classes
# ===========================

BaseSimClass = get_single_element_sim_class(PomeroyDoubleRes)

_CAP_NAMES = ["c1", "c2", "c3", "c4"]


class PomeroyDoubleResEigenmodeSim(BaseSimClass):
    """HFSS eigenmode simulation for Pomeroy Double Resonator.

    Each of the four Manhattan capacitors is modeled as a lumped capacitor
    boundary (ports 1-4) attached to the lumped_rlc layer from PomeroyCap.
    """

    cap_capacitance = Param(pdt.TypeDouble, "Lumped capacitance of each Manhattan capacitor", 200e-15, unit="F")

    def build(self):
        super().build()

        # Eigenmode does not use feedline edge ports.
        self.ports = []

        # Add one lumped capacitor boundary per PomeroyCap instance.
        for i, cap_name in enumerate(_CAP_NAMES, start=1):
            signal_loc = self.refpoints[f"{cap_name}_cap_signal"]
            ground_loc = self.refpoints[f"{cap_name}_cap_ground"]
            self.ports.append(
                InternalPort(
                    number=i,
                    signal_location=signal_loc,
                    ground_location=ground_loc,
                    resistance=1e9,
                    capacitance=self.cap_capacitance,
                    lumped_element=True,
                )
            )


class PomeroyDoubleResWaveSim(BaseSimClass):
    """HFSS wave simulation for Pomeroy Double Resonator S-parameter measurement.

    Two edge ports at the feedline ends (ports 1-2) plus one lumped capacitor
    boundary per PomeroyCap instance (ports 3-6).
    """

    cap_capacitance = Param(pdt.TypeDouble, "Lumped capacitance of each Manhattan capacitor", 200e-15, unit="F")

    def build(self):
        super().build()

        # Clear auto-generated ports before adding our own.
        self.ports = []

        # Feedline edge ports: extensions out to the box edges.
        feedline_a = self.refpoints["feedline_a"]
        feedline_b = self.refpoints["feedline_b"]

        self.produce_waveguide_to_port(
            feedline_a,
            feedline_a + pya.DVector(-100, 0),  # direction: left
            port_nr=1,
            side="left",
            use_internal_ports=False,
        )
        self.produce_waveguide_to_port(
            feedline_b,
            feedline_b + pya.DVector(100, 0),   # direction: right
            port_nr=2,
            side="right",
            use_internal_ports=False,
        )

        # One lumped capacitor boundary per PomeroyCap instance (ports 3-6).
        for i, cap_name in enumerate(_CAP_NAMES, start=3):
            signal_loc = self.refpoints[f"{cap_name}_cap_signal"]
            ground_loc = self.refpoints[f"{cap_name}_cap_ground"]
            self.ports.append(
                InternalPort(
                    number=i,
                    signal_location=signal_loc,
                    ground_location=ground_loc,
                    resistance=1e9,
                    capacitance=self.cap_capacitance,
                    lumped_element=True,
                )
            )


# ===========================
# Command-line arguments
# ===========================

parser = argparse.ArgumentParser(description="Pomeroy Double Resonator eigenmode + wave simulation")
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

# Capacitance of each Manhattan capacitor in Farads.
CAP_CAPACITANCE = 200e-15  # 200 fF default

shared_params = {
    "face_stack": ["1t1"],
    "a": 10,
    "b": 6,
    "n": 24,
    "enable_mesh_layers": True,
    "feedline_cutout_bool": False,
}

eigenmode_sim_parameters = {
    "name": "pomeroy_double_res_eigenmode",
    "use_internal_ports": True,
    "use_ports": True,
    "box": pya.DBox(pya.DPoint(-1200, -1600), pya.DPoint(1200, 200)),
    "cap_capacitance": CAP_CAPACITANCE,
    **shared_params,
}

eigenmode_solution_parameters = {
    "ansys_tool": "eigenmode",
    "n_modes": 1,
    "min_frequency": 1,
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
    "name": "pomeroy_double_res_wave",
    "use_internal_ports": False,
    "use_ports": True,
    "box": pya.DBox(pya.DPoint(-1500, -1600), pya.DPoint(1500, 200)),
    "cap_capacitance": CAP_CAPACITANCE,
    **shared_params,
}

wave_solution_parameters = {
    "ansys_tool": "hfss",
    "frequency": 5,
    "max_delta_s": 0.01,
    "sweep_start": 4.5,
    "sweep_end": 5.5,
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
    # Sweep all four capacitors together (same value for each).
    "cap_capacitance": [88e-15, 198e-15],
}

# ===========================
# Generate Simulations
# ===========================

print("\n" + "="*70)
print("Pomeroy Double Resonator Eigenmode + Wave Simulation Workflow")
print("="*70)
print(f"Mode: {'eigenmode only' if args.eigenmode_only else args.eigenmode_mode}")
print(f"Cap capacitance: {CAP_CAPACITANCE*1e15:.1f} fF (each of 4 caps)")
if not args.eigenmode_only:
    print(f"Sweep width: +/- {args.sweep_width/2} GHz around eigenfrequency")
print("="*70 + "\n")

if args.eigenmode_only or args.eigenmode_mode == "each":
    eigenmode_sims = cross_sweep_simulation(layout, PomeroyDoubleResEigenmodeSim, eigenmode_sim_parameters, sweep_params)
    print(f"Creating {len(eigenmode_sims)} eigenmode simulations")
elif args.eigenmode_mode == "shared":
    eigenmode_sims = cross_sweep_simulation(layout, PomeroyDoubleResEigenmodeSim, eigenmode_sim_parameters, {})
    print(f"Creating 1 shared eigenmode simulation (used for all sweep points)")

if not args.eigenmode_only:
    wave_sims = cross_sweep_simulation(layout, PomeroyDoubleResWaveSim, wave_sim_parameters, sweep_params)
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
    design_name="pomeroy_double_res",
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
        f.write(f"title Pomeroy Double Resonator Eigenmode Simulations\n")
        f.write(f"echo Running {len(eigenmode_sims)} eigenmode simulation(s) in one ANSYS session...\n\n")
        all_jsons = ";".join(str(p) for p in eigenmode_json_files)
        f.write(f'"{ANSYS_EXECUTABLE}" -scriptargs "{all_jsons}" -RunScript "{batch_simulate_script}"\n')
    elif args.eigenmode_mode == "each":
        f.write(f"title Pomeroy Double Resonator Eigenmode + Wave Simulations\n")
        f.write(f"echo Running {len(wave_sims)} eigenmode + wave pairs...\n")
        f.write(f"echo Sweep width: +/- {args.sweep_width/2} GHz\n\n")
        for i, (eigen_json, wave_json) in enumerate(zip(eigenmode_json_files, wave_json_files)):
            arg = f"{eigen_json};{wave_json};{args.sweep_width}"
            f.write(f"echo Simulation {i+1}/{len(wave_sims)}\n")
            f.write(f'"{ANSYS_EXECUTABLE}" -scriptargs "{arg}" -RunScript "{eigenmode_wave_script}"\n')
            f.write("echo.\n")
    elif args.eigenmode_mode == "shared":
        f.write(f"title Pomeroy Double Resonator Eigenmode + Wave Simulations\n")
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
