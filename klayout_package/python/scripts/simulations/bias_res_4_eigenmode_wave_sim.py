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


"""Eigenmode + Wave S21 Simulation for BiasResonator4

Simulates the resonator with a configurable impedance load at the grounding
capacitor termination, representing coupling to a lossy line.  The load
resistance is set by GC_TERMINATION_RESISTANCE below.
"""

from kqcircuits.pya_resolver import pya
from kqcircuits.elements.bias_res_4 import BiasResonator4
from kqcircuits.simulations.port import InternalPort
from kqcircuits.simulations.eigenmode_wave_workflow import (
    create_eigenmode_sim_class,
    create_wave_sim_class,
    run_eigenmode_wave_workflow,
)


# Resistance seen at the bottom of the grounding capacitor (ohms).
# Change this to simulate different coupling to the lossy line.
GC_TERMINATION_RESISTANCE = 50.0


# ===========================
# Port Setup Helpers
# ===========================

def add_feedline_termination(sim):
    """Add 50-ohm lumped loads at both feedline ends for eigenmode simulation.

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


def add_gc_termination(sim, resistance=GC_TERMINATION_RESISTANCE):
    """Add impedance load at the bottom of the grounding capacitor."""
    try:
        signal_loc = sim.refpoints["gc_termination_signal"]
        ground_loc = sim.refpoints["gc_termination_ground"]
    except KeyError as e:
        print(f"Warning: Could not find gc termination refpoint: {e}")
        return

    port_num = len(sim.ports) + 1
    sim.ports.append(
        InternalPort(
            number=port_num,
            signal_location=signal_loc,
            ground_location=ground_loc,
            resistance=resistance,
            inductance=0,
            capacitance=0,
            lumped_element=True,
            rlc_type="series",
        )
    )


def eigenmode_extra_setup(sim):
    add_feedline_termination(sim)
    add_gc_termination(sim)


def wave_extra_setup(sim):
    add_gc_termination(sim)


# ===========================
# Simulation Classes
# ===========================

EigenmodeSim = create_eigenmode_sim_class(BiasResonator4, extra_port_setup=eigenmode_extra_setup)
WaveSim = create_wave_sim_class(
    BiasResonator4,
    feedline_ports=["main_inductor_port_feedline_a", "main_inductor_port_feedline_b"],
    extra_port_setup=wave_extra_setup,
)


# ===========================
# Simulation Parameters
# ===========================

eigenmode_sim_params = {
    "name": "bias_res_4_eigenmode",
    "use_internal_ports": True,
    "use_ports": True,
    "box": pya.DBox(pya.DPoint(-1500, -4500), pya.DPoint(1500, 300)),
    "face_stack": ["1t1"],

    "enable_mesh_layers": True,
    "n": 24,
    "feedline_cutout_bool": True,
    "enable_feedline_termination": True,
    "enable_gc_termination": True,
}

eigenmode_solution_params = {
    "ansys_tool": "eigenmode",
    "n_modes": 1,
    "min_frequency": 1,
    "max_delta_f": 1,
    "maximum_passes": 10,
    "minimum_converged_passes": 2,
    "mesh_size": {
        "1t1_mesh_1": 12,
    },
}

wave_sim_params = {
    "name": "bias_res_4_wave",
    "use_internal_ports": False,
    "use_ports": True,
    "box": pya.DBox(pya.DPoint(-1100, -4500), pya.DPoint(1100, 200)),
    "face_stack": ["1t1"],

    "enable_mesh_layers": True,
    "n": 24,
    "feedline_cutout_bool": False,
    "enable_gc_termination": True,
}

wave_solution_params = {
    "ansys_tool": "hfss",
    "frequency": 6,
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

# Parameter sweep over element geometry
sweep_params = {
    "l_tot_length": [9000],
    "l_coupling_length": [200]
}


# ===========================
# Run Workflow
# ===========================

FREQUENCY_OFFSET_FACTOR = 0.9

if __name__ == "__main__":
    run_eigenmode_wave_workflow(
        element_class=BiasResonator4,
        eigenmode_sim_class=EigenmodeSim,
        wave_sim_class=WaveSim,
        eigenmode_sim_params=eigenmode_sim_params,
        eigenmode_solution_params=eigenmode_solution_params,
        wave_sim_params=wave_sim_params,
        wave_solution_params=wave_solution_params,
        sweep_params=sweep_params,
        design_name="bias_resonator_4",
        script_name="bias_res_4",
        frequency_offset_factor=FREQUENCY_OFFSET_FACTOR,
    )
