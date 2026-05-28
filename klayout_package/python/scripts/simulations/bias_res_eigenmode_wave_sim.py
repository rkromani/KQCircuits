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


"""Eigenmode + Wave S21 Simulation Workflow with Mesh Import for BiasResonator

This script creates a chained simulation workflow that:
1. Runs HFSS eigenmode simulation to extract resonance frequency
2. Uses eigenfrequency to configure wave equation S21 simulation sweep range
3. Imports mesh from eigenmode setup into wave setup (for faster convergence)
4. Runs wave simulation to measure S21 and extract coupling parameters

Both simulations run in the SAME ANSYS project for seamless mesh sharing.

Two eigenmode strategies available via --eigenmode-mode flag:
- "each": Eigenmode + wave for EACH sweep point (use when f_res varies with sweep)
- "shared": ONE eigenmode + wave for each sweep point (use when f_res is constant)
"""

import argparse
import json
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

# Import simulation database manager
sys.path.insert(0, str(Path(__file__).parents[4]))
from simulations_database.tools.simulation_db import SimulationDB

# Import base classes for building custom simulation classes
from kqcircuits.elements.bias_resonator import BiasResonator
from kqcircuits.simulations.port import InternalPort
from kqcircuits.simulations.single_element_simulation import get_single_element_sim_class
from kqcircuits.util.refpoints import WaveguideToSimPort


# Define simulation classes (adapted from bias_res_hfss_sim.py)

# Eigenmode simulation class
BaseSimClass_Eigenmode = get_single_element_sim_class(BiasResonator)

class BiasResEigenmodeSim(BaseSimClass_Eigenmode):
    """Custom simulation class for HFSS eigenmode analysis of bias resonator."""

    def build(self):
        # Call parent build to create geometry
        super().build()

        # Set up net assignment ports for eigenmode
        self.ports = []

        # Port on feedline coupling region
        try:
            signal_loc_feedline = self.refpoints['feedline_a']
        except KeyError:
            signal_loc_feedline = pya.DPoint(0, 0)

        # Port on inductor - use ACRL source point if available
        try:
            signal_loc_inductor = self.refpoints['acrl_source_main_inductor']
        except KeyError:
            try:
                signal_loc_inductor = self.refpoints['inductor_ground']
            except KeyError:
                # Fallback to a reasonable location
                signal_loc_inductor = pya.DPoint(self.l_coupling_length/2, self.ground_gap_bottom)

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


# Wave simulation class
BaseSimClass_Wave = get_single_element_sim_class(BiasResonator)

class BiasResWaveSim(BaseSimClass_Wave):
    """HFSS wave equation simulation for BiasResonator S-parameter measurement."""

    def build(self):
        """Build simulation and add waveguide ports to feedlines."""
        # Call parent build first
        super().build()

        # Get refpoints from the cell
        refp = self.get_refpoints(self.cell)

        # Add waveguide ports for feedline_a and feedline_b
        port_configs = [
            WaveguideToSimPort("port_feedline_a", use_internal_ports=False, side="left", a=self.a, b=self.b),
            WaveguideToSimPort("port_feedline_b", use_internal_ports=False, side="right", a=self.a, b=self.b),
        ]

        port_i = len(self.ports)  # Start numbering after existing ports

        for port_config in port_configs:
            # Get the towards refpoint (defaults to {refpoint}_corner)
            towards = port_config.towards
            if port_config.towards is None:
                towards = f"{port_config.refpoint}_corner"

            # Create waveguide to port
            self.produce_waveguide_to_port(
                refp[port_config.refpoint],
                refp[towards],
                (port_i := port_i + 1),
                side=port_config.side,
                a=port_config.a if port_config.a is not None else self.a,
                b=port_config.b if port_config.b is not None else self.b,
                term1=port_config.term1,
                turn_radius=port_config.turn_radius if port_config.turn_radius is not None else self.r,
                use_internal_ports=port_config.use_internal_ports if port_config.use_internal_ports is not None else self.use_internal_ports,
                waveguide_length=port_config.waveguide_length,
                face=port_config.face,
                airbridge=port_config.airbridge,
                deembed_cross_section=port_config.deembed_cross_section,
            )


# Parse command-line arguments
parser = argparse.ArgumentParser(
    description="Eigenmode + Wave simulation workflow for BiasResonator with automatic mesh import"
)
parser.add_argument(
    "--no-gui",
    action="store_true",
    help="Don't open KLayout to view results"
)
parser.add_argument(
    "--sweep-width",
    type=float,
    default=1.0,
    help="Frequency sweep width around eigenfrequency in GHz (default: 1.0)"
)
parser.add_argument(
    "--eigenmode-mode",
    type=str,
    default="each",
    choices=["each", "shared"],
    help="Eigenmode strategy: 'each' = eigenmode+wave for each sweep point, "
         "'shared' = one eigenmode for all wave sims (default: each)"
)
args = parser.parse_args()

# Prepare output directory
dir_path = create_or_empty_tmp_directory(Path(__file__).stem + "_output")

# Get layout
logging.basicConfig(level=logging.WARN, stream=sys.stdout)
layout = get_active_or_new_layout()

# ===========================
# Eigenmode Simulation Setup
# ===========================

eigenmode_sim_parameters = {
    "name": "bias_res_eigenmode",
    "use_internal_ports": True,
    "use_ports": True,
    "box": pya.DBox(pya.DPoint(-1000, -4600), pya.DPoint(2000, 500)),
    "face_stack": ["1t1"],

    # BiasResonator geometry parameters
    "include_inductor": True,
    "include_capacitor": True,
    "enable_mesh_layers": True,
    "a": 4.6,
    "b": 10,
    "n": 24,
}

eigenmode_solution_parameters = {
    "ansys_tool": "eigenmode",
    "n_modes": 1,
    "min_frequency": 1,
    "max_delta_f": 0.3,
    "maximum_passes": 10,
    "minimum_converged_passes": 2,
    "mesh_size": {
        "1t1_mesh_2": 8,  # Coarse mesh for inductor
        "1t1_mesh_3": 4,  # Fine mesh for capacitor
    },
}

eigenmode_export_parameters = {
    "path": dir_path,
    "post_process": PostProcess("produce_epr_table.py"),
    "exit_after_run": True,
}

# ===========================
# Wave Simulation Setup
# ===========================

wave_sim_parameters = {
    "name": "bias_res_wave",
    "use_internal_ports": False,  # Edge ports for S-parameters
    "use_ports": True,
    "box": pya.DBox(pya.DPoint(-3400, -4600), pya.DPoint(4400, 500)),  # Large box for waveguides
    "face_stack": ["1t1"],

    # Same BiasResonator geometry
    "include_inductor": True,
    "include_capacitor": True,
    "enable_mesh_layers": True,
    "a": 4.6,
    "b": 10,
    "n": 24,

    # Feedline parameters
    "feedline_cutout_bool": False,
}

wave_solution_parameters = {
    "ansys_tool": "hfss",  # Wave equation (default HFSS mode)
    "frequency": [6],  # Initial guess - will be updated by batch script
    "max_delta_s": 0.01,
    "sweep_start": 5.75,  # Placeholder - updated by eigenmode result
    "sweep_end": 6.25,    # Placeholder - updated by eigenmode result
    "sweep_count": 5001,  # High resolution: ~0.1 MHz per point for accurate Q measurement
    "sweep_type": "interpolating",
    "maximum_passes": 10,
    "minimum_converged_passes": 1,
    "mesh_size": {
        "1t1_mesh_2": 8,   # Inductor (coarse)
        "1t1_mesh_3": 6,   # Capacitor (fine)
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

# Define parameter sweep (example - modify as needed)
sweep_params = {
    # Example sweeps - uncomment/modify as needed:
    "l_coupling_length": [60],  # Coupling strength (shared mode OK)
    "l_coupling_distance": [64, 128, 256],  # Coupling strength (shared mode OK)
    # "l_length": [3500, 4000, 4250, 4500, 5000],  # Resonator length (use each mode)
}

# ===========================
# Generate Simulations
# ===========================

print("\n" + "="*70)
print("Eigenmode + Wave Simulation Workflow (BiasResonator)")
print("="*70)
print(f"Mode: {args.eigenmode_mode}")
print(f"Sweep width: +/- {args.sweep_width/2} GHz around eigenfrequency")
print("="*70 + "\n")

# Create eigenmode simulations based on mode
if args.eigenmode_mode == "each":
    # Mode 1: Eigenmode for EACH sweep point
    eigenmode_sims = cross_sweep_simulation(
        layout, BiasResEigenmodeSim, eigenmode_sim_parameters, sweep_params
    )
    print(f"Creating {len(eigenmode_sims)} eigenmode simulations (one per sweep point)")
elif args.eigenmode_mode == "shared":
    # Mode 2: Single eigenmode simulation (no sweep)
    eigenmode_sims = cross_sweep_simulation(
        layout, BiasResEigenmodeSim, eigenmode_sim_parameters, {}  # No sweep
    )
    print(f"Creating 1 shared eigenmode simulation (used for all sweep points)")

# Create wave simulations (always sweep)
wave_sims = cross_sweep_simulation(
    layout, BiasResWaveSim, wave_sim_parameters, sweep_params
)
print(f"Creating {len(wave_sims)} wave simulations")

# ===========================
# Register with Database
# ===========================

db = SimulationDB()
db_folders = db.register_simulations(
    simulations=eigenmode_sims + wave_sims,
    design_name='bias_resonator',
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
# Create Custom Batch File
# ===========================

print("\nCreating custom batch file...")

bat_file = dir_path / "simulation.bat"
custom_script = Path(__file__).parent / "ansys" / "eigenmode_wave_batch.py"

with open(bat_file, 'w') as f:
    f.write('@echo off\n')
    f.write('title Eigenmode + Wave Simulations (BiasResonator)\n')
    f.write('\n')

    if args.eigenmode_mode == "each":
        # Mode 1: Pair each eigenmode with corresponding wave simulation
        f.write(f'echo Running {len(wave_sims)} eigenmode + wave simulation pairs...\n')
        f.write('echo Mode: Eigenmode for EACH sweep point\n')
        f.write(f'echo Sweep width: +/- {args.sweep_width/2} GHz around eigenfrequency\n')
        f.write('echo.\n\n')

        for i, (eigen_json, wave_json) in enumerate(zip(eigenmode_json_files, wave_json_files)):
            arg = f"{eigen_json};{wave_json};{args.sweep_width}"
            f.write(f'echo Simulation {i+1}/{len(wave_sims)}\n')
            f.write(f'"{ANSYS_EXECUTABLE}" ')
            f.write(f'-scriptargs "{arg}" -RunScript "{custom_script}"\n')
            f.write('echo.\n')

    elif args.eigenmode_mode == "shared":
        # Mode 2: Use single eigenmode for all wave simulations
        f.write(f'echo Running 1 eigenmode + {len(wave_sims)} wave simulations...\n')
        f.write('echo Mode: SHARED eigenmode for all sweep points\n')
        f.write(f'echo Sweep width: +/- {args.sweep_width/2} GHz around eigenfrequency\n')
        f.write('echo.\n\n')

        shared_eigenmode_json = eigenmode_json_files[0]  # Single eigenmode
        for i, wave_json in enumerate(wave_json_files):
            arg = f"{shared_eigenmode_json};{wave_json};{args.sweep_width}"
            f.write(f'echo Simulation {i+1}/{len(wave_sims)}\n')
            f.write(f'"{ANSYS_EXECUTABLE}" ')
            f.write(f'-scriptargs "{arg}" -RunScript "{custom_script}"\n')
            f.write('echo.\n')

    f.write('\n')
    f.write('echo ========================================\n')
    f.write('echo All ANSYS simulations complete!\n')
    f.write('echo ========================================\n')
    f.write('echo.\n')
    f.write('echo Starting automated post-processing...\n')
    f.write('echo.\n\n')

    # Add post-processing: Copy .s2p files and run analysis
    f.write('REM ========================================\n')
    f.write('REM Copy S-parameter files to database\n')
    f.write('REM ========================================\n')

    # Get database sweep folder from db_folders
    if isinstance(db_folders, dict) and db_folders:
        first_sim_folder = list(db_folders.values())[0]
        if hasattr(first_sim_folder, 'parent'):
            sweep_folder = first_sim_folder.parent
        else:
            sweep_folder = Path(first_sim_folder).parent
    elif db_folders:
        sweep_folder = Path(str(db_folders)).parent if hasattr(db_folders, 'parent') else Path(str(db_folders))
    else:
        sweep_folder = None

    if sweep_folder:
        # Copy each .s2p file to its database location
        for i, wave_sim in enumerate(wave_sims):
            wave_name = wave_sim.name
            # In "each" mode: one eigenmode per wave sim
            # In "shared" mode: one eigenmode for all wave sims
            if args.eigenmode_mode == "each":
                eigen_name = eigenmode_sims[i].name
            else:  # "shared" mode
                eigen_name = eigenmode_sims[0].name

            # Source file follows pattern: bias_res_eigenmode_XXX_and_bias_res_wave_XXX_SMatrix.s2p
            src_file = f"{dir_path}\\{eigen_name}_and_{wave_name}_SMatrix.s2p"
            dst_folder = f"{sweep_folder}\\{wave_name}\\results"
            dst_file = f"{dst_folder}\\{wave_name}.s2p"

            f.write(f'echo Copying {wave_name}.s2p to database...\n')
            f.write(f'copy "{src_file}" "{dst_file}" >nul 2>&1\n')
            f.write('if %ERRORLEVEL% EQU 0 (\n')
            f.write(f'    echo   [OK] {wave_name}.s2p\n')
            f.write(') else (\n')
            f.write(f'    echo   [SKIP] {wave_name}.s2p not found (simulation may have failed)\n')
            f.write(')\n')

        f.write('echo.\n\n')

        # Run finalize_and_fit.py
        python_exe = sys.executable
        finalize_script = Path(__file__).parents[4] / "simulations_database" / "tools" / "finalize_and_fit.py"

        f.write('REM ========================================\n')
        f.write('REM Run S-parameter analysis and plotting\n')
        f.write('REM ========================================\n')
        f.write(f'echo Running finalize_and_fit.py on {sweep_folder}...\n')
        f.write('echo.\n')
        f.write(f'"{python_exe}" "{finalize_script}" "{sweep_folder}"\n')
        f.write('if %ERRORLEVEL% EQU 0 (\n')
        f.write('    echo.\n')
        f.write('    echo ========================================\n')
        f.write('    echo SUCCESS! All results processed.\n')
        f.write('    echo ========================================\n')
        f.write('    echo Plots saved to database folder:\n')
        f.write(f'    echo {sweep_folder}\n')
        f.write('    echo.\n')
        f.write(') else (\n')
        f.write('    echo.\n')
        f.write('    echo WARNING: Post-processing had errors.\n')
        f.write('    echo Check output above for details.\n')
        f.write('    echo.\n')
        f.write(')\n')
    else:
        f.write('echo WARNING: Could not determine database folder for post-processing\n')
        f.write('echo You can manually run: finalize_and_fit.py on the database folder\n')

    f.write('\ntimeout /t 30\n')

print(f"Created batch file: {bat_file}")

# ===========================
# Export OAS for Visualization
# ===========================

oas_file = export_simulation_oas(eigenmode_sims + wave_sims, dir_path)

# ===========================
# Summary
# ===========================

print(f"\n{'='*70}")
print(f"EXPORT COMPLETE")
print(f"{'='*70}")
print(f"Output directory: {dir_path}")
print(f"")
print(f"Eigenmode simulations: {len(eigenmode_sims)}")
print(f"Wave simulations: {len(wave_sims)}")
print(f"")
print(f"Workflow:")
print(f"  1. Run eigenmode -> extract resonance frequency")
print(f"  2. Configure wave sweep: f_res +/- {args.sweep_width/2} GHz")
print(f"  3. Import mesh from eigenmode into wave setup")
print(f"  4. Run wave simulation -> measure S21")
print(f"")
print(f"Next step:")
print(f"  cd {dir_path}")
print(f"  simulation.bat")
print(f"{'='*70}\n")

# Optionally open in KLayout
if not args.no_gui:
    open_with_klayout_or_default_application(oas_file)
else:
    print("Skipping KLayout GUI (--no-gui flag set)")
