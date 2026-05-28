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


"""Eigenmode + Wave S21 Simulation for DoubleRes

Uses the shared eigenmode_wave_workflow module for the simulation infrastructure.
Includes optional lumped RLC bias resistor support.
"""

from kqcircuits.pya_resolver import pya
from kqcircuits.elements.double_res import DoubleRes
from kqcircuits.simulations.port import InternalPort
from kqcircuits.simulations.eigenmode_wave_workflow import (
    create_eigenmode_sim_class,
    create_wave_sim_class,
    run_eigenmode_wave_workflow,
)


# ===========================
# Custom Port Setup for Bias Resistor
# ===========================

def add_bias_resistor_port_eigenmode(sim):
    """Add lumped RLC element for bias resistor in eigenmode simulation."""
    if getattr(sim, 'include_bias_resistor', False):
        try:
            signal_loc = sim.refpoints['resistor_signal']
            ground_loc = sim.refpoints['resistor_ground']
            resistance_value = 50.0

            sim.ports.append(
                InternalPort(
                    number=2,
                    signal_location=signal_loc,
                    ground_location=ground_loc,
                    resistance=resistance_value,
                    inductance=0,
                    capacitance=0,
                    lumped_element=True,
                    rlc_type="series",
                )
            )
        except KeyError as e:
            print(f"Warning: Could not find resistor refpoints: {e}")


def add_bias_resistor_port_wave(sim):
    """Add lumped RLC element for bias resistor in wave simulation."""
    if getattr(sim, 'include_bias_resistor', False):
        try:
            signal_loc = sim.refpoints['resistor_signal']
            ground_loc = sim.refpoints['resistor_ground']
            resistance_value = 50.0

            # Port number continues after waveguide ports (which are 1 and 2)
            port_num = len(sim.ports) + 1

            sim.ports.append(
                InternalPort(
                    number=port_num,
                    signal_location=signal_loc,
                    ground_location=ground_loc,
                    resistance=resistance_value,
                    inductance=0,
                    capacitance=0,
                    lumped_element=True,
                    rlc_type="series",
                )
            )
        except KeyError as e:
            print(f"Warning: Could not find resistor refpoints in wave sim: {e}")


# Create simulation classes with bias resistor support
EigenmodeSim = create_eigenmode_sim_class(DoubleRes, extra_port_setup=add_bias_resistor_port_eigenmode)
WaveSim = create_wave_sim_class(DoubleRes, extra_port_setup=add_bias_resistor_port_wave)


# ===========================
# Simulation Parameters
# ===========================

eigenmode_sim_params = {
    "name": "double_res_eigenmode",
    "use_internal_ports": True,
    "use_ports": True,
    "box": pya.DBox(pya.DPoint(-1000, -3000), pya.DPoint(1000, 500)),
    "face_stack": ["1t1"],

    # DoubleRes geometry parameters
    "include_inductor": True,
    "enable_mesh_layers": True,
    "a": 10,
    "b": 6,
    "n": 24,

    # Bias resistor
    "include_bias_resistor": True,
}

eigenmode_solution_params = {
    "ansys_tool": "eigenmode",
    "n_modes": 3,  # Solve for 3 modes to find highest Q when resistor is enabled
    "min_frequency": 1,
    "max_delta_f": 0.3,
    "maximum_passes": 10,
    "minimum_converged_passes": 2,
    "mesh_size": {
        "1t1_mesh_1": 4,  # Fine mesh for capacitor gaps
        "1t1_mesh_2": 8,  # Coarse mesh for inductor
    },
}

wave_sim_params = {
    "name": "double_res_wave",
    "use_internal_ports": False,  # Edge ports for S-parameters
    "use_ports": True,
    "box": pya.DBox(pya.DPoint(-3000, -3000), pya.DPoint(3000, 500)),
    "face_stack": ["1t1"],

    # Same DoubleRes geometry
    "include_inductor": True,
    "enable_mesh_layers": True,
    "a": 10,
    "b": 6,
    "n": 24,

    # Feedline parameters
    "feedline_cutout_bool": False,

    # Bias resistor - only in eigenmode (to select correct mode), not in wave sim
    "include_bias_resistor": False,
}

wave_solution_params = {
    "ansys_tool": "hfss",
    "frequency": 6,  # Use single value, not list, so MaxDeltaS is properly set
    "max_delta_s": 0.03,
    "sweep_start": 5.75,
    "sweep_end": 6.25,
    "sweep_count": 5001,
    "sweep_type": "interpolating",
    "maximum_passes": 10,
    "minimum_converged_passes": 1,
    "mesh_size": {
        "1t1_mesh_1": 4,
        "1t1_mesh_2": 8,
    },
}

# Parameter sweep
sweep_params = {
    "l_coupling_length": [80, 160, 320, 640],
    "l_coupling_distance": [10, 20],
    #"l_coupling_length": [160],
}


# ===========================
# Run Workflow
# ===========================

if __name__ == "__main__":
    run_eigenmode_wave_workflow(
        element_class=DoubleRes,
        eigenmode_sim_class=EigenmodeSim,
        wave_sim_class=WaveSim,
        eigenmode_sim_params=eigenmode_sim_params,
        eigenmode_solution_params=eigenmode_solution_params,
        wave_sim_params=wave_sim_params,
        wave_solution_params=wave_solution_params,
        sweep_params=sweep_params,
        design_name="double_resonator",
        script_name="double_res",
    )
