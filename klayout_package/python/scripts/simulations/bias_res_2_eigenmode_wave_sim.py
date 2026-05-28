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


"""Eigenmode + Wave S21 Simulation for BiasResonator2

Uses the shared eigenmode_wave_workflow module for the simulation infrastructure.
"""

from kqcircuits.pya_resolver import pya
from kqcircuits.elements.bias_resonator_2 import BiasResonator2
from kqcircuits.simulations.eigenmode_wave_workflow import (
    create_eigenmode_sim_class,
    create_wave_sim_class,
    run_eigenmode_wave_workflow,
)


# Create simulation classes using the standard port configurations
EigenmodeSim = create_eigenmode_sim_class(BiasResonator2)
WaveSim = create_wave_sim_class(BiasResonator2)


# ===========================
# Simulation Parameters
# ===========================

eigenmode_sim_params = {
    "name": "bias_res_2_eigenmode",
    "use_internal_ports": True,
    "use_ports": True,
    "box": pya.DBox(pya.DPoint(-3000, -2500), pya.DPoint(1000, 500)),
    "face_stack": ["1t1"],

    # BiasResonator2 geometry parameters
    "include_inductor": True,
    "enable_mesh_layers": True,
    "a": 10,
    "b": 6,
    "n": 24,
}

eigenmode_solution_params = {
    "ansys_tool": "eigenmode",
    "n_modes": 1,
    "min_frequency": 1,
    "max_delta_f": 1,
    "maximum_passes": 10,
    "minimum_converged_passes": 2,
    "mesh_size": {
        "1t1_mesh_1": 4,  # Fine mesh for capacitor gaps
        "1t1_mesh_2": 8,  # Coarse mesh for inductor
    },
}

wave_sim_params = {
    "name": "bias_res_2_wave",
    "use_internal_ports": False,  # Edge ports for S-parameters
    "use_ports": True,
    "box": pya.DBox(pya.DPoint(-2500, -2500), pya.DPoint(1500, 500)),
    "face_stack": ["1t1"],

    # Same BiasResonator2 geometry
    "include_inductor": True,
    "enable_mesh_layers": True,
    "a": 10,
    "b": 6,
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
        "1t1_mesh_1": 4,
        "1t1_mesh_2": 8,
    },
}

# Parameter sweep
sweep_params = {
    "l_coupling_distance": [20], 
    "l_coupling_length": [300],
    "l_tot_length": [4725, 4500, 4300]
}


# ===========================
# Run Workflow
# ===========================

if __name__ == "__main__":
    run_eigenmode_wave_workflow(
        element_class=BiasResonator2,
        eigenmode_sim_class=EigenmodeSim,
        wave_sim_class=WaveSim,
        eigenmode_sim_params=eigenmode_sim_params,
        eigenmode_solution_params=eigenmode_solution_params,
        wave_sim_params=wave_sim_params,
        wave_solution_params=wave_solution_params,
        sweep_params=sweep_params,
        design_name="bias_resonator_2",
        script_name="bias_res_2",
    )
