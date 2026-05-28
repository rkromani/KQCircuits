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
sys.path.insert(0, str(Path(__file__).parents[4]))
from simulations_database.tools.simulation_db import SimulationDB

from kqcircuits.elements.met_cpw import METCPW
from kqcircuits.simulations.post_process import PostProcess
from kqcircuits.simulations.single_element_simulation import get_single_element_sim_class
from kqcircuits.util.export_helper import (
    create_or_empty_tmp_directory,
    get_active_or_new_layout,
    open_with_klayout_or_default_application,
)
from kqcircuits.util.parameters import Param, pdt

# Parse command-line arguments
parser = argparse.ArgumentParser(description="Run zoomed HFSS eigenmode simulations on MET CPW junction region")
parser.add_argument("--no-gui", action="store_true",
                    help="Don't open KLayout to view results")
parser.add_argument("--sweep-override", type=str, default=None,
                    help="Override sweep parameters as JSON")
args = parser.parse_args()

# Prepare output directory
dir_path = create_or_empty_tmp_directory(Path(__file__).stem + "_output")

# Create custom simulation class
BaseSimClass = get_single_element_sim_class(METCPW)

class METCPWHfssSimZoomed(BaseSimClass):
    """Zoomed HFSS eigenmode simulation focused on junction region.

    This simulation creates a small box around the two junctions and adds a third
    RLC boundary condition to represent the CPW resonator that has been cut off.

    Models the 5-layer vertical stack:
    - Base Ta (infinitely thin sheet at z=0)
    - Bottom Al electrode (100 nm, z=0 to 0.1 µm)
    - Junction oxide AlOx (2 nm, z=0.1 to 0.102 µm)
    - Top Al electrode (100 nm, z=0.102 to 0.202 µm)
    - Airbridge flyover Ta (infinitely thin sheet at z=0.202 µm)

    Three RLC boundaries:
    1. Main junction: Vertical YZ plane with inductance only
    2. Coupler junction: Vertical YZ plane with inductance only
    3. CPW resonator: Horizontal XY plane with parallel L and C
    """

    # Junction parameters
    junction_bool = Param(pdt.TypeBoolean, "Enable junction modeling", True)
    junction_use_lumped = Param(pdt.TypeBoolean, "Use lumped RLC model for junction", True)
    junction_lumped_inductance = Param(pdt.TypeDouble, "Junction inductance", 16, unit="nH")

    # Coupler junction parameters
    coupler_bool = Param(pdt.TypeBoolean, "Enable coupler junction modeling", True)
    coupler_use_lumped = Param(pdt.TypeBoolean, "Use lumped RLC model for coupler junction", True)
    coupler_lumped_inductance = Param(pdt.TypeDouble, "Coupler junction inductance", 100, unit="nH")

    # CPW resonator equivalent parameters (NEW for zoomed simulation)
    cpw_resonator_bool = Param(pdt.TypeBoolean, "Enable CPW resonator RLC boundary", True)
    cpw_resonator_inductance = Param(pdt.TypeDouble, "CPW resonator effective inductance", 5.0, unit="nH")
    cpw_resonator_capacitance = Param(pdt.TypeDouble, "CPW resonator effective capacitance", 100.0, unit="fF")
    cpw_resonator_resistance = Param(pdt.TypeDouble, "CPW resonator resistance (losses)", 0.0, unit="Ω")

    # 3D junction stack export
    use_sis_junction_stack = Param(pdt.TypeBoolean, "Export 3D junction stack layers", True)
    sis_junction_thickness = Param(pdt.TypeNone, "SIS junction layer thicknesses (µm)", None)
    sis_junction_materials = Param(pdt.TypeNone, "SIS junction layer materials", None)

    def get_port_data(self):
        """Override to create vertical RLC boundary on AlOx junction faces.

        Creates vertical polygons on the YZ plane for both main and coupler junctions.
        The CPW resonator RLC boundary is created automatically from the lumped_rlc layer.
        """
        # Get parent port data
        port_data = super().get_port_data()

        # Only create vertical polygon if SIS junction stack is enabled
        if not self.use_sis_junction_stack:
            return port_data

        # Get z-levels
        z = self.face_z_levels()
        face_id = "1t1"
        base_z = z[face_id][0]  # Should be 0.0

        # Calculate AlOx layer z-positions from thickness parameters
        sis_thickness = self.sis_junction_thickness or {}
        bottom_al_thickness = sis_thickness.get('bottom_al', 0.1)
        alox_thickness = sis_thickness.get('alox', 0.002)

        z_alox_bottom = base_z + bottom_al_thickness      # Top of bottom Al
        z_alox_top = z_alox_bottom + alox_thickness       # Top of AlOx

        # Get junction refpoint coordinates for identification
        try:
            junction_signal_x = self.refpoints["junction_signal"].x
        except KeyError:
            junction_signal_x = None
        try:
            coupler_signal_x = self.refpoints["coupler_signal"].x
        except KeyError:
            coupler_signal_x = None

        # Process each port and create vertical polygons for junctions
        for p_data in port_data:
            if p_data.get("junction", False):
                # Get the signal location
                sig_loc = p_data.get("signal_location")
                if sig_loc is None:
                    continue

                # Check if this is near the main junction or coupler junction
                tol = 1  # 1 µm tolerance

                # Main junction
                if junction_signal_x and abs(sig_loc[0] - junction_signal_x) < tol:
                    signal_loc_2d = self.refpoints["junction_signal"]
                    ground_loc_2d = self.refpoints["junction_ground"]
                    junction_width = self.met_width

                # Coupler junction
                elif coupler_signal_x and abs(sig_loc[0] - coupler_signal_x) < tol:
                    signal_loc_2d = self.refpoints["coupler_signal"]
                    ground_loc_2d = self.refpoints["coupler_ground"]
                    junction_width = self.coupler_width
                else:
                    continue

                # Junction gap center X coordinate (constant for vertical YZ plane)
                junction_x = (signal_loc_2d.x + ground_loc_2d.x) / 2
                junction_y = signal_loc_2d.y  # Center Y coordinate

                # Junction width in Y direction
                half_width = junction_width / 2

                # Create vertical YZ plane polygon on AlOx side face
                p_data["polygon"] = [
                    [junction_x, junction_y - half_width, z_alox_bottom],  # Bottom-left
                    [junction_x, junction_y + half_width, z_alox_bottom],  # Bottom-right
                    [junction_x, junction_y + half_width, z_alox_top],     # Top-right
                    [junction_x, junction_y - half_width, z_alox_top],     # Top-left
                ]

                # Current line endpoints (vertical through AlOx)
                p_data["signal_location"] = [junction_x, junction_y, z_alox_top]
                p_data["ground_location"] = [junction_x, junction_y, z_alox_bottom]

                # Force InternalPort polygon creation (not lumped_rlc sheet)
                p_data["lumped_element"] = False
                p_data["type"] = "InternalPort"

        return port_data

SimClass = METCPWHfssSimZoomed

# Simulation parameters for zoomed HFSS eigenmode analysis
sim_parameters = {
    "name": "met_cpw_eigenmode_zoomed",
    "use_internal_ports": True,
    "use_ports": True,

    # Small zoomed-in simulation box around junction region
    # Calculated based on actual junction positions with 50 µm buffer
    # Junction positions from geometry: X~2505-2516, Y~-4266
    # Box: 100 µm buffer around junctions
    "box": pya.DBox(pya.DPoint(2400, -4370), pya.DPoint(2620, -4170)),

    # Face stack configuration
    "face_stack": ["1t1"],

    # Metal height for base Ta layer (infinitely thin sheet)
    "metal_height": 0.0,

    # Airbridge height - distance from bottom Ta to top Ta (200 nm for junction)
    "airbridge_height": 0.2,  # 200 nm vertical separation

    # Junction modeling parameters
    "junction_bool": True,
    "junction_use_lumped": True,
    "junction_lumped_inductance": 16,  # Junction inductance in nH

    # Coupler junction modeling parameters
    "coupler_bool": True,
    "coupler_use_lumped": True,
    "coupler_lumped_inductance": 100,  # Coupler junction inductance in nH

    # CPW resonator equivalent parameters (NEW for zoomed simulation)
    "cpw_resonator_bool": True,
    "cpw_resonator_inductance": 5.0,  # nH (effective L of full CPW)
    "cpw_resonator_capacitance": 100.0,  # fF (effective C of full CPW)
    "cpw_resonator_resistance": 0.0,  # Ω (losses)

    # MET CPW geometry parameters (same as full simulation)
    "feedline_length": 700,
    "cpw_length": 4800,  # Full resonator (will be cropped by box)
    "cpw_coupling_length": 250,
    "cpw_a": 10,
    "cpw_b": 4.5,
    "met_width": 1.25,
    "met_height": 1.25,
    "met_bridge_length": 10,
    "al_undercut": 1.5,

    # Enable CPW resonator stub for lumped boundary
    "use_cpw_resonator_stub": True,

    # Enable mesh layers for refinement
    "enable_mesh_layers": False,

    # Base metal addition layers
    "base_metal_addition_layers": ["base_metal_addition"],

    # ========== 3D Junction Stack Configuration ==========
    "use_sis_junction_stack": True,
    "sis_junction_thickness": {
        "bottom_al": 0.1,      # Bottom Al electrode (100 nm)
        "alox": 0.002,         # Junction oxide (2 nm AlOx)
        "top_al": 0.1,         # Top Al electrode (100 nm)
    },
    # ======================================================

    # Material definitions
    "material_dict": {
        "silicon": {
            "permittivity": 11.45,
        },
        "sapphire": {
            "permittivity": 9.8,
            "conductivity": 0,
            "dielectric_loss_tangent": 0.0001,
        },
        "aluminum": {
            "permittivity": 1.0,
            "conductivity": 3.77e7,  # S/m
        },
        "tantalum": {
            "permittivity": 1.0,
            "conductivity": 7.5e6,  # S/m
        },
    },
}

# HFSS eigenmode export parameters
export_parameters = {
    "path": dir_path,
    "ansys_tool": "eigenmode",
    "post_process": PostProcess("produce_epr_table.py"),  # EPR analysis
    "exit_after_run": False,

    # Eigenmode solver settings
    "n_modes": 2,  # Solve for 2 modes
    "min_frequency": 1,  # Minimum frequency in GHz
    "max_delta_f": 0.3,  # Convergence criterion: max frequency change (%)
    "maximum_passes": 25,
    "minimum_converged_passes": 2,

    # Mesh refinement for accurate junction capacitance
    "mesh_size": {
        "1t1_SIS_junction": 0.3,  # Fine mesh at bottom Al electrode
        "1t1_SIS_shadow": 0.1,  # Very fine mesh at junction oxide (2 nm!)
        "1t1_SIS_junction_2": 0.3,  # Fine mesh at top Al electrode
        "1t1_airbridge_flyover": 2,  # Coarser mesh on flyover
        "1t1_lumped_rlc": 0.2,  # Fine mesh on RLC boundary plane
        "1t1_base_metal_gap_wo_grid": 5,  # Base Ta layer (sheet)
    },
}

# Get layout
logging.basicConfig(level=logging.WARN, stream=sys.stdout)
layout = get_active_or_new_layout()

# Parameter sweeps
simulations = []

# Define sweep parameters
import json
sweep_params = {
    # CPW resonator equivalent parameters
    # Sweep these to match resonance frequency with full simulation
    "cpw_resonator_inductance": [5.0],  # nH
    #"cpw_resonator_capacitance": [100.0, 150.0, 200.0],  # fF

    # Junction parameter sweeps
    #"junction_lumped_inductance": [11.5, 16],  # nH
}

# Apply sweep overrides if provided via command line
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
    design_name='met_cpw_junction_zoomed',
    sim_parameters=sim_parameters,
    export_parameters=export_parameters,
    output_folder=dir_path
)

# Export ANSYS HFSS eigenmode files
export_ansys(simulations, **export_parameters)

# Write OAS file
oas_file = export_simulation_oas(simulations, dir_path)
print(f"Exported zoomed HFSS eigenmode simulation files to: {dir_path}")
print(f"OAS file: {oas_file}")
print(f"Number of simulations: {len(simulations)}")

# Print next steps
print(f"\n{'='*60}")
print(f"-> Next step:")
print(f"  Run ANSYS simulations: {dir_path}\\simulation.bat")
print(f"  (Results will be automatically saved to database)")
print(f"\n-> This is a zoomed-in simulation with:")
print(f"  - Small box: ~111 x 100 µm (vs. full 2500 x 4000 µm)")
print(f"  - 3 RLC boundaries: 2 junctions + 1 CPW resonator")
print(f"  - CPW resonator L={sim_parameters['cpw_resonator_inductance']} nH, C={sim_parameters['cpw_resonator_capacitance']} fF")
print(f"{'='*60}\n")

# Optionally open in KLayout
if not args.no_gui:
    open_with_klayout_or_default_application(oas_file)
else:
    print("Skipping KLayout GUI (--no-gui flag set)")
