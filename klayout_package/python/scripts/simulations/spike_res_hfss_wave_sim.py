"""HFSS wave equation simulation for ResonatorSpike S-parameter measurement.

This script creates a port-driven (wave equation) HFSS simulation to measure
feedline-to-resonator coupling via S-parameters. Complements the eigenmode
simulation by providing S-parameter measurements rather than resonance frequency extraction.
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

from kqcircuits.elements.resonator_spike import ResonatorSpike
from kqcircuits.simulations.post_process import PostProcess
from kqcircuits.simulations.single_element_simulation import get_single_element_sim_class
from kqcircuits.util.export_helper import (
    create_or_empty_tmp_directory,
    get_active_or_new_layout,
    open_with_klayout_or_default_application,
)
from kqcircuits.util.refpoints import WaveguideToSimPort


# Create custom simulation class with waveguide ports
BaseSimClass = get_single_element_sim_class(ResonatorSpike)


class SpikeResWaveSim(BaseSimClass):
    """HFSS wave equation simulation for ResonatorSpike S-parameter measurement.

    Extends the base simulation class to add waveguide ports for feedline_a and feedline_b.
    These ports are created as EdgePorts (use_internal_ports=False) for S-parameter measurement.
    """

    def build(self):
        """Build simulation and add waveguide ports to feedlines.

        Overrides the parent build() to add WaveguideToSimPort processing for
        the feedline_a and feedline_b ports created by ResonatorSpike.
        """
        # Call parent build first - this creates the element and processes its get_sim_ports()
        super().build()

        # Get refpoints from the cell
        refp = self.get_refpoints(self.cell)

        # Add waveguide ports for feedline_a and feedline_b
        # These refpoints are created by ResonatorSpike.add_port() calls
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


SimClass = SpikeResWaveSim


# Command-line argument parser
parser = argparse.ArgumentParser(
    description="HFSS wave equation simulation for ResonatorSpike S-parameters"
)
parser.add_argument("--no-gui", action="store_true", help="Don't open KLayout")
args = parser.parse_args()

dir_path = create_or_empty_tmp_directory(Path(__file__).stem + "_output")

# Simulation parameters
sim_parameters = {
    "name": "spike_res_wave",
    "use_internal_ports": False,  # Use EdgePorts
    "use_ports": True,

    # Simulation box - must contain resonator + waveguide extensions
    # Increased to accommodate longer l_coupling_length values (up to 400)
    # With l_coupling_length=400, geometry extends to ~(-1400, 2400)
    "box": pya.DBox(pya.DPoint(-1500, -4500), pya.DPoint(2500, 1500)),

    "face_stack": ["1t1"],

    # ResonatorSpike geometry
    #"feedline_length": 700,
    #"feedline_spacing": 10,
    "feedline_cutout_bool": False,  # Simple 2-port measurement

    # Inductor (full resonator)
    "include_inductor": True,
    #"l_height": 2000,
    #"l_coupling_length": 500,
    #"l_coupling_distance": 16,  # Controls coupling strength

    # No spikes/junction initially
    "spike_number": 0,
    "junction_bool": False,

    # Mesh layers
    "enable_mesh_layers": True,

    # CPW parameters
    "a": 4.6,  # Center conductor width
    "b": 10,   # Gap width
    "n": 24,
}

# Export parameters (HFSS Wave Equation)
export_parameters = {
    "path": dir_path,
    "ansys_tool": "hfss",  # Wave equation is default HFSS mode
    "exit_after_run": False,

    # S-parameter sweep (HIGH RESOLUTION for accurate Q measurement)
    "frequency": [6.5],       # Adaptive solve frequencies (GHz)
    "max_delta_s": 0.01,      # 1% S-parameter convergence
    "sweep_start": 5.5,         # Start frequency (GHz) - focused on resonance
    "sweep_end": 7.5,           # End frequency (GHz) - 1 GHz span
    "sweep_count": 5001,      # 0.2 MHz resolution (~13.5 points per linewidth)
    "sweep_type": "interpolating",

    # Alternative: Full range with high resolution (13.2x slower)
    # "sweep_start": 6,
    # "sweep_end": 11,
    # "sweep_count": 18519,  # 0.27 MHz resolution (10 points per linewidth)

    # Convergence
    "maximum_passes": 20,
    "minimum_converged_passes": 2,

    # Mesh refinement
    # Note: Only mesh_2 (inductor) and mesh_3 (capacitor) layers are present
    # Feedline gaps don't use mesh layers in ResonatorSpike
    "mesh_size": {
        "1t1_mesh_2": 8,   # Inductor (coarse)
        "1t1_mesh_3": 4,   # Capacitor (fine - critical for coupling)
    },

    "post_process": PostProcess("produce_s_matrix.py"),
}

# Parameter sweeps
sweep_params = {
    #"l_coupling_distance": [8, 12, 16, 20, 24],  # Coupling strength sweep
    "l_coupling_length": [100, 200, 400]
}

# Create simulations
layout = get_active_or_new_layout()
simulations = cross_sweep_simulation(
    layout,
    SimClass,
    sim_parameters,
    sweep_params,
)

# Database integration
db = SimulationDB()
db_folders = db.register_simulations(
    simulations=simulations,
    design_name='spike_resonator',
    sim_parameters=sim_parameters,
    export_parameters=export_parameters,
    output_folder=dir_path
)

# Export and visualization
logging.basicConfig(level=logging.WARN, stream=sys.stdout)

if not args.no_gui:
    open_with_klayout_or_default_application(export_simulation_oas(simulations, dir_path))
else:
    export_simulation_oas(simulations, dir_path)

export_ansys(simulations, **export_parameters)

# Modify simulation.bat to add automated post-processing after ANSYS completes
simulation_bat = dir_path / "simulation.bat"
if simulation_bat.exists():
    # Read existing batch file
    with open(simulation_bat, 'r') as f:
        bat_content = f.read()

    # Append post-processing commands at the end (before final pause/exit)
    python_exe = Path(sys.executable)
    finalize_script = Path(__file__).parents[4] / "simulations_database" / "tools" / "finalize_and_fit.py"

    post_process_commands = f'''
REM ========================================
REM Automated Post-Processing
REM ========================================
echo.
echo ANSYS simulations complete!
echo Starting automated post-processing...
echo.

"{python_exe}" "{finalize_script}" "{dir_path}"

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo WARNING: Post-processing failed! Check error messages above.
    echo You can manually run: python simulations_database/tools/finalize_and_fit.py "{dir_path}"
    echo.
) else (
    echo.
    echo ========================================
    echo SUCCESS! All results processed.
    echo ========================================
    echo Check database folder for:
    echo   - Individual S21 plots (full + zoomed)
    echo   - Sweep summary plots
    echo   - CSV summary file
    echo   - fit_results.json in each simulation folder
    echo.
)
'''

    # Insert before the final pause (if it exists)
    if 'pause' in bat_content.lower():
        # Insert before last pause
        parts = bat_content.rsplit('pause', 1)
        bat_content = parts[0] + post_process_commands + '\npause' + parts[1]
    else:
        # Just append at the end
        bat_content += '\n' + post_process_commands

    # Write modified batch file
    with open(simulation_bat, 'w') as f:
        f.write(bat_content)

# Save database folder reference for automated post-processing
db_reference_file = dir_path / "database_folders.json"

# db_folders can be a dict, list, or string depending on return format
if isinstance(db_folders, dict):
    # Dict values could be Path objects or strings
    first_val = list(db_folders.values())[0] if db_folders else None
    if first_val:
        sweep_folder = str(first_val.parent) if hasattr(first_val, 'parent') else str(Path(first_val).parent)
    else:
        sweep_folder = None
elif isinstance(db_folders, (list, tuple)):
    sweep_folder = str(db_folders[0]) if db_folders else None
else:
    sweep_folder = str(db_folders) if db_folders else None

with open(db_reference_file, 'w') as f:
    json.dump({
        'sweep_folder': sweep_folder,
        'tmp_folder': str(dir_path),
        'simulations': [sim.name for sim in simulations]
    }, f, indent=2)

print(f"\nExported {len(simulations)} simulations to {dir_path}")
print(f"Database folders: {db_folders}")
print(f"\n{'='*70}")
print(f"FULLY AUTOMATED WORKFLOW:")
print(f"{'='*70}")
print(f"Run ANSYS simulations with automatic post-processing:")
print(f"  cd {dir_path}")
print(f"  simulation.bat")
print(f"\nThis will:")
print(f"  1. Run all ANSYS HFSS simulations")
print(f"  2. Automatically copy .s2p files to database")
print(f"  3. Automatically fit hanger model to resonances")
print(f"  4. Generate all plots (full + zoomed S21, sweep summaries)")
print(f"  5. Create CSV summary file")
print(f"\nNo additional commands needed - everything is automatic!")
print(f"{'='*70}")
