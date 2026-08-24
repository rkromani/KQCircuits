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


"""Eigenmode + Wave S21 Simulation for MetRfs

Eigenmode: RLC lumped element for the MET junction (parallel L+C+R) replaces
the physical junction. No feedline ports are needed because the lumped port
itself defines the resonator circuit.

Wave: Feedline edge ports (1, 2) for S-parameter measurement plus lumped
RLC port (3) for the junction.

Junction resistance note:
For a parallel RLC, Q_int = R / (omega_0 * L). Larger R means higher Q (less
internal loss). Set R=0 for an ideal lossless junction. To broaden the S21 dip
(simulate internal loss), decrease R, e.g. R = Q_target * omega_0 * L.
The parameter rlc_junction_r is exposed so you can sweep it to fit measured data.
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

from kqcircuits.elements.met_rfs import MetRfs
from kqcircuits.simulations.port import InternalPort
from kqcircuits.simulations.single_element_simulation import get_single_element_sim_class


# ===========================
# Simulation Classes
# ===========================

BaseSimClass_Eigenmode = get_single_element_sim_class(MetRfs)

class MetRfsEigenmodeSim(BaseSimClass_Eigenmode):
    """HFSS eigenmode simulation for MetRfs.

    Uses a single lumped parallel RLC port for the junction. The feedline is
    left open (no termination) -- this is sufficient for finding the resonance
    frequency and EPR participation of the junction mode.
    """

    def build(self):
        super().build()
        self.ports = []

        self.ports.append(InternalPort(
            number=1,
            signal_location=self.refpoints["rlc_junction_signal"],
            ground_location=self.refpoints["rlc_junction_ground"],
            capacitance=self.rlc_junction_c * 1e-15,
            inductance=self.rlc_junction_l * 1e-9,
            resistance=self.rlc_junction_r,
            lumped_element=True,
            rlc_type="parallel",
        ))


BaseSimClass_Wave = get_single_element_sim_class(MetRfs)

class MetRfsWaveSim(BaseSimClass_Wave):
    """HFSS wave simulation for MetRfs S-parameter measurement.

    Feedline edge ports (1, 2) for S21, plus lumped RLC port (3) for the junction.
    """

    def build(self):
        super().build()
        self.ports = []

        feedline_a = self.refpoints["feedline_a"]
        feedline_b = self.refpoints["feedline_b"]

        # Left feedline edge port: waveguide travels leftward from feedline_a to box edge
        self.produce_waveguide_to_port(
            feedline_a,
            pya.DPoint(feedline_a.x - 100, feedline_a.y),
            1,
            side="left",
            a=self.a,
            b=self.b,
            use_internal_ports=False,
        )

        # Right feedline edge port: waveguide travels rightward from feedline_b to box edge
        self.produce_waveguide_to_port(
            feedline_b,
            pya.DPoint(feedline_b.x + 100, feedline_b.y),
            2,
            side="right",
            a=self.a,
            b=self.b,
            use_internal_ports=False,
        )

        # Junction lumped RLC port
        self.ports.append(InternalPort(
            number=3,
            signal_location=self.refpoints["rlc_junction_signal"],
            ground_location=self.refpoints["rlc_junction_ground"],
            capacitance=self.rlc_junction_c * 1e-15,
            inductance=self.rlc_junction_l * 1e-9,
            resistance=self.rlc_junction_r,
            lumped_element=True,
            rlc_type="parallel",
        ))


# ===========================
# Command-line arguments
# ===========================

parser = argparse.ArgumentParser(description="MetRfs eigenmode + wave simulation workflow")
parser.add_argument("--no-gui", action="store_true", help="Don't open KLayout to view results")
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

# Shared geometry and RLC parameters used in both sims.
# Box sized for MetRfs defaults:
#   feedline at y=0, x in [-800, 800] (feedline_length=1600)
#   inductor cutout bottom ~-1531 um, MET structure bottom ~-1661 um
shared_params = {
    "face_stack": ["1t1"],
    "a": 10,
    "b": 6,
    "n": 24,
    "enable_rlc": True,          # Required: creates ground-plane gaps at RLC junction
    "feedline_cutout_bool": False,
    # RLC values for the junction (adjust to match device)
    "rlc_junction_c": 10,        # fF, junction capacitance
    "rlc_junction_l": 10,        # nH, junction (Josephson) inductance
    "rlc_junction_r": 0,         # Ohm, 0 = lossless; reduce to add internal loss
}

eigenmode_sim_parameters = {
    "name": "met_rfs_eigenmode",
    "use_internal_ports": True,
    "use_ports": True,
    "box": pya.DBox(pya.DPoint(-950, -1800), pya.DPoint(950, 300)),
    **shared_params,
}

eigenmode_solution_parameters = {
    "ansys_tool": "eigenmode",
    "n_modes": 3,
    "min_frequency": 4,
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
    "name": "met_rfs_wave",
    "use_internal_ports": False,  # Edge ports for S-parameters
    "use_ports": True,
    "box": pya.DBox(pya.DPoint(-950, -1800), pya.DPoint(950, 300)),
    "port_size": 100,
    **shared_params,
}

wave_solution_parameters = {
    "ansys_tool": "hfss",
    "frequency": 6,
    "max_delta_s": 0.01,
    "sweep_start": 5.5,    # placeholder - updated by eigenmode result
    "sweep_end": 6.5,      # placeholder - updated by eigenmode result
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
    # Sweep junction inductance to study frequency tuning
    # "rlc_junction_l": [8.0, 10.0, 12.0],
    # Sweep resistance to model internal loss (smaller R = lower Q = broader S21 dip)
    # "rlc_junction_r": [0, 5e4, 1e5],
    "rlc_junction_l": [10.0],
}

# ===========================
# Generate Simulations
# ===========================

print("\n" + "="*70)
print("MetRfs Eigenmode + Wave Simulation Workflow")
print("="*70)
print(f"Mode: {args.eigenmode_mode}")
print(f"Sweep width: +/- {args.sweep_width/2} GHz around eigenfrequency")
print("="*70 + "\n")

if args.eigenmode_mode == "each":
    eigenmode_sims = cross_sweep_simulation(layout, MetRfsEigenmodeSim, eigenmode_sim_parameters, sweep_params)
    print(f"Creating {len(eigenmode_sims)} eigenmode simulations (one per sweep point)")
elif args.eigenmode_mode == "shared":
    eigenmode_sims = cross_sweep_simulation(layout, MetRfsEigenmodeSim, eigenmode_sim_parameters, {})
    print(f"Creating 1 shared eigenmode simulation (used for all sweep points)")

wave_sims = cross_sweep_simulation(layout, MetRfsWaveSim, wave_sim_parameters, sweep_params)
print(f"Creating {len(wave_sims)} wave simulations")

# ===========================
# Register with Database
# ===========================

db = SimulationDB()
db_folders = db.register_simulations(
    simulations=eigenmode_sims + wave_sims,
    design_name="met_rfs",
    sim_parameters={**eigenmode_sim_parameters, **wave_sim_parameters},
    export_parameters={**eigenmode_solution_parameters, **eigenmode_export_parameters,
                       **wave_solution_parameters, **wave_export_parameters},
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
print(f"Exported {len(wave_json_files)} wave JSON files")

# ===========================
# Create Batch File
# ===========================

print("\nCreating batch file...")

bat_file = dir_path / "simulation.bat"
custom_script = Path(__file__).parent / "ansys" / "eigenmode_wave_batch.py"

if isinstance(db_folders, dict) and db_folders:
    first_sim_folder = list(db_folders.values())[0]
    sweep_folder = first_sim_folder.parent if hasattr(first_sim_folder, "parent") else Path(first_sim_folder).parent
elif db_folders:
    sweep_folder = Path(str(db_folders)).parent
else:
    sweep_folder = None

with open(bat_file, "w") as f:
    f.write("@echo off\n")
    f.write("title MetRfs Eigenmode + Wave Simulations\n")
    f.write("set ANS_USE_ISOLATED_CLIPBOARD=1\n\n")

    if args.eigenmode_mode == "each":
        f.write(f"echo Running {len(wave_sims)} eigenmode + wave pairs...\n")
        f.write(f"echo Sweep width: +/- {args.sweep_width/2} GHz\n\n")
        for i, (eigen_json, wave_json) in enumerate(zip(eigenmode_json_files, wave_json_files)):
            arg = f"{eigen_json};{wave_json};{args.sweep_width}"
            f.write(f"echo Simulation {i+1}/{len(wave_sims)}\n")
            f.write(f'"{ANSYS_EXECUTABLE}" -scriptargs "{arg}" -RunScript "{custom_script}"\n')
            f.write("echo.\n")
    elif args.eigenmode_mode == "shared":
        f.write(f"echo Running 1 shared eigenmode + {len(wave_sims)} wave simulations...\n")
        f.write(f"echo Sweep width: +/- {args.sweep_width/2} GHz\n\n")
        shared_eigenmode_json = eigenmode_json_files[0]
        for i, wave_json in enumerate(wave_json_files):
            arg = f"{shared_eigenmode_json};{wave_json};{args.sweep_width}"
            f.write(f"echo Simulation {i+1}/{len(wave_sims)}\n")
            f.write(f'"{ANSYS_EXECUTABLE}" -scriptargs "{arg}" -RunScript "{custom_script}"\n')
            f.write("echo.\n")

    f.write("\necho ========================================\n")
    f.write("echo All ANSYS simulations complete!\n")
    f.write("echo ========================================\n\n")

    if sweep_folder:
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
    else:
        f.write("echo WARNING: Could not determine database folder for post-processing\n")

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
print(f"Eigenmode sims: {len(eigenmode_sims)}, Wave sims: {len(wave_sims)}")
print(f"Next step: cd {dir_path} && simulation.bat")
print(f"{'='*70}\n")

if not args.no_gui:
    open_with_klayout_or_default_application(oas_file)
else:
    print("Skipping KLayout GUI (--no-gui flag set)")
