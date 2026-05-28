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

from math import pi
from kqcircuits.pya_resolver import pya
from kqcircuits.util.parameters import Param, pdt
from kqcircuits.elements.element import Element
from kqcircuits.elements.waveguide_coplanar import WaveguideCoplanar
from kqcircuits.util.refpoints import WaveguideToSimPort
from kqcircuits.elements.waveguide_composite import WaveguideComposite, Node


class HangerResonatorL4(Element):
    """
    Hanger Resonator
    """

    feedline_length = Param(pdt.TypeDouble, "Feedline length", 600, unit="μm")
    feedline_spacing = Param(pdt.TypeDouble, "Feedline spacing", 10, unit="μm")
    feedline_coupling_ground_spacing = Param(pdt.TypeDouble, "Feedline coupling ground spacing", 10, unit="μm")
    feedline_cutout = Param(pdt.TypeDouble, "Feedline cutout length", 50, unit="μm")
    feedline_cutout_bool = Param(pdt.TypeBoolean, "Whether to add feedline cutout", False)

    res_length = Param(pdt.TypeDouble, "Total length of the resonator", 4250, unit="μm")
    res_coupling_length = Param(pdt.TypeDouble, "Length of the coupling section of the resonator", 200, unit="μm")
    res_bottom_y = Param(pdt.TypeDouble, "Y coordinate of the bottom of the resonator", 2000, unit="μm")
    res_r = Param(pdt.TypeDouble, "Turn radius of the resonator", 100, unit="μm")
    res_a = Param(pdt.TypeDouble, "Trace width of resonator line", 5.15, unit="μm")
    res_b = Param(pdt.TypeDouble, "Gap width of resonator line", 3, unit="μm")

    ground_width = Param(pdt.TypeDouble, "Trace width of middle ground", 10, unit="μm")

    def build(self):

        # distance from origin to start of the wg trace
        wg_start_height = -self.a / 2 - self.b - self.feedline_coupling_ground_spacing - self.res_b - self.res_a / 2

        node_coupling_feedline_start = Node(pya.DPoint(-self.res_coupling_length/2, wg_start_height))
        node_coupling_feedline_end = Node(pya.DPoint(self.res_coupling_length/2, wg_start_height))
        node_end = Node(pya.DPoint(self.res_coupling_length/2, wg_start_height  -self.res_bottom_y))
        
        def my_route(extra_length):
            return [
                node_coupling_feedline_start,
                node_coupling_feedline_end,
                Node(pya.DPoint(self.res_coupling_length/2, wg_start_height - self.res_bottom_y), length_before=extra_length)
            ]

        WaveguideComposite.produce_fixed_length_waveguide(
            self,
            my_route, initial_guess=self.res_bottom_y + self.res_coupling_length, length=self.res_length,
            r=self.res_r, a=self.res_a, b=self.res_b, layer=self.get_layer("base_metal_gap_wo_grid")
        )

        pts_open_end = [
            pya.DPoint(self.res_coupling_length/2 - self.res_a/2 - self.res_b, wg_start_height - self.res_bottom_y),
            pya.DPoint(self.res_coupling_length/2 + self.res_a/2 + self.res_b, wg_start_height - self.res_bottom_y),
            pya.DPoint(self.res_coupling_length/2 + self.res_a/2 + self.res_b, wg_start_height - self.res_bottom_y - 2*self.res_b),
            pya.DPoint(self.res_coupling_length/2 - self.res_a/2 - self.res_b, wg_start_height - self.res_bottom_y - 2*self.res_b),
        ]
        region_open_end = pya.Region(pya.DPolygon(pts_open_end).to_itype(self.layout.dbu))

        
        feedline_region = self._make_feedline()

        self.cell.shapes(self.get_layer("base_metal_gap_wo_grid")).insert(
            region_open_end + feedline_region
        )

        

        self.add_port("feedline_a", pya.DPoint(-self.feedline_length/2, 0), pya.DVector(-1, 0))
        self.add_port("feedline_b", pya.DPoint(self.feedline_length/2, 0), pya.DVector(1, 0))
        self.refpoints["feedline_a"] = pya.DPoint(-self.feedline_length/2, 0)
        self.refpoints["feedline_b"] = pya.DPoint(self.feedline_length/2, 0)

    @classmethod
    def get_sim_ports(cls, simulation):
        return [
            WaveguideToSimPort("port_feedline_a", use_internal_ports=False, a=simulation.a, b=simulation.b),
            WaveguideToSimPort("port_feedline_b", use_internal_ports=False, a=simulation.a, b=simulation.b),
        ]

    def _make_feedline(self):
        pts_top = [
                pya.DPoint(-self.feedline_length/2, self.a/2),
                pya.DPoint(-self.feedline_length/2, self.a/2 + self.b),
                pya.DPoint(self.feedline_length/2, self.a/2 + self.b),
                pya.DPoint(self.feedline_length/2, self.a/2)
                ]
        top_region = pya.Region(pya.DPolygon(pts_top).to_itype(self.layout.dbu))
       
        pts_bottom = [
                pya.DPoint(-self.feedline_length/2, -self.a/2),
                pya.DPoint(-self.feedline_length/2, -self.a/2 - self.b),
                pya.DPoint(self.feedline_length/2, -self.a/2 - self.b),
                pya.DPoint(self.feedline_length/2, -self.a/2)
                ]
        bottom_region = pya.Region(pya.DPolygon(pts_bottom).to_itype(self.layout.dbu))

        if self.feedline_cutout_bool:
            cutout_l_pts = [
                pya.DPoint(-self.feedline_length/2, -self.a/2 - self.b),
                pya.DPoint(-self.feedline_length/2 - self.feedline_cutout, -self.a/2 - self.b),
                pya.DPoint(-self.feedline_length/2 - self.feedline_cutout, self.a/2 + self.b),
                pya.DPoint(-self.feedline_length/2, self.a/2 + self.b),
            ]
            cutout_r_pts = [
                pya.DPoint(self.feedline_length/2, -self.a/2 - self.b),
                pya.DPoint(self.feedline_length/2 + self.feedline_cutout, -self.a/2 - self.b),
                pya.DPoint(self.feedline_length/2 + self.feedline_cutout, self.a/2 + self.b),
                pya.DPoint(self.feedline_length/2, self.a/2 + self.b),
            ]  
            cutout_l_region = pya.Region(pya.DPolygon(cutout_l_pts).to_itype(self.layout.dbu))
            cutout_r_region = pya.Region(pya.DPolygon(cutout_r_pts).to_itype(self.layout.dbu))
            cutout_region = cutout_l_region + cutout_r_region
        else:
            cutout_region = pya.Region()

        return top_region + bottom_region + cutout_region
