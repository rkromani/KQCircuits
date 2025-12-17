# This code is part of KQCircuits
# Copyright (C) 2022 IQM Finland Oy
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


import math
import numpy as np

from kqcircuits.elements.element import Element
#from kqcircuits.junctions.squid import Squid
#from kqcircuits.junctions.manhattan import Manhattan
#from kqcircuits.junctions.manhattan_single_junction import ManhattanSingleJunction
#from kqcircuits.junctions.overlap_junction2 import Overlap2
from kqcircuits.junctions.rkr_bridge_junction import RKRBridge
from kqcircuits.util.parameters import Param, pdt, add_parameters_from
#from kqcircuits.qubits.qubit import Qubit
from kqcircuits.pya_resolver import pya
from kqcircuits.elements.waveguide_coplanar import WaveguideCoplanar
from kqcircuits.elements.waveguide_composite import WaveguideComposite, Node
from kqcircuits.util.refpoints import WaveguideToSimPort, JunctionSimPort


#@add_parameters_from(Squid, junction_type="Overlap2")
#@add_parameters_from(Manhattan)
#@add_parameters_from(ManhattanSingleJunction)
#@add_parameters_from(RKRBridge)
class HangerResQubit(Element):
    """
    A grounded transmon, where most of the capacitance to ground is through an electrode close to the main transmon that
    can be biased, but can be connected to ground with a large capacitance added at the chip level.
    """

    #ground gap
    ground_gap = Param(pdt.TypeList, "Width, height of the ground gap (µm, µm)", [500, 1800])
    ground_gap_r = Param(pdt.TypeDouble, "Ground gap rounding radius", 50, unit="μm")
    ground_gap_padding = Param(pdt.TypeDouble, "Ground gap padding", 50, unit="μm")

    #coupler
    coupler_extent = Param(pdt.TypeList, "Width, height of the coupler (µm, µm)", [20, 120])
    coupler_r = Param(pdt.TypeDouble, "Coupler rounding radius", 10, unit="μm")
    coupler_a = Param(pdt.TypeDouble, "Width of the coupler waveguide center conductor", Element.a, unit="μm")
    coupler_offset = Param(pdt.TypeDouble, "Distance from qubit island to coupler", 50, unit="μm")

    #qubit_island_geometry
    q_island_extent = Param(pdt.TypeList, "Width, height of the qubit island (µm, µm)", [350, 200])
    q_island_ground_spacing_top = Param(pdt.TypeDouble, "Qubit island spacing from ground at top", 10, unit="μm")
    q_island_res_spacing = Param(pdt.TypeDouble, "Qubit island spacing from resonator at bottom", 60, unit="μm")
    q_island_r = Param(pdt.TypeDouble, "Qubit island rounding radius", 20, unit="μm")
    q_island_taper_width = Param(pdt.TypeDouble, "Qubit junction tapering width on the island/ground side", 50, unit="µm")
    q_island_taper_junction_width = Param(
        pdt.TypeDouble, "Qubit junction tapering width on the junction side", 25, unit="µm"
    )
    q_island_sep = Param(pdt.TypeDouble, "Qubit and readout resonator island separation", 40, unit="μm")

    #readout_resonator_island_geometry
    r_island_extent = Param(pdt.TypeList, "Width, height of the resonator island (µm, µm)", [400, 200])
    r_island_r = Param(pdt.TypeDouble, "Resonator island rounding radius", 20, unit="μm")
    r_island_taper_width = Param(pdt.TypeDouble, "Resonator junction tapering width on the island/ground side", 60, unit="µm")
    r_island_taper_junction_width = Param(
        pdt.TypeDouble, "Resonator junction tapering width on the junction side", 25, unit="µm"
    )
    #readout_resonator_inductor_geometry
    #r_inductor_length = Param(pdt.TypeDouble, "Readout resonator inductor total length", 4000, unit="μm")
    r_inductor_width = Param(pdt.TypeDouble, "Readout resonator inductor width", 2, unit="μm")
    r_inductor_r = Param(pdt.TypeDouble, "Readout resonator inductor radius", 50, unit="μm")
    r_inductor_coupling_length = Param(pdt.TypeDouble, "Readout resonator inductor coupler length", 350, unit="μm")
    r_inductor_coupling_spacing = Param(pdt.TypeDouble, "Readout resonator inductor coupler spacing from ground", 10, unit="μm")
    r_inductor_coupling_ground_width = Param(pdt.TypeDouble, "Readout resonator inductor coupler ground width", 20, unit="μm")
    r_inductor_ground_junction_sep = Param(pdt.TypeDouble, "Separation between readout inductor grounding and junction grounding", 150, unit="μm")


    #junction
    pad_width = Param(pdt.TypeDouble, "Width of pad connecting to to circuit", 6, unit="μm")
    pad_height = Param(pdt.TypeDouble, "Height of pad connecting to to circuit", 8, unit="μm")
    base_length = Param(pdt.TypeDouble, "Length of junction base", 8, unit="μm")
    finger_length = Param(pdt.TypeDouble, "Length of junction finger", 3, unit="μm")
    finger_tip_length = Param(pdt.TypeDouble, "Length of junction finger tip", 0.5, unit="μm")
    finger_width = Param(pdt.TypeDouble, "Width of junction finger a.k.a. bridge length", 0.1, unit="μm")
    finger_taper_base_width = Param(pdt.TypeDouble, "Width of junction finger taper at base", 3, unit="μm")
    junction_length = Param(pdt.TypeDouble, "Length of junction", 0.1, unit="μm")
    shadow_angle = Param(pdt.TypeDouble, "Angle of shadow", 30, unit="deg")
    resist_thickness = Param(pdt.TypeDouble, "Thickness of resist", 3, unit="μm")
    bias_width = Param(pdt.TypeDouble, "Bias width connection to island 2", 20, unit="µm")
    #pad_to_pad_separation = Param(pdt.TypeDouble, "Bias width connection to island 2", 40, unit="µm")

    def build(self):
        # Qubit base
        ground_gap_points = [
            pya.DPoint(float(self.ground_gap[0]) / 2, float(self.ground_gap[1]) / 2),
            pya.DPoint(float(self.ground_gap[0]) / 2, -float(self.ground_gap[1]) / 2),
            pya.DPoint(-float(self.ground_gap[0]) / 2, -float(self.ground_gap[1]) / 2),
            pya.DPoint(-float(self.ground_gap[0]) / 2, float(self.ground_gap[1]) / 2),
        ]
        ground_gap_polygon = pya.DPolygon(ground_gap_points)
        ground_gap_region = pya.Region(ground_gap_polygon.to_itype(self.layout.dbu))
        ground_gap_region.round_corners(
            self.ground_gap_r / self.layout.dbu, self.ground_gap_r / self.layout.dbu, self.n
        )

        #junction property calculations
        angle_extension = 2*self.resist_thickness * np.sin(np.radians(self.shadow_angle))
        self.bridge_width = angle_extension - self.junction_length
        self.total_junction_height = self.pad_height + self.base_length + self.finger_length + self.finger_tip_length + self.bridge_width
        self.pad_to_pad_separation = self.total_junction_height #- self.pad_height/2 - self.base_length/2

        #taper_height = (self.island_island_gap - squid_height) / 2

        # Qubit region
        q_region = self._build_qubit()

        junction_offset = self.total_junction_height/2 #+ self.bridge_width / 2

        q_island_centery = self.ground_gap[1] / 2 - self.q_island_ground_spacing_top - self.q_island_extent[1]/2
        q_junction_centerx = (self.ground_gap[0] / 2 - self.q_island_extent[0]/2)/2 + self.q_island_extent[0]/2
        self.insert_cell(
            RKRBridge, pya.DTrans(1, False, q_junction_centerx + junction_offset, q_island_centery), f"JQ_",
            pad_width=self.pad_width, pad_height=self.pad_height, base_length=self.base_length,
            finger_length=self.finger_length, finger_tip_length=self.finger_tip_length, finger_width=self.finger_width,
            finger_taper_base_width=self.finger_taper_base_width, junction_length=self.junction_length,
            shadow_angle=self.shadow_angle, resist_thickness=self.resist_thickness
        )

        # Resonator region
        r_region = self._build_resonator()

        res_island_centery = self.ground_gap[1] / 2 - self.q_island_ground_spacing_top - self.q_island_extent[1] - self.q_island_res_spacing- self.r_island_extent[1]/2
        res_junction_centerx = (self.ground_gap[0] / 2 - self.r_island_extent[0]/2)/2 + self.r_island_extent[0]/2
        self.insert_cell(
            RKRBridge, pya.DTrans(1, False, res_junction_centerx + junction_offset, res_island_centery), f"JR_", 
            pad_width=self.pad_width, pad_height=self.pad_height, base_length=self.base_length,
            finger_length=self.finger_length, finger_tip_length=self.finger_tip_length, finger_width=self.finger_width,
            finger_taper_base_width=self.finger_taper_base_width, junction_length=self.junction_length,
            shadow_angle=self.shadow_angle, resist_thickness=self.resist_thickness
        )

        # Feedline region
        f_region = self._build_feedline()

        # Coupler gap
        coupler_region = self._build_coupler()

        self.cell.shapes(self.get_layer("base_metal_gap_wo_grid")).insert(
            ground_gap_region - coupler_region - q_region - r_region + f_region
        )

        # Protection
        #protection_polygon = pya.DPolygon(
        #    [
        #        p + pya.DVector(math.copysign(self.margin, p.x), math.copysign(self.margin, p.y))
        #        for p in ground_gap_points
        #    ]
        #)
        #protection_region = pya.Region(protection_polygon.to_itype(self.layout.dbu))
        #protection_region.round_corners(
        #    (self.ground_gap_r + self.margin) / self.layout.dbu,
        #    (self.ground_gap_r + self.margin) / self.layout.dbu,
        #    self.n,
        #)
        #self.add_protection(protection_region)

        # Coupler port
        self.add_port(
            "cplr",
            pya.DPoint(-float(self.ground_gap[1]) / 2, 0),
            direction=pya.DVector(pya.DPoint(float(-self.ground_gap[1]), 0)),
        )

        self.add_port(
            "feed_a",
            pya.DPoint(float(-self.ground_gap[0]) / 2, -self.ground_gap[1]/2 - self.r_inductor_coupling_ground_width - self.b - self.a/2),
            direction=pya.DVector(pya.DPoint(-1, 0)),
        )
        self.add_port(
            "feed_b",
            pya.DPoint(float(self.ground_gap[0]) / 2, -self.ground_gap[1]/2 - self.r_inductor_coupling_ground_width - self.b - self.a/2),
            direction=pya.DVector(pya.DPoint(1, 0)),
        )

        # Drive port
        #self.add_port(
        #    "drive",
        #    pya.DPoint(float(self.drive_position[0]), float(self.drive_position[1])),
        #    direction=pya.DVector(float(self.drive_position[0]), float(self.drive_position[1])),
        #)

        # Probepoints
        #self.refpoints["probe_island_1"] = pya.DPoint(
        #    0, self.squid_offset + squid_height / 2 + taper_height + float(self.island1_extent[1]) / 2
        #)
        #self.refpoints["probe_island_2"] = pya.DPoint(
        #    0, self.squid_offset - squid_height / 2 - taper_height - float(self.island2_extent[1]) / 2
        #)

        # Now actually add SQUID
        #self.refpoints["junction1"] = pya.DPoint(junction_centerx + self.junction_height/2, junction_centery)
        #self.refpoints["junction2"] = pya.DPoint(junction_centerx - self.junction_height/2, junction_centery)

    def _build_coupler(self):
        first_island_right_edge = -self.q_island_extent[0]/2
        coupler_right_edge = first_island_right_edge - self.coupler_offset - float(self.coupler_extent[0])
        island_center_y = -self.q_island_extent[1]/2 + self.ground_gap[1]/2 - self.q_island_ground_spacing_top
        coupler_polygon = pya.DPolygon(
            [
                pya.DPoint(coupler_right_edge, island_center_y - float(self.coupler_extent[1]) / 2),
                pya.DPoint(first_island_right_edge - self.coupler_offset, island_center_y - float(self.coupler_extent[1]) / 2),
                pya.DPoint(first_island_right_edge - self.coupler_offset, island_center_y + float(self.coupler_extent[1]) / 2),
                pya.DPoint(coupler_right_edge, island_center_y + float(self.coupler_extent[1]) / 2),
            ]
        )
        coupler_region = pya.Region(coupler_polygon.to_itype(self.layout.dbu))
        coupler_region.round_corners(self.coupler_r / self.layout.dbu, self.coupler_r / self.layout.dbu, self.n)
        coupler_path_polygon = pya.DPolygon(
            [
                pya.DPoint((float(-self.ground_gap[0]) / 2), island_center_y-self.coupler_a / 2),
                pya.DPoint((float(-self.ground_gap[0]) / 2), island_center_y+self.coupler_a / 2),
                pya.DPoint(coupler_right_edge, island_center_y+self.coupler_a / 2),
                pya.DPoint(coupler_right_edge, island_center_y-self.coupler_a / 2),
            ]
        )
        coupler_path = pya.Region(coupler_path_polygon.to_itype(self.layout.dbu))
        return coupler_region + coupler_path

    def _build_qubit(self):
        island_centery = self.ground_gap[1] / 2 - self.q_island_ground_spacing_top - self.q_island_extent[1]/2
        island_top = self.ground_gap[1] / 2 - self.q_island_ground_spacing_top

        ground_bottom = self.ground_gap[1] / 2
        taper_height = (self.ground_gap[0]/2 - self.pad_to_pad_separation/2 - self.q_island_extent[0]/2)/2
        island_polygon = pya.DPolygon(
            [
                pya.DPoint(
                    float(self.q_island_extent[0]/2), island_centery-float(self.q_island_extent[1]) / 2
                ),
                pya.DPoint(
                    float(self.q_island_extent[0]/2), island_centery+float(self.q_island_extent[1]) / 2
                ),
                pya.DPoint(-float(self.q_island_extent[0]/2), island_centery+float(self.q_island_extent[1]) / 2),
                pya.DPoint(-float(self.q_island_extent[0]/2), island_centery-float(self.q_island_extent[1]) / 2),
            ]
        )
        island_taper1 = pya.Region(
            pya.DPolygon(
                [
                    pya.DPoint(self.q_island_extent[0]/2 , island_centery - self.q_island_taper_width / 2),
                    pya.DPoint(self.q_island_extent[0]/2 , island_centery + self.q_island_taper_width / 2),
                    pya.DPoint(self.q_island_extent[0]/2 + taper_height, island_centery + self.q_island_taper_junction_width / 2),
                    pya.DPoint(self.q_island_extent[0]/2 + taper_height, island_centery - self.q_island_taper_junction_width / 2),
                ]
            ).to_itype(self.layout.dbu)
        )
        island_region = pya.Region(island_polygon.to_itype(self.layout.dbu))
        island_region += island_taper1
        island_region.round_corners(self.q_island_r / self.layout.dbu, self.q_island_r / self.layout.dbu, self.n)
        island_taper2 = pya.Region(
            pya.DPolygon(
                [
                    pya.DPoint(self.ground_gap[0]/2 , island_centery - self.q_island_taper_width / 2),
                    pya.DPoint(self.ground_gap[0]/2 , island_centery - self.q_island_taper_width * 4),
                    pya.DPoint(self.ground_gap[0]/2 + taper_height, island_centery - self.q_island_taper_width * 4),
                    pya.DPoint(self.ground_gap[0]/2 + taper_height, island_centery + self.q_island_taper_width * 4),
                    pya.DPoint(self.ground_gap[0]/2, island_centery + self.q_island_taper_width * 4),
                    pya.DPoint(self.ground_gap[0]/2 , island_centery + self.q_island_taper_width / 2),
                    pya.DPoint(self.ground_gap[0]/2 - taper_height, island_centery + self.q_island_taper_junction_width / 2),
                    pya.DPoint(self.ground_gap[0]/2 - taper_height, island_centery - self.q_island_taper_junction_width / 2),
                ]
            ).to_itype(self.layout.dbu)
        )
        island_taper2.round_corners(self.r_island_r / self.layout.dbu, self.r_island_r / self.layout.dbu, self.n)


        return island_region + island_taper2

    def _build_resonator(self):
        island_centery = self.ground_gap[1] / 2 - self.q_island_ground_spacing_top - self.q_island_extent[1] - self.q_island_res_spacing- self.r_island_extent[1]/2
        
        ground_right = self.ground_gap[0] / 2
        taper_height = (self.ground_gap[0]/2 - self.pad_to_pad_separation/2 - self.r_island_extent[0]/2)/2
        island_polygon = pya.DPolygon(
            [
                pya.DPoint(
                    float(self.r_island_extent[0]/2), island_centery-float(self.r_island_extent[1]) / 2
                ),
                pya.DPoint(
                    float(self.r_island_extent[0]/2), island_centery+float(self.r_island_extent[1]) / 2
                ),
                pya.DPoint(-float(self.r_island_extent[0]/2), island_centery+float(self.r_island_extent[1]) / 2),
                pya.DPoint(-float(self.r_island_extent[0]/2), island_centery-float(self.r_island_extent[1]) / 2),
            ]
        )
        island_taper1 = pya.Region(
            pya.DPolygon(
                [
                    pya.DPoint(self.r_island_extent[0]/2 , island_centery - self.r_island_taper_width / 2),
                    pya.DPoint(self.r_island_extent[0]/2 , island_centery + self.r_island_taper_width / 2),
                    pya.DPoint(self.r_island_extent[0]/2 + taper_height, island_centery + self.r_island_taper_junction_width / 2),
                    pya.DPoint(self.r_island_extent[0]/2 + taper_height, island_centery - self.r_island_taper_junction_width / 2),
                ]
            ).to_itype(self.layout.dbu)
        )
        island_region = pya.Region(island_polygon.to_itype(self.layout.dbu))
        island_region += island_taper1
        island_region.round_corners(self.r_island_r / self.layout.dbu, self.r_island_r / self.layout.dbu, self.n)
        island_taper2 = pya.Region(
            pya.DPolygon(
                [
                    pya.DPoint(self.ground_gap[0]/2 , island_centery - self.r_island_taper_width / 2),
                    pya.DPoint(self.ground_gap[0]/2 , island_centery - self.r_island_taper_width * 4),
                    pya.DPoint(self.ground_gap[0]/2 + taper_height, island_centery - self.r_island_taper_width * 4),
                    pya.DPoint(self.ground_gap[0]/2 + taper_height, island_centery + self.r_island_taper_width * 4),
                    pya.DPoint(self.ground_gap[0]/2, island_centery + self.r_island_taper_width * 4),
                    pya.DPoint(self.ground_gap[0]/2 , island_centery + self.r_island_taper_width / 2),
                    pya.DPoint(self.ground_gap[0]/2 - taper_height, island_centery + self.r_island_taper_junction_width / 2),
                    pya.DPoint(self.ground_gap[0]/2 - taper_height, island_centery - self.r_island_taper_junction_width / 2),
                ]
            ).to_itype(self.layout.dbu)
        )
        island_taper2.round_corners(self.r_island_r / self.layout.dbu, self.r_island_r / self.layout.dbu, self.n)


        #inductor
        self.add_port(
            "res_i_ground",
            pya.DPoint(float(self.ground_gap[0]) / 2, island_centery - self.r_inductor_ground_junction_sep),
            direction=pya.DVector(pya.DPoint(-1, 0)),
        )
        res_i_ground_x = float(self.ground_gap[0]) / 2
        res_i_ground_y = island_centery - self.r_inductor_ground_junction_sep
        self.add_port(
            "res_i_island",
            pya.DPoint(float(-self.r_island_extent[0]) / 2, island_centery),
            direction=pya.DVector(pya.DPoint(-1, 0)),
        )
        res_i_island_x = -self.r_island_extent[0] / 2
        res_i_island_y = island_centery

        coupling_center_ground_step = self.a/2 + self.r_inductor_coupling_spacing
        ground_i_stepout = res_i_ground_x - (self.r_inductor_coupling_length/2 + self.r_inductor_r)
        island_i_stepout = -res_i_island_x + (-self.r_inductor_coupling_length/2 - self.r_inductor_r)
        #length_var = self.r_inductor_length - (self.r_inductor_coupling_length + self.r_inductor_r*np.pi - ground_i_stepout - island_i_stepout)
        #length_g_side_var = (length_var - self.r_inductor_ground_junction_sep)/2
        #length_i_side_var = (length_var + self.r_inductor_ground_junction_sep)/2

        inductor_wire_poly_1= pya.DPolygon(
            [
                pya.DPoint(res_i_island_x + self.r_inductor_r * 0.5, res_i_island_y + self.r_inductor_width / 2),
                pya.DPoint(res_i_island_x + self.r_inductor_r * 0.5, res_i_island_y - self.r_inductor_width / 2),
                pya.DPoint(-self.ground_gap[0]/2 + self.r_inductor_r * 1.5 + self.ground_gap_r, res_i_island_y - self.r_inductor_width / 2),
                pya.DPoint(-self.ground_gap[0]/2 + self.r_inductor_r * 1.5 + self.ground_gap_r, res_i_island_y + self.r_inductor_width / 2),
            ]
        )
        inductor_wire = pya.Region(inductor_wire_poly_1.to_itype(self.layout.dbu ))

        inductor_wire_poly_2= pya.DPolygon(
            [
                pya.DPoint(-self.ground_gap[0]/2 + self.r_inductor_r * 1.5 + self.ground_gap_r, res_i_island_y - self.r_inductor_width / 2),
                pya.DPoint(-self.ground_gap[0]/2 + self.r_inductor_r * 1.5 + self.ground_gap_r, -self.ground_gap[1]/2 + self.r_inductor_coupling_spacing),
                pya.DPoint(-self.ground_gap[0]/2 + self.r_inductor_r * 1.5 + self.ground_gap_r + self.r_inductor_width, -self.ground_gap[1]/2 + self.r_inductor_coupling_spacing),
                pya.DPoint(-self.ground_gap[0]/2 + self.r_inductor_r * 1.5 + self.ground_gap_r + self.r_inductor_width, res_i_island_y - self.r_inductor_width / 2),
            ]
        )
        inductor_wire += pya.Region(inductor_wire_poly_2.to_itype(self.layout.dbu))

        inductor_wire_poly_3= pya.DPolygon(
            [
                pya.DPoint(-self.ground_gap[0]/2 + self.r_inductor_r * 1.5 + self.ground_gap_r, -self.ground_gap[1]/2 + self.r_inductor_coupling_spacing),
                pya.DPoint(self.ground_gap[0]/2 - self.r_inductor_r * 1.5 - self.ground_gap_r, -self.ground_gap[1]/2 + self.r_inductor_coupling_spacing),
                pya.DPoint(self.ground_gap[0]/2 - self.r_inductor_r * 1.5 - self.ground_gap_r, -self.ground_gap[1]/2 + self.r_inductor_coupling_spacing - self.r_inductor_width),
                pya.DPoint(-self.ground_gap[0]/2 + self.r_inductor_r * 1.5 + self.ground_gap_r, -self.ground_gap[1]/2 + self.r_inductor_coupling_spacing - self.r_inductor_width),
            ]
        )
        inductor_wire += pya.Region(inductor_wire_poly_3.to_itype(self.layout.dbu))

        inductor_wire_poly_4= pya.DPolygon(
            [
                pya.DPoint(self.ground_gap[0]/2 - self.r_inductor_r * 1.5 - self.ground_gap_r, -self.ground_gap[1]/2 + self.r_inductor_coupling_spacing),
                pya.DPoint(self.ground_gap[0]/2 - self.r_inductor_r * 1.5 - self.ground_gap_r, res_i_island_y - self.r_inductor_r*2 - self.r_island_extent[1]/2),
                pya.DPoint(self.ground_gap[0]/2 - self.r_inductor_r * 1.5 - self.ground_gap_r - self.r_inductor_width, res_i_island_y - self.r_inductor_r*2 - self.r_island_extent[1]/2),
                pya.DPoint(self.ground_gap[0]/2 - self.r_inductor_r * 1.5 - self.ground_gap_r - self.r_inductor_width, -self.ground_gap[1]/2 + self.r_inductor_coupling_spacing),
            ]
        )
        inductor_wire += pya.Region(inductor_wire_poly_4.to_itype(self.layout.dbu))

        inductor_wire_poly_5= pya.DPolygon(
            [
                pya.DPoint(self.ground_gap[0]/2 - self.r_inductor_r * 1.5 - self.ground_gap_r, res_i_island_y - self.r_inductor_r*2 - self.r_island_extent[1]/2),
                pya.DPoint(self.ground_gap[0]/2 - self.r_inductor_r * 1.5 - self.ground_gap_r, res_i_island_y - self.r_inductor_r*2 - self.r_island_extent[1]/2 - self.r_inductor_width),
                pya.DPoint(self.ground_gap[0]/2 + self.r_inductor_r * 0.5, res_i_island_y - self.r_inductor_r*2 - self.r_island_extent[1]/2 - self.r_inductor_width),
                pya.DPoint(self.ground_gap[0]/2 + self.r_inductor_r * 0.5, res_i_island_y - self.r_inductor_r*2 - self.r_island_extent[1]/2),
            ]
        )
        inductor_wire += pya.Region(inductor_wire_poly_5.to_itype(self.layout.dbu))


        inductor_wire.round_corners(self.r_inductor_r / self.layout.dbu, self.r_inductor_r / self.layout.dbu + self.r_inductor_width / self.layout.dbu, self.n)
    
        
        #self.insert_cell(
        #        WaveguideComposite,
        #        nodes = [
        #            Node((res_i_ground_x, res_i_ground_y)), 
        #            Node((self.r_inductor_coupling_length/2 + self.r_inductor_r, res_i_ground_y)), 
        #            Node((self.r_inductor_coupling_length/2 + self.r_inductor_r, -self.ground_gap[1]/2 + coupling_center_ground_step), 
        #                 length_before=length_g_side_var),
        #            Node((-self.r_inductor_coupling_length/2 - self.r_inductor_r, -self.ground_gap[1]/2 + coupling_center_ground_step)),
        #            Node((-self.r_inductor_coupling_length/2 - self.r_inductor_r, res_i_island_y), 
        #                 length_before=length_i_side_var),
        #            Node((res_i_island_x, res_i_island_y)),
        #        ], 
        #        r=self.r_inductor_r, 
        #        #add_metal=True,
        #        #ground_grid_in_trace=True
        #    )


        return island_region + island_taper2 + inductor_wire


    def _build_feedline(self):

        feedline_center_y = -self.ground_gap[1]/2 - self.r_inductor_coupling_ground_width - self.b - self.a/2

        feedline_gap_top = pya.Region(
            pya.DPolygon(
                [
                    pya.DPoint(-self.ground_gap[0]/2 , feedline_center_y + self.a/2),
                    pya.DPoint(-self.ground_gap[0]/2 , feedline_center_y + self.a/2 + self.b),
                    pya.DPoint(self.ground_gap[0]/2 , feedline_center_y + self.a/2 + self.b),
                    pya.DPoint(self.ground_gap[0]/2 , feedline_center_y + self.a/2),
                ]
            ).to_itype(self.layout.dbu)
        )

        feedline_gap_bottom = pya.Region(
            pya.DPolygon(
                [
                    pya.DPoint(-self.ground_gap[0]/2 , feedline_center_y - self.a/2),
                    pya.DPoint(-self.ground_gap[0]/2 , feedline_center_y - self.a/2 - self.b),
                    pya.DPoint(self.ground_gap[0]/2 , feedline_center_y - self.a/2 - self.b),
                    pya.DPoint(self.ground_gap[0]/2 , feedline_center_y - self.a/2),
                ]
            ).to_itype(self.layout.dbu)
        )

        return feedline_gap_top + feedline_gap_bottom

    @classmethod
    def get_sim_ports(cls, simulation):  # pylint: disable=unused-argument
        return [JunctionSimPort(), WaveguideToSimPort("port_cplr", side="top")]
