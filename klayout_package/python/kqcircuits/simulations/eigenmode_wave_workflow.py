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

"""Eigenmode + Wave S21 Simulation Workflow

This module provides a reusable workflow for running chained eigenmode + wave simulations:
1. Runs HFSS eigenmode simulation to extract resonance frequency
2. Uses eigenfrequency to configure wave equation S21 simulation sweep range
3. Runs wave simulation to measure S21 and extract coupling parameters

Usage:
    from kqcircuits.simulations.eigenmode_wave_workflow import (
        create_eigenmode_sim_class,
        create_wave_sim_class,
        run_eigenmode_wave_workflow,
    )

    # Create simulation classes
    EigenmodeSim = create_eigenmode_sim_class(MyElement)
    WaveSim = create_wave_sim_class(MyElement)

    # Run workflow
    run_eigenmode_wave_workflow(
        element_class=MyElement,
        eigenmode_sim_class=EigenmodeSim,
        wave_sim_class=WaveSim,
        eigenmode_params={...},
        wave_params={...},
        sweep_params={...},
    )
"""

import argparse
import logging
import os
import sys
from pathlib import Path

from kqcircuits.pya_resolver import pya
from kqcircuits.simulations.export.ansys.ansys_solution import get_ansys_solution
from kqcircuits.simulations.export.ansys.ansys_export import export_ansys_json
from kqcircuits.simulations.export.simulation_export import (
    cross_sweep_simulation,
    export_simulation_oas,
    copy_content_into_directory,
)
from kqcircuits.simulations.post_process import PostProcess
from kqcircuits.util.export_helper import (
    create_or_empty_tmp_directory,
    get_active_or_new_layout,
    open_with_klayout_or_default_application,
)
from kqcircuits.defaults import ANSYS_EXECUTABLE, ANSYS_SCRIPT_PATHS
from kqcircuits.simulations.port import InternalPort
from kqcircuits.simulations.single_element_simulation import get_single_element_sim_class
from kqcircuits.util.refpoints import WaveguideToSimPort


def create_eigenmode_sim_class(element_class, extra_port_setup=None):
    """Create an eigenmode simulation class for the given element.

    The eigenmode simulation uses internal ports for net assignment, placing ports
    on the feedline and inductor regions with the same port number to indicate
    they're the same electrical net.

    Args:
        element_class: The KQCircuits element class (e.g., BiasResonator2)
        extra_port_setup: Optional callable(self) for additional port setup (e.g., lumped RLC)

    Returns:
        A simulation class configured for eigenmode analysis
    """
    BaseSimClass = get_single_element_sim_class(element_class)

    class EigenmodeSim(BaseSimClass):
        """HFSS eigenmode simulation for resonance frequency extraction."""

        def build(self):
            super().build()

            # Set up net assignment ports for eigenmode
            self.ports = []

            # Port on feedline coupling region
            try:
                signal_loc_feedline = self.refpoints['port_feedline_a']
            except KeyError:
                try:
                    signal_loc_feedline = self.refpoints['feedline_a']
                except KeyError:
                    signal_loc_feedline = pya.DPoint(0, 0)

            # Port on inductor - use ACRL source point if available
            try:
                signal_loc_inductor = self.refpoints['acrl_source_main_inductor']
            except KeyError:
                # Fallback to ground_gap_top if available
                if hasattr(self, 'ground_gap_top'):
                    signal_loc_inductor = pya.DPoint(0, self.ground_gap_top)
                else:
                    signal_loc_inductor = pya.DPoint(0, -500)

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

            # Call extra port setup if provided
            if extra_port_setup is not None:
                extra_port_setup(self)

    return EigenmodeSim


def create_wave_sim_class(element_class, feedline_ports=None, extra_port_setup=None):
    """Create a wave simulation class for the given element.

    The wave simulation uses edge ports on the feedlines for S-parameter measurement.

    Args:
        element_class: The KQCircuits element class (e.g., BiasResonator2)
        feedline_ports: List of feedline port refpoint names, e.g., ["port_feedline_a", "port_feedline_b"]
                       Defaults to ["port_feedline_a", "port_feedline_b"]
        extra_port_setup: Optional callable(self) for additional port setup (e.g., lumped RLC)

    Returns:
        A simulation class configured for wave S-parameter analysis
    """
    if feedline_ports is None:
        feedline_ports = ["port_feedline_a", "port_feedline_b"]

    BaseSimClass = get_single_element_sim_class(element_class)

    class WaveSim(BaseSimClass):
        """HFSS wave equation simulation for S-parameter measurement."""

        def build(self):
            super().build()

            # Get refpoints from the cell
            refp = self.get_refpoints(self.cell)

            # Configure port sides based on port names
            port_configs = []
            for port_name in feedline_ports:
                # Determine side from port name
                if "_a" in port_name or "left" in port_name.lower():
                    side = "left"
                elif "_b" in port_name or "right" in port_name.lower():
                    side = "right"
                else:
                    side = None  # Let produce_waveguide_to_port figure it out

                port_configs.append(
                    WaveguideToSimPort(port_name, use_internal_ports=False, side=side, a=self.a, b=self.b)
                )

            port_i = len(self.ports)

            for port_config in port_configs:
                towards = port_config.towards
                if port_config.towards is None:
                    towards = f"{port_config.refpoint}_corner"

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

            # Call extra port setup if provided
            if extra_port_setup is not None:
                extra_port_setup(self)

    return WaveSim


def create_batch_file(
    bat_file_path,
    eigenmode_json_files,
    wave_json_files,
    eigenmode_sims,
    wave_sims,
    custom_script_path,
    output_dir,
    sweep_width,
    eigenmode_mode,
    db_sweep_folder=None,
    ansys_wait_time=10,
):
    """Create the Windows batch file to run ANSYS simulations.

    Args:
        bat_file_path: Path to write the batch file
        eigenmode_json_files: List of eigenmode JSON file paths
        wave_json_files: List of wave JSON file paths
        eigenmode_sims: List of eigenmode simulation objects
        wave_sims: List of wave simulation objects
        custom_script_path: Path to eigenmode_wave_batch.py
        output_dir: Output directory path
        sweep_width: Frequency sweep width in GHz
        eigenmode_mode: "each" or "shared"
        db_sweep_folder: Database sweep folder path (optional)
        ansys_wait_time: Seconds to wait after each ANSYS run (default 10)
    """
    with open(bat_file_path, 'w') as f:
        f.write('@echo off\n')
        f.write('title Eigenmode + Wave Simulations\n')
        f.write('\n')
        # Set environment variable to fix clipboard issues when copying designs between projects
        f.write('set ANS_USE_ISOLATED_CLIPBOARD=1\n')
        f.write('\n')

        if eigenmode_mode == "each":
            f.write(f'echo Running {len(wave_sims)} eigenmode + wave simulation pairs...\n')
            f.write('echo Mode: Eigenmode for EACH sweep point\n')
            f.write(f'echo Sweep width: +/- {sweep_width/2} GHz around eigenfrequency\n')
            f.write('echo.\n\n')

            for i, (eigen_json, wave_json) in enumerate(zip(eigenmode_json_files, wave_json_files)):
                arg = f"{eigen_json};{wave_json};{sweep_width}"
                # Log file is named after eigenmode simulation
                eigen_basename = os.path.splitext(os.path.basename(eigen_json))[0]
                log_file = f"{eigen_basename}_run.log"
                f.write(f'echo Simulation {i+1}/{len(wave_sims)}\n')
                f.write(f'"{ANSYS_EXECUTABLE}" ')
                f.write(f'-scriptargs "{arg}" -RunScript "{custom_script_path}"\n')
                f.write('echo Waiting for ANSYS to finish cleanup...\n')
                f.write(f'timeout /t {ansys_wait_time} /nobreak >nul\n')
                f.write('echo.\n')
                f.write('echo ======== ANSYS Output ========\n')
                f.write(f'type "{output_dir}\\\\{log_file}"\n')
                f.write('echo =============================\n')
                f.write('echo.\n')

        elif eigenmode_mode == "shared":
            f.write(f'echo Running 1 eigenmode + {len(wave_sims)} wave simulations...\n')
            f.write('echo Mode: SHARED eigenmode for all sweep points\n')
            f.write(f'echo Sweep width: +/- {sweep_width/2} GHz around eigenfrequency\n')
            f.write('echo.\n\n')

            shared_eigenmode_json = eigenmode_json_files[0]
            eigen_basename = os.path.splitext(os.path.basename(shared_eigenmode_json))[0]
            log_file = f"{eigen_basename}_run.log"
            for i, wave_json in enumerate(wave_json_files):
                arg = f"{shared_eigenmode_json};{wave_json};{sweep_width}"
                f.write(f'echo Simulation {i+1}/{len(wave_sims)}\n')
                f.write(f'"{ANSYS_EXECUTABLE}" ')
                f.write(f'-scriptargs "{arg}" -RunScript "{custom_script_path}"\n')
                f.write('echo Waiting for ANSYS to finish cleanup...\n')
                f.write(f'timeout /t {ansys_wait_time} /nobreak >nul\n')
                f.write('echo.\n')
                f.write('echo ======== ANSYS Output ========\n')
                f.write(f'type "{output_dir}\\\\{log_file}"\n')
                f.write('echo =============================\n')
                f.write('echo.\n')

        f.write('\n')
        f.write('echo ========================================\n')
        f.write('echo All ANSYS simulations complete!\n')
        f.write('echo ========================================\n')
        f.write('echo.\n')
        f.write('echo Starting automated post-processing...\n')
        f.write('echo.\n\n')

        # Post-processing: Copy .s2p files and run analysis
        f.write('REM ========================================\n')
        f.write('REM Copy S-parameter files to database\n')
        f.write('REM ========================================\n')

        if db_sweep_folder:
            for i, wave_sim in enumerate(wave_sims):
                wave_name = wave_sim.name
                if eigenmode_mode == "each":
                    eigen_name = eigenmode_sims[i].name
                else:
                    eigen_name = eigenmode_sims[0].name

                src_file = f"{output_dir}\\\\{eigen_name}_and_{wave_name}_SMatrix.s2p"
                dst_folder = f"{db_sweep_folder}\\\\{wave_name}\\\\results"
                dst_file = f"{dst_folder}\\\\{wave_name}.s2p"

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
            finalize_script = Path(__file__).parents[3] / "scripts" / "simulations" / "tools" / "finalize_and_fit.py"

            # Check if finalize_and_fit.py exists in the expected location, otherwise try alternative
            if not finalize_script.exists():
                finalize_script = Path(__file__).parents[4] / "simulations_database" / "tools" / "finalize_and_fit.py"

            if finalize_script.exists():
                f.write('REM ========================================\n')
                f.write('REM Run S-parameter analysis and plotting\n')
                f.write('REM ========================================\n')
                f.write('echo Running finalize_and_fit.py...\n')
                f.write('echo.\n')
                f.write(f'"{python_exe}" "{finalize_script}" "{output_dir}" --db-folder "{db_sweep_folder}"\n')
                f.write('if %ERRORLEVEL% EQU 0 (\n')
                f.write('    echo.\n')
                f.write('    echo ========================================\n')
                f.write('    echo SUCCESS! All results processed.\n')
                f.write('    echo ========================================\n')
                f.write('    echo Plots saved to database folder:\n')
                f.write(f'    echo {db_sweep_folder}\n')
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


def run_eigenmode_wave_workflow(
    element_class,
    eigenmode_sim_class,
    wave_sim_class,
    eigenmode_sim_params,
    eigenmode_solution_params,
    wave_sim_params,
    wave_solution_params,
    sweep_params,
    design_name,
    script_name=None,
    args=None,
):
    """Run the complete eigenmode + wave simulation workflow.

    Args:
        element_class: The KQCircuits element class
        eigenmode_sim_class: Eigenmode simulation class (from create_eigenmode_sim_class)
        wave_sim_class: Wave simulation class (from create_wave_sim_class)
        eigenmode_sim_params: Dict of eigenmode simulation parameters
        eigenmode_solution_params: Dict of eigenmode solution/solver parameters
        wave_sim_params: Dict of wave simulation parameters
        wave_solution_params: Dict of wave solution/solver parameters
        sweep_params: Dict of parameter sweeps
        design_name: Name for database registration
        script_name: Optional script name for output directory (defaults to design_name)
        args: Optional pre-parsed arguments. If None, will parse from command line.

    Returns:
        Path to output directory
    """
    # Parse command-line arguments if not provided
    if args is None:
        parser = argparse.ArgumentParser(
            description="Eigenmode + Wave simulation workflow with automatic mesh import"
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
    if script_name is None:
        script_name = design_name
    dir_path = create_or_empty_tmp_directory(f"{script_name}_eigenmode_wave_sim_output")

    # Copy ANSYS scripts to output directory
    copy_content_into_directory(ANSYS_SCRIPT_PATHS, dir_path, "scripts")

    # Get layout
    logging.basicConfig(level=logging.WARN, stream=sys.stdout)
    layout = get_active_or_new_layout()

    # Print header
    print("\n" + "="*70)
    print(f"Eigenmode + Wave Simulation Workflow ({element_class.__name__})")
    print("="*70)
    print(f"Mode: {args.eigenmode_mode}")
    print(f"Sweep width: +/- {args.sweep_width/2} GHz around eigenfrequency")
    print("="*70 + "\n")

    # Create eigenmode simulations based on mode
    if args.eigenmode_mode == "each":
        eigenmode_sims = cross_sweep_simulation(
            layout, eigenmode_sim_class, eigenmode_sim_params, sweep_params
        )
        print(f"Creating {len(eigenmode_sims)} eigenmode simulations (one per sweep point)")
    elif args.eigenmode_mode == "shared":
        eigenmode_sims = cross_sweep_simulation(
            layout, eigenmode_sim_class, eigenmode_sim_params, {}  # No sweep
        )
        print(f"Creating 1 shared eigenmode simulation (used for all sweep points)")

    # Create wave simulations (always sweep)
    wave_sims = cross_sweep_simulation(
        layout, wave_sim_class, wave_sim_params, sweep_params
    )
    print(f"Creating {len(wave_sims)} wave simulations")

    # Register with database
    db_folders = None
    try:
        # Import here to avoid hard dependency
        sys.path.insert(0, str(Path(__file__).parents[4]))
        from simulations_database.tools.simulation_db import SimulationDB

        db = SimulationDB()
        db_folders = db.register_simulations(
            simulations=eigenmode_sims + wave_sims,
            design_name=design_name,
            sim_parameters={**eigenmode_sim_params, **wave_sim_params},
            export_parameters={**eigenmode_solution_params, **wave_solution_params},
            output_folder=dir_path
        )
    except ImportError:
        print("Note: SimulationDB not available, skipping database registration")
    except Exception as e:
        print(f"Warning: Database registration failed: {e}")

    # Export JSON files
    print("\nExporting simulation files...")

    eigenmode_export_params = {
        "path": dir_path,
        "post_process": PostProcess("produce_epr_table.py"),
    }

    wave_export_params = {
        "path": dir_path,
        "post_process": PostProcess("produce_s_matrix.py"),
    }

    eigenmode_json_files = []
    for sim in eigenmode_sims:
        solution = get_ansys_solution(**eigenmode_solution_params)
        json_path = export_ansys_json(sim, solution, dir_path)
        eigenmode_json_files.append(json_path)

    wave_json_files = []
    for sim in wave_sims:
        solution = get_ansys_solution(**wave_solution_params)
        json_path = export_ansys_json(sim, solution, dir_path)
        wave_json_files.append(json_path)

    print(f"Exported {len(eigenmode_json_files)} eigenmode JSON files")
    print(f"Exported {len(wave_json_files)} wave JSON files")

    # Create batch file
    print("\nCreating custom batch file...")

    bat_file = dir_path / "simulation.bat"
    custom_script = Path(__file__).parent.parent / "scripts" / "simulations" / "ansys" / "eigenmode_wave_batch.py"

    # Alternative path if the above doesn't exist
    if not custom_script.exists():
        custom_script = dir_path / "scripts" / "eigenmode_wave_batch.py"

    # Get database sweep folder
    sweep_folder = None
    if isinstance(db_folders, dict) and db_folders:
        first_sim_folder = list(db_folders.values())[0]
        if hasattr(first_sim_folder, 'parent'):
            sweep_folder = first_sim_folder.parent
        else:
            sweep_folder = Path(first_sim_folder).parent
    elif db_folders:
        sweep_folder = Path(str(db_folders)).parent if hasattr(db_folders, 'parent') else Path(str(db_folders))

    create_batch_file(
        bat_file_path=bat_file,
        eigenmode_json_files=eigenmode_json_files,
        wave_json_files=wave_json_files,
        eigenmode_sims=eigenmode_sims,
        wave_sims=wave_sims,
        custom_script_path=custom_script,
        output_dir=dir_path,
        sweep_width=args.sweep_width,
        eigenmode_mode=args.eigenmode_mode,
        db_sweep_folder=sweep_folder,
    )

    print(f"Created batch file: {bat_file}")

    # Export OAS for visualization
    oas_file = export_simulation_oas(eigenmode_sims + wave_sims, dir_path)

    # Summary
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

    return dir_path
