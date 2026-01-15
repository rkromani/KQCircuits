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

import numpy as np


@add_parameters_from(WaveguideCoplanar, "add_metal")
class ResonatorSpike(Element):

    feedline_length = Param(pdt.TypeDouble, "Feedline length", 700, unit="μm")
    feedline_spacing = Param(pdt.TypeDouble, "Feedline spacing", 10, unit="μm")

    l_width = Param(pdt.TypeDouble, "Inductor width", 3, unit="μm")
    l_coupling_length = Param(pdt.TypeDouble, "Inductor coupling length", 250, unit="μm")
    l_coupling_distance = Param(pdt.TypeDouble, "Inductor coupling distance", 16, unit="μm")
    l_height = Param(pdt.TypeDouble, "Inductor height", 500, unit="μm")
    l_radius = Param(pdt.TypeDouble, "Inductor turn radius", 25, unit="μm")
    l_ground_gap = Param(pdt.TypeDouble, "Inductor ground gap", 120, unit="μm")

    end_box_width = Param(pdt.TypeDouble, "End box width", 20, unit="μm")
    end_box_buffer = Param(pdt.TypeDouble, "End box buffer", 2.5, unit="μm")
    end_box_spacing = Param(pdt.TypeDouble, "End box spacing from bottom of ground gap box", 20, unit="μm")

    t_cut_body_width = Param(pdt.TypeDouble, "Width of T-cut", 3, unit="μm")
    t_cut_distance_from_edge = Param(pdt.TypeDouble, "Distance of T-cut from edge of optical layer", 3, unit="μm")
    t_cut_t_width = Param(pdt.TypeDouble, "Width of T-cut T", 6, unit="μm")
    t_cut_t_height = Param(pdt.TypeDouble, "Height of T-cut T", 3, unit="μm")
    t_cut_number = Param(pdt.TypeInt, "Number of T-cuts", 2)
    t_cut_radius = Param(pdt.TypeDouble, "Radius of T-cut corners", 2, unit="μm")
    
    spike_height = Param(pdt.TypeDouble, "Spike height", 1.5, unit="μm")
    spike_gap = Param(pdt.TypeDouble, "Spike gap", 0.1, unit="μm")
    spike_base_width = Param(pdt.TypeDouble, "Spike base width", 1, unit="μm")
    spike_base_height = Param(pdt.TypeDouble, "Spike base height", 10, unit="μm")
    spike_number = Param(pdt.TypeInt, "Number of spikes", 8)
    
    shadow_angle_1 = Param(pdt.TypeDouble, "Angle of shadow 1", 30, unit="deg")
    shadow_angle_2 = Param(pdt.TypeDouble, "Angle of shadow 2", 0, unit="deg")
    resist_thickness = Param(pdt.TypeDouble, "Thickness of resist", 3, unit="μm")

    n = Param(pdt.TypeInt, "Number of points for rounding", 64)

    def build(self):

        self.angle_evap_offset = self.resist_thickness * (np.sin(np.radians(self.shadow_angle_1)) - np.sin(np.radians(self.shadow_angle_2)))
        self.end_box_height = self.spike_base_width*self.spike_number + 2 * self.end_box_buffer

        self.ground_gap_bottom = -(self.l_height + self.l_coupling_distance + self.feedline_spacing + self.b + self.a/2)
        self.ground_gap_top = -(self.b + self.a/2 + self.feedline_spacing)
        self.ground_gap_left = -(self.l_coupling_length/2 + self.l_ground_gap)
        self.ground_gap_right = - self.ground_gap_left

        self.end_box_top = self.end_box_spacing + self.ground_gap_bottom + self.end_box_height
        self.end_box_bottom = self.end_box_spacing + self.ground_gap_bottom
        self.end_box_left = self.l_coupling_length/2 - self.end_box_width
        self.end_box_right = self.l_coupling_length/2 + self.end_box_width

        self.spike_region_width = self.spike_height * 2 + self.spike_gap

        pts = [
            pya.DPoint(self.ground_gap_left, self.ground_gap_top),
            pya.DPoint(self.ground_gap_left, self.ground_gap_bottom),
            pya.DPoint(self.ground_gap_right, self.ground_gap_bottom),
            pya.DPoint(self.ground_gap_right, self.ground_gap_top),
        ]
        ground_gap_region = pya.Region(pya.DPolygon(pts).to_itype(self.layout.dbu))
        

        inductor_region = self._make_inductor() 
        end_box_region = self._make_end_box()
        feedline_region = self._make_feedline()
        
        if self.spike_number != 0:
            t_cut_region = self._make_t_cuts()
        else:
            t_cut_region = pya.Region()
        
        spikes_shape = self._make_spikes_shape()
        self.cell.shapes(self.get_layer("SIS_junction")).insert(spikes_shape)

        spikes_shadow = self._make_spikes_shadow()
        self.cell.shapes(self.get_layer("SIS_shadow")).insert(spikes_shadow)

        spikes_combined = (spikes_shape + spikes_shadow).merge()
        self.cell.shapes(self.get_layer("SIS_junction_2")).insert(
            spikes_combined
        )

        self.cell.shapes(self.get_layer("base_metal_gap")).insert(
            ground_gap_region + feedline_region - inductor_region - end_box_region + t_cut_region
        )
        self.cell.shapes(self.get_layer("base_metal_gap_wo_grid")).insert(
            ground_gap_region + feedline_region - inductor_region - end_box_region + t_cut_region - spikes_combined
        )

        # Add mesh control regions for fine-grained ANSYS mesh refinement
        # mesh_1: Fine mesh around spike regions
        # mesh_2: Coarse mesh for inductor region
        spikes_meshing_region = self._make_meshing_region()
        self.cell.shapes(self.get_layer("mesh_1")).insert(
            spikes_meshing_region
        )
        self.cell.shapes(self.get_layer("mesh_2")).insert(
            inductor_region
        )
        

        # add reference point
        self.add_port("feedline_a", pya.DPoint(-self.feedline_length/2, 0), pya.DVector(-1, 0))
        self.add_port("feedline_b", pya.DPoint(self.feedline_length/2, 0), pya.DVector(1, 0))

    def _make_inductor(self):
        ground_gap_bottom = -(self.l_height + self.l_coupling_distance + self.feedline_spacing + self.b + self.a/2 + self.angle_evap_offset) - 2*self.a
        ground_gap_top = -(self.b + self.a/2  +self.feedline_spacing)
        end_box_top = self.end_box_spacing + self.ground_gap_bottom + self.end_box_height
    
        pts_ind = [
                pya.DPoint(-self.l_coupling_length/2 - self.l_width/2, ground_gap_bottom),
                pya.DPoint(-self.l_coupling_length/2 + self.l_width/2, ground_gap_bottom),
                pya.DPoint(-self.l_coupling_length/2 + self.l_width/2, ground_gap_top - self.l_coupling_distance - self.l_width),
                pya.DPoint(self.l_coupling_length/2 - self.l_width/2, ground_gap_top - self.l_coupling_distance - self.l_width),
                pya.DPoint(self.l_coupling_length/2 - self.l_width/2, end_box_top - 2 * self.a),
                pya.DPoint(self.l_coupling_length/2 + self.l_width/2, end_box_top - 2 * self.a),
                pya.DPoint(self.l_coupling_length/2 + self.l_width/2, ground_gap_top - self.l_coupling_distance),
                pya.DPoint(-self.l_coupling_length/2 - self.l_width/2, ground_gap_top - self.l_coupling_distance),
            ]
        ind_region = pya.Region(pya.DPolygon(pts_ind).to_itype(self.layout.dbu))
        ind_region.round_corners(self.l_radius / self.layout.dbu - self.l_width/self.layout.dbu, self.l_radius / self.layout.dbu, self.n)

        return ind_region
    
    def _make_end_box(self):
        
        pts_end_box = [
            pya.DPoint(self.end_box_left, self.end_box_top),
            pya.DPoint(self.end_box_right, self.end_box_top),
            pya.DPoint(self.end_box_right, self.end_box_bottom),
            pya.DPoint(self.end_box_left, self.end_box_bottom),
        ]

        end_box_region = pya.Region(pya.DPolygon(pts_end_box).to_itype(self.layout.dbu))

        pts_boxes_l = [
            pya.DPoint(self.end_box_left - self.spike_region_width, self.end_box_top),
            pya.DPoint(self.end_box_left - self.spike_region_width, self.ground_gap_bottom),
            pya.DPoint(self.end_box_left - self.spike_region_width - self.end_box_width, self.ground_gap_bottom),
            pya.DPoint(self.end_box_left - self.spike_region_width - self.end_box_width, self.end_box_top),
        ]

        pts_boxes_r = [
            pya.DPoint(self.end_box_right + self.spike_region_width, self.end_box_top),
            pya.DPoint(self.end_box_right + self.spike_region_width, self.ground_gap_bottom),
            pya.DPoint(self.end_box_right + self.spike_region_width + self.end_box_width, self.ground_gap_bottom),
            pya.DPoint(self.end_box_right + self.spike_region_width + self.end_box_width, self.end_box_top),
        ]

        end_boxes_l_region = pya.Region(pya.DPolygon(pts_boxes_l).to_itype(self.layout.dbu))
        end_boxes_r_region = pya.Region(pya.DPolygon(pts_boxes_r).to_itype(self.layout.dbu))

        return end_box_region + end_boxes_l_region + end_boxes_r_region

    def _make_feedline(self):
        ground_gap_bottom = -(self.l_height + self.l_coupling_distance + self.feedline_spacing + self.b + self.a/2 + self.angle_evap_offset)
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
    
    def _make_spikes_shape(self):

        pts_spikes_ll = [
                pya.DPoint(self.end_box_left - self.spike_region_width, self.end_box_bottom + self.end_box_buffer),
                pya.DPoint(self.end_box_left - self.spike_region_width - self.spike_base_height, self.end_box_bottom + self.end_box_buffer),
                pya.DPoint(self.end_box_left - self.spike_region_width - self.spike_base_height, self.end_box_top - self.end_box_buffer),
                pya.DPoint(self.end_box_left - self.spike_region_width, self.end_box_top - self.end_box_buffer),
                ]
        
        pts_spikes_lr = [
                pya.DPoint(self.end_box_left, self.end_box_bottom + self.end_box_buffer),
                pya.DPoint(self.end_box_left + self.spike_base_height, self.end_box_bottom + self.end_box_buffer),
                pya.DPoint(self.end_box_left + self.spike_base_height, self.end_box_top - self.end_box_buffer),
                pya.DPoint(self.end_box_left, self.end_box_top - self.end_box_buffer),
                ]
        
        pts_spikes_rl = [
                pya.DPoint(self.end_box_right, self.end_box_bottom + self.end_box_buffer),
                pya.DPoint(self.end_box_right - self.spike_base_height, self.end_box_bottom + self.end_box_buffer),
                pya.DPoint(self.end_box_right - self.spike_base_height, self.end_box_top - self.end_box_buffer),
                pya.DPoint(self.end_box_right, self.end_box_top - self.end_box_buffer),
                ]
        
        pts_spikes_rr = [
                pya.DPoint(self.end_box_right + self.spike_region_width, self.end_box_bottom + self.end_box_buffer),
                pya.DPoint(self.end_box_right + self.spike_region_width + self.spike_base_height, self.end_box_bottom + self.end_box_buffer),
                pya.DPoint(self.end_box_right + self.spike_region_width + self.spike_base_height, self.end_box_top - self.end_box_buffer),
                pya.DPoint(self.end_box_right + self.spike_region_width, self.end_box_top - self.end_box_buffer),
                ]
        
        i = 0
        while i < self.spike_number:
            j = 0
            while j < 2:
                if j == 0:
                    pts_spikes_ll.append(pya.DPoint(self.end_box_left - self.spike_region_width, self.end_box_top - self.end_box_buffer - (i + j/2) * self.spike_base_width))
                    pts_spikes_lr.append(pya.DPoint(self.end_box_left, self.end_box_top - self.end_box_buffer - (i + j/2) * self.spike_base_width))
                    pts_spikes_rl.append(pya.DPoint(self.end_box_right, self.end_box_top - self.end_box_buffer - (i + j/2) * self.spike_base_width))
                    pts_spikes_rr.append(pya.DPoint(self.end_box_right + self.spike_region_width, self.end_box_top - self.end_box_buffer - (i + j/2) * self.spike_base_width))
                else:
                    pts_spikes_ll.append(pya.DPoint(self.end_box_left - self.spike_region_width + self.spike_height, self.end_box_top - self.end_box_buffer - (i + j/2) * self.spike_base_width))
                    pts_spikes_lr.append(pya.DPoint(self.end_box_left - self.spike_height, self.end_box_top - self.end_box_buffer - (i + j/2) * self.spike_base_width))
                    pts_spikes_rl.append(pya.DPoint(self.end_box_right + self.spike_height, self.end_box_top - self.end_box_buffer - (i + j/2) * self.spike_base_width))
                    pts_spikes_rr.append(pya.DPoint(self.end_box_right + self.spike_region_width - self.spike_height, self.end_box_top - self.end_box_buffer - (i + j/2) * self.spike_base_width))

                j += 1
            i += 1

        spikes_ll_region = pya.Region(pya.DPolygon(pts_spikes_ll).to_itype(self.layout.dbu))
        spikes_lr_region = pya.Region(pya.DPolygon(pts_spikes_lr).to_itype(self.layout.dbu))
        spikes_rl_region = pya.Region(pya.DPolygon(pts_spikes_rl).to_itype(self.layout.dbu))
        spikes_rr_region = pya.Region(pya.DPolygon(pts_spikes_rr).to_itype(self.layout.dbu))

        return spikes_ll_region + spikes_lr_region + spikes_rl_region + spikes_rr_region

    def _make_spikes_shadow(self):

        spikes_shape = self._make_spikes_shape()

        shift_1_y = -1 * self.resist_thickness * np.sin(np.radians(self.shadow_angle_1))
        shift_2_y = -1 * self.resist_thickness * np.sin(np.radians(self.shadow_angle_2))
        shift_1_y_dbu = shift_1_y / self.layout.dbu
        shift_2_y_dbu = shift_2_y / self.layout.dbu

        trans_1 = pya.DTrans(0, False, 0, int(shift_1_y_dbu))
        trans_2 = pya.DTrans(0, False, 0, int(-shift_2_y_dbu))

        shadow_1 = spikes_shape.transformed(trans_1)
        shadow_2 = spikes_shape.transformed(trans_2)

        return shadow_1 + shadow_2
    
    def _make_t_cuts(self):

        t_cut_center_x_l = self.l_coupling_length/2 - self.end_box_width - self.spike_region_width/2
        t_cut_center_x_r = self.l_coupling_length/2 + self.end_box_width + self.spike_region_width/2

        t_cut_total_length = self.spike_region_width + 2 * self.t_cut_distance_from_edge + 2*self.t_cut_t_height

        t_cut_center_y_list = np.zeros(self.t_cut_number)
        for i in range(self.t_cut_number):
            t_cut_center_y_list[i] = self.end_box_bottom + self.end_box_buffer + (i + 0.5) * ((self.end_box_height - 2*self.end_box_buffer) / self.t_cut_number)

        i = 0
        while i < self.t_cut_number:
            t_cut_pts_l = [
                pya.DPoint(t_cut_center_x_l - t_cut_total_length / 2, t_cut_center_y_list[i] + self.t_cut_t_width / 2),
                pya.DPoint(t_cut_center_x_l - t_cut_total_length / 2, t_cut_center_y_list[i] - self.t_cut_t_width / 2),
                pya.DPoint(t_cut_center_x_l - t_cut_total_length / 2 + self.t_cut_t_height, t_cut_center_y_list[i] - self.t_cut_t_width / 2),
                pya.DPoint(t_cut_center_x_l - t_cut_total_length / 2 + self.t_cut_t_height, t_cut_center_y_list[i] - self.t_cut_body_width / 2),
                pya.DPoint(t_cut_center_x_l + t_cut_total_length / 2 - self.t_cut_t_height, t_cut_center_y_list[i] - self.t_cut_body_width / 2),
                pya.DPoint(t_cut_center_x_l + t_cut_total_length / 2 - self.t_cut_t_height, t_cut_center_y_list[i] - self.t_cut_t_width / 2),
                pya.DPoint(t_cut_center_x_l + t_cut_total_length / 2, t_cut_center_y_list[i] - self.t_cut_t_width / 2),
                pya.DPoint(t_cut_center_x_l + t_cut_total_length / 2, t_cut_center_y_list[i] + self.t_cut_t_width / 2),
                pya.DPoint(t_cut_center_x_l + t_cut_total_length / 2 - self.t_cut_t_height, t_cut_center_y_list[i] + self.t_cut_t_width / 2),
                pya.DPoint(t_cut_center_x_l + t_cut_total_length / 2 - self.t_cut_t_height, t_cut_center_y_list[i] + self.t_cut_body_width / 2),
                pya.DPoint(t_cut_center_x_l - t_cut_total_length / 2 + self.t_cut_t_height, t_cut_center_y_list[i] + self.t_cut_body_width / 2),
                pya.DPoint(t_cut_center_x_l - t_cut_total_length / 2 + self.t_cut_t_height, t_cut_center_y_list[i] + self.t_cut_t_width / 2),
            ]

            t_cut_pts_r = [
                pya.DPoint(t_cut_center_x_r - t_cut_total_length / 2, t_cut_center_y_list[i] + self.t_cut_t_width / 2),
                pya.DPoint(t_cut_center_x_r - t_cut_total_length / 2, t_cut_center_y_list[i] - self.t_cut_t_width / 2),
                pya.DPoint(t_cut_center_x_r - t_cut_total_length / 2 + self.t_cut_t_height, t_cut_center_y_list[i] - self.t_cut_t_width / 2),
                pya.DPoint(t_cut_center_x_r - t_cut_total_length / 2 + self.t_cut_t_height, t_cut_center_y_list[i] - self.t_cut_body_width / 2),
                pya.DPoint(t_cut_center_x_r + t_cut_total_length / 2 - self.t_cut_t_height, t_cut_center_y_list[i] - self.t_cut_body_width / 2),
                pya.DPoint(t_cut_center_x_r + t_cut_total_length / 2 - self.t_cut_t_height, t_cut_center_y_list[i] - self.t_cut_t_width / 2),
                pya.DPoint(t_cut_center_x_r + t_cut_total_length / 2, t_cut_center_y_list[i] - self.t_cut_t_width / 2),
                pya.DPoint(t_cut_center_x_r + t_cut_total_length / 2, t_cut_center_y_list[i] + self.t_cut_t_width / 2),
                pya.DPoint(t_cut_center_x_r + t_cut_total_length / 2 - self.t_cut_t_height, t_cut_center_y_list[i] + self.t_cut_t_width / 2),
                pya.DPoint(t_cut_center_x_r + t_cut_total_length / 2 - self.t_cut_t_height, t_cut_center_y_list[i] + self.t_cut_body_width / 2),
                pya.DPoint(t_cut_center_x_r - t_cut_total_length / 2 + self.t_cut_t_height, t_cut_center_y_list[i] + self.t_cut_body_width / 2),
                pya.DPoint(t_cut_center_x_r - t_cut_total_length / 2 + self.t_cut_t_height, t_cut_center_y_list[i] + self.t_cut_t_width / 2),
            ]


            if i == 0:
                t_cut_l_region = pya.Region(pya.DPolygon(t_cut_pts_l).to_itype(self.layout.dbu))
                t_cut_r_region = pya.Region(pya.DPolygon(t_cut_pts_r).to_itype(self.layout.dbu))
            else:
                t_cut_l_region += pya.Region(pya.DPolygon(t_cut_pts_l).to_itype(self.layout.dbu))
                t_cut_r_region += pya.Region(pya.DPolygon(t_cut_pts_r).to_itype(self.layout.dbu))

            i += 1
        
        t_cut_region = t_cut_l_region + t_cut_r_region
        t_cut_region.round_corners(self.t_cut_radius / self.layout.dbu, self.t_cut_radius / self.layout.dbu, self.n)

        return t_cut_region

    def _make_meshing_region(self):
        buffer = 0.25*self.spike_region_width
        
        pts_l = [
                pya.DPoint(self.end_box_left + buffer, self.end_box_bottom),
                pya.DPoint(self.end_box_left - self.spike_region_width - buffer, self.end_box_bottom),
                pya.DPoint(self.end_box_left - self.spike_region_width - buffer, self.end_box_top),
                pya.DPoint(self.end_box_left + buffer, self.end_box_top),
                ]
        region_l = pya.Region(pya.DPolygon(pts_l).to_itype(self.layout.dbu))

        pts_r = [
                pya.DPoint(self.end_box_right - buffer, self.end_box_bottom),
                pya.DPoint(self.end_box_right + self.spike_region_width + buffer, self.end_box_bottom),
                pya.DPoint(self.end_box_right + self.spike_region_width + buffer, self.end_box_top),
                pya.DPoint(self.end_box_right - buffer, self.end_box_top),
                ]
        region_r = pya.Region(pya.DPolygon(pts_r).to_itype(self.layout.dbu))
        

        return region_r + region_l