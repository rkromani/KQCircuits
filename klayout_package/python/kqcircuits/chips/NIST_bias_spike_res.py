# This code is part of KQCircuits
# Copyright (C) 2025 Roger Romani
# Copyright (C) 2023 IQM Finland Oy
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation, either version 3 of the License, or (at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see https://www.gnu.org/licenses/gpl-3.0.html.
#
# Contributions are made under the IQM Individual Contributor License Agreement.
# For more information, see: https://meetiqm.com/iqm-individual-contributor-license-agreement
 
from math import pi
from kqcircuits.pya_resolver import pya
from kqcircuits.elements.element import Element
from kqcircuits.chips.chip import Chip
#from kqcircuits.elements.chip_frame import ChipFrame
from kqcircuits.util.parameters import Param, pdt, add_parameters_from, add_parameter
from kqcircuits.elements.launcher import Launcher
from kqcircuits.elements.waveguide_coplanar import WaveguideCoplanar
from kqcircuits.elements.waveguide_composite import WaveguideComposite, Node
from kqcircuits.elements.hanger_resonator import HangerResonator

from kqcircuits.elements.resonator_spike import ResonatorSpike
from kqcircuits.elements.finger_capacitor_ground_v3 import FingerCapacitorGroundV3

@add_parameters_from(Element, b = 4.6, a = 10, margin=100)
@add_parameters_from(ResonatorSpike)
@add_parameters_from(FingerCapacitorGroundV3)
#@add_parameters_from(ChipFrame, box = pya.DBox(pya.DPoint(0, 0), pya.DPoint(7500, 7500)))
# no flip chip alignment markers
#@add_parameters_from(ChipFrame, marker_types=['','','',''])
#@add_parameters_from(Chip,
#                     face_boxes=[None, pya.DBox(pya.DPoint(0, 0), pya.DPoint(3000, 3000))],
#                    )#frames_dice_width=['50'], name_brand='NIST', name_chip='BIAS', name_copy='v3F')

class BiasSpikeResTest(Element):
    # parameters accessible in PCell
    #a_launcher = Param(pdt.TypeDouble, "Pad CPW trace center", 200, unit="μm")
    #b_launcher = Param(pdt.TypeDouble, "Pad CPW trace gap", 153, unit="μm")
    #launcher_width = Param(pdt.TypeDouble, "Pad extent", 250, unit="μm")
    #taper_length = Param(pdt.TypeDouble, "Tapering length", 200, unit="μm")
    #launcher_frame_gap = Param(pdt.TypeDouble, "Gap at chip frame", 100, unit="μm")
    #launcher_indent = Param(pdt.TypeDouble, "Chip edge to pad port", 700, unit="μm")

    cap_distance = Param(pdt.TypeDouble, "Capacitor distance from bottom of ground gap", 5, unit="μm")

    inductor_width = Param(pdt.TypeDouble, "Width of inductor trace", 3, unit="μm")

    # Lumped model control parameters
    use_lumped_models = Param(pdt.TypeBoolean, "Use lumped models for capacitor and junction", False)
    cap_lumped_value = Param(pdt.TypeDouble, "Lumped capacitance value (fF)", 150.0, unit="fF")
    junction_lumped_inductance = Param(pdt.TypeDouble, "Lumped junction inductance (nH)", 11.5, unit="nH")

    def build(self):


        self.insert_cell(
            ResonatorSpike, pya.DPoint(0, 0), f"RS",
            bias_width=self.a,
            inductor_width=self.inductor_width,
            # Lumped junction parameters
            junction_use_lumped=False, #self.use_lumped_models,
            #junction_lumped_inductance=self.junction_lumped_inductance,
            #ground_gap=['800', '510'],
            #ground_gap_r=20.0, coupler_extent=['300', '18'], coupler_r=20.0, coupler_offset=14.0,
            #finger_width=3, finger_gap=3, finger_gap_end=3, finger_length=55, finger_number=34,
            #corner_r=5, with_junction=True, #with_tapers=True,
            #island1_taper_width=20, island1_taper_junction_width=20,
            #island2_taper_width=20, island2_taper_junction_width=20,
        )

        # Position capacitor so its top edge is cap_distance below the inductor ground
        cap_center_x = self.refpoints[f"RS_inductor_ground"].x
        cap_center_y = self.refpoints[f"RS_inductor_ground"].y - self.cap_distance

        self.insert_cell(
            FingerCapacitorGroundV3, pya.DPoint(cap_center_x, cap_center_y), f"CAP",
            # Lumped capacitor parameters
            use_lumped_model=self.use_lumped_models,
            lumped_capacitance=self.cap_lumped_value,
        )

        self.insert_cell(
                WaveguideComposite, 
                nodes=[
                Node(self.refpoints[f"RS_inductor_ground"]),
                Node(self.refpoints['CAP_top_port'])
            ],
            a=self.inductor_width,
            b=self.b
            )

        if not self.use_lumped_models:
            self.insert_cell(
                    WaveguideComposite,
                    nodes=[
                    Node(self.refpoints['CAP_bottom_port']),
                    Node((self.refpoints['CAP_bottom_port'].x, self.refpoints['CAP_bottom_port'].y - self.cap_distance))
                ],
                a=0,
                b=self.b
                )

    @classmethod
    def get_sim_ports(cls, simulation):
        """Collect simulation ports from subcells (ResonatorSpike and FingerCapacitorGroundV3).

        This is needed because BiasSpikeResTest inserts these as subcells, so their
        get_sim_ports() methods need to be called explicitly.
        """
        ports = []

        # Get ports from ResonatorSpike (junction lumped model if enabled)
        ports.extend(ResonatorSpike.get_sim_ports(simulation))

        # Get ports from FingerCapacitorGroundV3 (capacitor lumped model if enabled)
        ports.extend(FingerCapacitorGroundV3.get_sim_ports(simulation))

        return ports
