# This code is part of KQCircuits
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


from kqcircuits.elements.element import Element
from kqcircuits.pya_resolver import pya
from kqcircuits.util.parameters import Param, pdt, add_parameters_from
from kqcircuits.elements.waveguide_coplanar import WaveguideCoplanar


@add_parameters_from(WaveguideCoplanar, "add_metal")
class ResonatorSpike(Element):

    feedline_length = Param(pdt.TypeDouble, "Feedline length", 500, unit="μm")
    feedline_spacing = Param(pdt.TypeDouble, "Feedline spacing", 10, unit="μm")

    l_width = Param(pdt.TypeDouble, "Inductor width", 4, unit="μm")
    l_coupling_length = Param(pdt.TypeDouble, "Inductor coupling length", 150, unit="μm")
    l_coupling_distance = Param(pdt.TypeDouble, "Inductor coupling distance", 8, unit="μm")
    l_height = Param(pdt.TypeDouble, "Inductor height", 300, unit="μm")
    l_radius = Param(pdt.TypeDouble, "Inductor turn radius", 25, unit="μm")
    l_ground_gap = Param(pdt.TypeDouble, "Inductor ground gap", 50, unit="μm")
    
    end_box_height = Param(pdt.TypeDouble, "End box height", 20, unit="μm")
    
    spike_height = Param(pdt.TypeDouble, "Spike height", 20, unit="μm")
    spike_gap = Param(pdt.TypeDouble, "Spike gap", 0.1, unit="μm")
    spike_base_width = Param(pdt.TypeDouble, "Spike base width", 10, unit="μm")
    spike_number = Param(pdt.TypeInt, "Number of spikes", 3)

    n = Param(pdt.TypeInt, "Number of points for rounding", 64)

    def build(self):

        ground_gap_bottom = -(self.l_height + self.l_coupling_distance + self.feedline_spacing + self.b + self.a/2)
        ground_gap_top = -(self.b + self.a/2  +self.feedline_spacing)
        ground_gap_left = -(self.l_coupling_length/2 + self.l_ground_gap)
        ground_gap_right = - ground_gap_left

        pts = [
            pya.DPoint(ground_gap_left, ground_gap_top),
            pya.DPoint(ground_gap_left, ground_gap_bottom),
            pya.DPoint(ground_gap_right, ground_gap_bottom),
            pya.DPoint(ground_gap_right, ground_gap_top),
        ]
        ground_gap_region = pya.Region(pya.DPolygon(pts).to_itype(self.layout.dbu))
        

        res_region = self._make_inductor() 
        feedline_region = self._make_feedline()

        self.cell.shapes(self.get_layer("base_metal_gap_wo_grid")).insert(
            ground_gap_region + feedline_region - res_region
        )
        

        """

        # add reference point
        self.add_port("", pya.DPoint(0, 0), pya.DVector(-1, 0))"""

    def _make_inductor(self):
        ground_gap_bottom = -(self.l_height + self.l_coupling_distance + self.feedline_spacing + self.b + self.a/2) - 2*self.a
        ground_gap_top = -(self.b + self.a/2  +self.feedline_spacing)
    
        pts_ind = [
                pya.DPoint(-self.l_coupling_length/2 - self.l_width/2, ground_gap_bottom),
                pya.DPoint(-self.l_coupling_length/2 + self.l_width/2, ground_gap_bottom),
                pya.DPoint(-self.l_coupling_length/2 + self.l_width/2, ground_gap_top - self.l_coupling_distance - self.l_width),
                pya.DPoint(self.l_coupling_length/2 - self.l_width/2, ground_gap_top - self.l_coupling_distance - self.l_width),
                pya.DPoint(self.l_coupling_length/2 - self.l_width/2, ground_gap_bottom + 2 * self.spike_height + self.spike_gap + self.end_box_height),
                pya.DPoint(self.l_coupling_length/2 + self.l_width/2, ground_gap_bottom + 2 * self.spike_height + self.spike_gap + self.end_box_height),
                pya.DPoint(self.l_coupling_length/2 + self.l_width/2, ground_gap_top - self.l_coupling_distance),
                pya.DPoint(-self.l_coupling_length/2 - self.l_width/2, ground_gap_top - self.l_coupling_distance),
            ]
        ind_region = pya.Region(pya.DPolygon(pts_ind).to_itype(self.layout.dbu))
        ind_region.round_corners(self.l_radius / self.layout.dbu - self.l_width/self.layout.dbu, self.l_radius / self.layout.dbu, self.n)

        end_box_top = 2 * self.spike_height + self.spike_gap + self.end_box_height + ground_gap_bottom + 2*self.a
        end_box_bottom = end_box_top - self.end_box_height
        end_box_left = self.l_coupling_length/2 - self.spike_base_width*self.spike_number/2
        end_box_right = self.l_coupling_length/2 + self.spike_base_width*self.spike_number/2
        pts_end_box = [
            pya.DPoint(end_box_left, end_box_top),
            pya.DPoint(end_box_right, end_box_top),
            pya.DPoint(end_box_right, end_box_bottom),
            pya.DPoint(end_box_left, end_box_bottom),
        ]
        end_box_region = pya.Region(pya.DPolygon(pts_end_box).to_itype(self.layout.dbu))
        ind_region += end_box_region

        return ind_region


    def _make_feedline(self):
        ground_gap_bottom = -(self.l_height + self.l_coupling_distance + self.feedline_spacing + self.b + self.a/2)
        ground_gap_top = -(self.b + self.a/2  +self.feedline_spacing)
    
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

        return top_region + bottom_region
