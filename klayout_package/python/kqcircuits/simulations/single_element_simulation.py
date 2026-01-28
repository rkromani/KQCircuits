# This code is part of KQCircuits
# Copyright (C) 2023 IQM Finland Oy
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

from typing import Callable
from kqcircuits.elements.element import Element
from kqcircuits.junctions import junction_type_choices
from kqcircuits.simulations.simulation import Simulation
from kqcircuits.pya_resolver import pya
from kqcircuits.simulations.partition_region import PartitionRegion
from kqcircuits.simulations.port import InternalPort, EdgePort
from kqcircuits.util.parameters import Param, pdt, add_parameters_from
from kqcircuits.util.refpoints import RefpointToInternalPort, RefpointToEdgePort, WaveguideToSimPort, JunctionSimPort


def _get_build_function(
    element_class, ignore_ports, transformation_from_center, sim_junction_type, deembed_cross_sections
):
    def _build_for_element_class(self):
        if sim_junction_type not in junction_type_choices:
            raise ValueError(
                f"Unknown sim_junction_type {sim_junction_type}. "
                f"Junction type should be listed in junction_type_choices"
            )

        simulation_cell = self.add_element(
            element_class, **{**self.get_parameters(), "junction_type": sim_junction_type, "fluxline_type": "none"}
        )

        element_trans = pya.DTrans(0, False, self.box.center())
        if transformation_from_center is not None:
            element_trans *= transformation_from_center(simulation_cell)
        _, refp = self.insert_cell(simulation_cell, element_trans, rec_levels=None)
        self.refpoints = refp

        if deembed_cross_sections is not None:
            deembed_cs_names = deembed_cross_sections.keys()
        else:
            deembed_cs_names = set()

        # Add ports
        port_i = 0
        for port in element_class.get_sim_ports(self):
            if ignore_ports is not None and port.refpoint in ignore_ports:
                continue

            if port.refpoint in deembed_cs_names:
                port.deembed_cross_section = deembed_cross_sections[port.refpoint]

            if isinstance(port, RefpointToInternalPort):
                self.ports.append(
                    InternalPort(
                        number=(port_i := port_i + 1),
                        signal_location=refp[port.refpoint],
                        ground_location=None if not port.ground_refpoint else refp[port.ground_refpoint],
                        resistance=port.resistance,
                        reactance=port.reactance,
                        inductance=port.inductance,
                        capacitance=port.capacitance,
                        face=port.face,
                        junction=port.junction,
                        lumped_element=port.lumped_element,
                        rlc_type=port.rlc_type,
                    )
                )
            elif isinstance(port, RefpointToEdgePort):
                self.ports.append(
                    EdgePort(
                        number=(port_i := port_i + 1),
                        signal_location=refp[port.refpoint],
                        resistance=port.resistance,
                        reactance=port.reactance,
                        inductance=port.inductance,
                        capacitance=port.capacitance,
                        deembed_len=port.deembed_len,
                        face=port.face,
                        junction=port.junction,
                        lumped_element=port.lumped_element,
                        rlc_type=port.rlc_type,
                        size=port.size,
                        deembed_cross_section=port.deembed_cross_section,
                    )
                )
            elif isinstance(port, WaveguideToSimPort):
                towards = port.towards
                if port.towards is None:
                    towards = f"{port.refpoint}_corner"
                self.produce_waveguide_to_port(
                    refp[port.refpoint],
                    refp[towards],
                    (port_i := port_i + 1),
                    side=port.side,
                    a=port.a,
                    b=port.b,
                    term1=port.term1,
                    turn_radius=port.turn_radius,
                    use_internal_ports=port.use_internal_ports,
                    waveguide_length=port.waveguide_length,
                    face=port.face,
                    airbridge=port.airbridge,
                    deembed_cross_section=port.deembed_cross_section,
                )

            elif isinstance(port, JunctionSimPort):
                self.ports.append(
                    InternalPort(
                        (port_i := port_i + 1),
                        *self.etched_line(refp[port.refpoint], refp[port.other_refpoint]),
                        face=port.face,
                        inductance=self.junction_inductance,
                        capacitance=self.junction_capacitance,
                        junction=True,
                        floating=port.floating,
                    )
                )

    return _build_for_element_class


def get_single_element_sim_class(
    element_class: Element,
    ignore_ports: list[str] | None = None,
    transformation_from_center: Callable[[pya.Cell], pya.DTrans] | None = None,
    partition_region_function: Callable[[Simulation], list[PartitionRegion]] | None = None,
    sim_junction_type: str = "Sim",
    deembed_cross_sections: dict[str] = None,
) -> type[Simulation]:
    """Formulates a simulation class containing a single cell of a given Element class

    Args:
        element_class: an Element class for which a simulation class is returned
        ignore_ports: If list of strings is given, simulation ports will not be created for the given
            refpoints in the simulation class.
        transformation_from_center: If None, simulated element is placed in the middle of simulation's box.
            Otherwise should be a function that takes an element cell as argument and returns a DTrans object.
            The returned transformation is applied to the element cell
            after placing it in the middle of simulation's box.
            The function should not cause any side-effects, i.e. change the cell parameters
        partition_region_function: optional. Function that the simulation instance will use to define
            partition regions, which may look up instances parameters and refpoints to derive the regions.
        deembed_cross_sections: optional dictionary for cross-section simulation that can be used for deembeding.
            The naming convention in the dictionary is `deembed_cross_sections[port_refpoint]=cross_section_name`,
            where `cross_section_name` is the name given to the correction cuts. For example, see
            `simulation.epr.smooth_capacitor.py`, deembed_cross_sections['port_a']='port_amer'.
    """
    overriden_class_attributes = {
        "junction_inductance": Param(pdt.TypeList, "Junction inductance (if junction exists)", 11.497e-9, unit="H"),
        "junction_capacitance": Param(pdt.TypeList, "Junction capacitance (if junction exists)", 0.1e-15, unit="F"),
        "build": _get_build_function(
            element_class, ignore_ports, transformation_from_center, sim_junction_type, deembed_cross_sections
        ),
    }
    if partition_region_function:
        _cache = {}

        def _get_partition_regions(simulation: Simulation):
            if simulation not in _cache:
                _cache[simulation] = partition_region_function(simulation)
            return _cache[simulation]

        overriden_class_attributes["get_partition_regions"] = _get_partition_regions
    element_sim_class = type(
        f"SingleElementSimulationClassFor{element_class.__name__}",
        (Simulation,),
        overriden_class_attributes,
    )
    add_parameters_from(element_class)(element_sim_class)
    return element_sim_class


def get_acrl_sim_class(
    element_class: Element,
    ignore_ports: list[str] | None = None,
    transformation_from_center: Callable[[pya.Cell], pya.DTrans] | None = None,
    partition_region_function: Callable[[Simulation], list[PartitionRegion]] | None = None,
    sim_junction_type: str = "Sim",
    deembed_cross_sections: dict[str] = None,
) -> type[Simulation]:
    """Creates a simulation class for ACRL (AC Resistance and Inductance) measurements.

    This function builds on get_single_element_sim_class() and automatically detects
    named ACRL refpoints (acrl_source_<name>, acrl_sink_<name>) in the element geometry.
    The refpoint coordinates and net names are stored in extra_json_data for use by ANSYS
    import scripts and post-processing.

    Args:
        element_class: Element class to create ACRL simulation for
        ignore_ports: Optional list of refpoint names to ignore when creating ports
        transformation_from_center: Optional transformation function for element placement
        partition_region_function: Optional function to define partition regions
        sim_junction_type: Junction type for simulation (default "Sim")
        deembed_cross_sections: Optional cross-section definitions for deembedding

    Returns:
        Simulation class configured for ACRL measurements with named nets

    Example:
        The element should define refpoints like:
        - acrl_source_inductor, acrl_sink_inductor for main inductor
        - acrl_source_feedline, acrl_sink_feedline for feedline
        - etc.

        These will be stored in extra_json_data as:
        {
            "acrl_port_locations": {
                1: {"source": [x1, y1, z1], "sink": [x2, y2, z2]},
                2: {"source": [x3, y3, z3], "sink": [x4, y4, z4]},
                ...
            },
            "net_names": {
                1: "inductor",
                2: "feedline",
                ...
            }
        }
    """
    # Get base simulation class
    BaseSimClass = get_single_element_sim_class(
        element_class,
        ignore_ports,
        transformation_from_center,
        partition_region_function,
        sim_junction_type,
        deembed_cross_sections,
    )

    # Create ACRL-enabled subclass
    class ACRLSimulation(BaseSimClass):
        """Simulation class that automatically extracts numbered ACRL refpoints."""

        def build(self):
            # Build element geometry and get refpoints
            super().build()

            # Find all named ACRL refpoints
            acrl_locations = {}
            net_names = {}

            # Search for acrl_source_<name> and acrl_sink_<name> pairs
            source_nets = {}
            sink_nets = {}

            for refpoint_name, refpoint_location in self.refpoints.items():
                if refpoint_name.startswith("acrl_source_"):
                    # Extract net name from refpoint name
                    net_name = refpoint_name.replace("acrl_source_", "")
                    source_nets[net_name] = refpoint_location
                elif refpoint_name.startswith("acrl_sink_"):
                    # Extract net name from refpoint name
                    net_name = refpoint_name.replace("acrl_sink_", "")
                    sink_nets[net_name] = refpoint_location

            # Match source and sink pairs and assign port numbers
            port_num = 1
            for net_name in sorted(source_nets.keys()):  # Sort for consistent ordering
                if net_name in sink_nets:
                    acrl_locations[port_num] = {
                        "source": [source_nets[net_name].x, source_nets[net_name].y, 0.0],
                        "sink": [sink_nets[net_name].x, sink_nets[net_name].y, 0.0]
                    }
                    net_names[port_num] = net_name
                    port_num += 1

            # Store in extra_json_data if any ACRL pairs were found
            if acrl_locations:
                # Create one InternalPort per inductor to designate as separate nets
                from kqcircuits.simulations.port import InternalPort

                for num in sorted(acrl_locations.keys()):
                    # Create port at midpoint between source and sink to designate net
                    src = acrl_locations[num]["source"]
                    snk = acrl_locations[num]["sink"]
                    mid_x = (src[0] + snk[0]) / 2
                    mid_y = (src[1] + snk[1]) / 2

                    self.ports.append(
                        InternalPort(
                            number=num,
                            signal_location=pya.DPoint(mid_x, mid_y),
                            ground_location=None
                        )
                    )

                # Store ACRL locations and net names for ANSYS import script
                self.extra_json_data = {
                    "acrl_port_locations": acrl_locations,
                    "net_names": net_names
                }

    return ACRLSimulation
