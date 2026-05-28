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


"""Eigenmode + Wave S21 Simulation for DoubleResonator2

Uses the shared eigenmode_wave_workflow module for the simulation infrastructure.
"""

from kqcircuits.pya_resolver import pya
from kqcircuits.elements.double_res_2 import DoubleRes2
from kqcircuits.simulations.port import InternalPort
from kqcircuits.simulations.eigenmode_wave_workflow import (
    create_eigenmode_sim_class,
    create_wave_sim_class,
    run_eigenmode_wave_workflow,
)


# ===========================
# Feedline Termination for Eigenmode
# ===========================

def add_feedline_termination(sim):
    """Add 50-ohm lumped loads at both feedline ends for eigenmode simulation.

    This matches the loading condition in the wave simulation where each feedline
    end sees a 50-ohm port, so the resonator coupling shift is the same in both.
    Requires feedline_cutout_bool=True and enable_feedline_termination=True.
    """
    for side, signal_key, ground_key in [
        ("a", "main_inductor_feedline_a_signal", "main_inductor_feedline_a_ground"),
        ("b", "main_inductor_feedline_b_signal", "main_inductor_feedline_b_ground"),
    ]:
        try:
            signal_loc = sim.refpoints[signal_key]
            ground_loc = sim.refpoints[ground_key]
        except KeyError as e:
            print(f"Warning: Could not find feedline termination refpoint: {e}")
            continue

        port_num = len(sim.ports) + 1
        sim.ports.append(
            InternalPort(
                number=port_num,
                signal_location=signal_loc,
                ground_location=ground_loc,
                resistance=50.0,
                inductance=0,
                capacitance=0,
                lumped_element=True,
                rlc_type="series",
            )
        )


# Create simulation classes
EigenmodeSim = create_eigenmode_sim_class(DoubleRes2, extra_port_setup=add_feedline_termination)
WaveSim = create_wave_sim_class(DoubleRes2)


# ===========================
# Simulation Parameters
# ===========================

eigenmode_sim_params = {
    "name": "double_res_2_eigenmode",
    "use_internal_ports": True,
    "use_ports": True,
    "box": pya.DBox(pya.DPoint(-1000, -1500), pya.DPoint(1000, 500)),
    "face_stack": ["1t1"],

    # DoubleResonator2 geometry parameters
    #"include_inductor": True,
    "enable_mesh_layers": True,
    #"a": 10,
    #"b": 6,
    "n": 24,

    # Feedline termination: cut the feedline ends and add 50-ohm loads
    # so the resonator loading matches the wave simulation
    "feedline_cutout_bool": True,
    "enable_feedline_termination": True,
}

eigenmode_solution_params = {
    "ansys_tool": "eigenmode",
    "n_modes": 1,
    "min_frequency": 1,
    "max_delta_f": 1,
    "maximum_passes": 10,
    "minimum_converged_passes": 2,
    "mesh_size": {
        "1t1_mesh_1": 12,  # Fine mesh for capacitor gaps
    },
}

wave_sim_params = {
    "name": "double_res_2_wave",
    "use_internal_ports": False,  # Edge ports for S-parameters
    "use_ports": True,
    "box": pya.DBox(pya.DPoint(-1000, -1500), pya.DPoint(1000, 500)),
    "face_stack": ["1t1"],

    # Same DoubleResonator2 geometry
    #"include_inductor": True,
    "enable_mesh_layers": True,
    #"a": 10,
    #"b": 6,
    "n": 24,

    # Feedline parameters
    "feedline_cutout_bool": False,
}

wave_solution_params = {
    "ansys_tool": "hfss",
    "frequency": 6,  # Use single value, not list, so MaxDeltaS is properly set
    "max_delta_s": 0.05,
    "sweep_start": 5.75,
    "sweep_end": 6.25,
    "sweep_count": 5001,
    "sweep_type": "interpolating",
    "maximum_passes": 10,
    "minimum_converged_passes": 1,
    "mesh_size": {
        "1t1_mesh_1": 3,
    },
}

# Parameter sweep
sweep_params = {
    "l_coupling_distance": [5], 
    "l_coupling_length": [700, 400],
    "l_tot_length": [7700]
}


# ===========================
# Run Workflow
# ===========================

# Wave sim center = eigenfrequency * FREQUENCY_OFFSET_FACTOR
# Use 1.0 to sweep centered on the eigenfrequency, or e.g. 1.1 for 10% higher
FREQUENCY_OFFSET_FACTOR = 0.9

if __name__ == "__main__":
    run_eigenmode_wave_workflow(
        element_class=DoubleRes2,
        eigenmode_sim_class=EigenmodeSim,
        wave_sim_class=WaveSim,
        eigenmode_sim_params=eigenmode_sim_params,
        eigenmode_solution_params=eigenmode_solution_params,
        wave_sim_params=wave_sim_params,
        wave_solution_params=wave_solution_params,
        sweep_params=sweep_params,
        design_name="double_resonator_2",
        script_name="double_res_2",
        frequency_offset_factor=FREQUENCY_OFFSET_FACTOR,
    )
