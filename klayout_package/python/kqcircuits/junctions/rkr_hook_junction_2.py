# This code is part of KQCircuits
# Copyright (C) 2025 Zachary Parrott
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


from math import sqrt
import numpy as np
from kqcircuits.pya_resolver import pya
from kqcircuits.util.parameters import Param, pdt
from kqcircuits.junctions.junction import Junction
from kqcircuits.util.symmetric_polygons import polygon_with_vsym, polygon_with_hsym
from kqcircuits.defaults import default_layers


class RKRHook2(Junction):
    """The PCell declaration for a test single junction.
    """
    pad_width = Param(pdt.TypeDouble, "Width of pad connecting to the circuit", 10, unit="μm")
    pad_height = Param(pdt.TypeDouble, "Height of pad connecting to the circuit", 5, unit="μm")
    pad_offset = Param(pdt.TypeDouble, "Distance from junction center to pad", 5, unit="μm")
    
    bridge_width = Param(pdt.TypeDouble, "Width of bridge separating the finger and hook", 0.15, unit="μm")
    bridge_length = Param(pdt.TypeDouble, "Length of bridge separating the finger and hook, i.e. the finger thickness", 0.2, unit="μm")

    hook_width = Param(pdt.TypeDouble, "Width of hook", 0.2, unit="μm")
    hook_overshoot = Param(pdt.TypeDouble, "Distance between finger center and end of hook", 1, unit="μm")

    lead_offset = Param(pdt.TypeDouble, "Distance between center and hook/finger leads", 1, unit="μm")
    
    taper_base = Param(pdt.TypeDouble, "Width of base of taper", 3, unit="μm")
    taper_height = Param(pdt.TypeDouble, "Height of taper", 3, unit="μm")
    
    shadow_angle_1 = Param(pdt.TypeDouble, "Angle of shadow 1", 45, unit="deg")
    shadow_angle_2 = Param(pdt.TypeDouble, "Angle of shadow 2", -45, unit="deg")
    resist_thickness = Param(pdt.TypeDouble, "Thickness of resist", 0.385, unit="μm")

    t_cut_body_width = Param(pdt.TypeDouble, "Width of T-cut", 4, unit="μm")
    t_cut_distance_from_front = Param(pdt.TypeDouble, "Distance of T-cut from front of Al deposition", 2, unit="μm")
    t_cut_t_width = Param(pdt.TypeDouble, "Width of T-cut T", 6, unit="μm")
    t_cut_t_height = Param(pdt.TypeDouble, "Height of T-cut T", 2, unit="μm")

    wiring_pad_bool = Param(pdt.TypeBoolean, "Whether to include wiring layer pads", False)
    wiring_pad_width = Param(pdt.TypeDouble, "Width of wiring layer pads", 200, unit="μm")
    wiring_pad_height = Param(pdt.TypeDouble, "Height of wiring layer pads", 200, unit="μm")
    wiring_pad_gap = Param(pdt.TypeDouble, "Gap between wiring layer pads and ground plane", 25, unit="μm")

    def build(self, **kwargs):
        ebeam_shape = self.get_ebeam_shape()
        self.cell.shapes(self.get_layer("SIS_junction")).insert(ebeam_shape)

        deposition_shape = self.get_deposited_shape()
        self.cell.shapes(self.get_layer("SIS_shadow")).insert(deposition_shape)

        if self.wiring_pad_bool:
            wiring_pad_shape = self.get_wiring_pad_shape()
            t_cut_combined = self.get_t_cut_shape()
            self.cell.shapes(self.get_layer("base_metal_gap_wo_grid")).insert(wiring_pad_shape+t_cut_combined)
        else:
            t_cut_combined = self.get_t_cut_shape()
            self.cell.shapes(self.get_layer("base_metal_gap_wo_grid")).insert(t_cut_combined)

    def get_ebeam_shape(self):
        pad_top_pts = [
            pya.DPoint(self.pad_width/2, self.pad_offset),
            pya.DPoint(-self.pad_width/2, self.pad_offset),
            pya.DPoint(-self.pad_width/2, self.pad_offset + self.pad_height),
            pya.DPoint(self.pad_width/2, self.pad_offset + self.pad_height),
        ]
        pad_top_region = pya.Region(pya.DPolygon(pad_top_pts).to_itype(self.layout.dbu))
        
        pad_bottom_pts = [
            pya.DPoint(self.pad_width/2, -self.pad_offset),
            pya.DPoint(-self.pad_width/2, -self.pad_offset),
            pya.DPoint(-self.pad_width/2, -self.pad_offset - self.pad_height),
            pya.DPoint(self.pad_width/2, -self.pad_offset - self.pad_height),
        ]
        pad_bottom_region = pya.Region(pya.DPolygon(pad_bottom_pts).to_itype(self.layout.dbu))

        pads_region = pad_top_region + pad_bottom_region
        

        finger_left = self.lead_offset - self.bridge_length/2
        finger_right = self.lead_offset + self.bridge_length/2
        finger_top = -self.bridge_width/2
        finger_taper_left = self.lead_offset - self.taper_base/2
        finger_taper_right = self.lead_offset + self.taper_base/2
        finger_taper_top = -self.pad_offset + self.taper_height
        finger_pts = [
            pya.DPoint(finger_taper_left, -self.pad_offset),
            pya.DPoint(finger_left, finger_taper_top),
            pya.DPoint(finger_left, finger_top),
            pya.DPoint(finger_right, finger_top),
            pya.DPoint(finger_right, finger_taper_top),
            pya.DPoint(finger_taper_right, -self.pad_offset),
        ]
        finger_region = pya.Region(pya.DPolygon(finger_pts).to_itype(self.layout.dbu))

        hook_left = -self.lead_offset - self.hook_width/2
        hook_right = -self.lead_offset + self.hook_width/2
        hook_end = self.lead_offset + self.hook_overshoot
        hook_bottom = self.bridge_width/2
        hook_top = self.bridge_width/2 + self.hook_width
        hook_taper_bottom = self.pad_offset - self.taper_height
        hook_taper_left = -self.lead_offset - self.taper_base/2
        hook_taper_right = -self.lead_offset + self.taper_base/2
        hook_pts = [
            pya.DPoint(hook_taper_left, self.pad_offset),
            pya.DPoint(hook_left, hook_taper_bottom),
            pya.DPoint(hook_left, hook_bottom),
            pya.DPoint(hook_end, hook_bottom),
            pya.DPoint(hook_end, hook_top),
            pya.DPoint(hook_right, hook_top),
            pya.DPoint(hook_right, hook_taper_bottom),
            pya.DPoint(hook_taper_right, self.pad_offset),
        ]
        hook_region = pya.Region(pya.DPolygon(hook_pts).to_itype(self.layout.dbu))

        ebeam_region = pads_region + finger_region + hook_region
        ebeam_region.merge()
        return ebeam_region
    
    def get_deposited_shape(self):
        ebeam_region = self.get_ebeam_shape()

        y_shift_1 = self.resist_thickness * np.tan(np.radians(self.shadow_angle_1))
        y_shift_2 = self.resist_thickness * np.tan(np.radians(self.shadow_angle_2))
        shift_1_y_dbu = y_shift_1 / self.layout.dbu
        shift_2_y_dbu = y_shift_2 / self.layout.dbu

        trans_1 = pya.DTrans(0, False, 0, int(shift_1_y_dbu))
        trans_2 = pya.DTrans(0, False, 0, int(shift_2_y_dbu))

        shadow_1 = ebeam_region.transformed(trans_1)
        shadow_2 = ebeam_region.transformed(trans_2)

        return shadow_1 + shadow_2
    
    def get_t_cut_shape(self):
        t_cut_body_top = self.pad_offset + self.t_cut_distance_from_front
        t_cut_body_bottom = -self.pad_offset - self.t_cut_distance_from_front
        t_cut_t_top = self.pad_offset + self.t_cut_t_height + self.t_cut_distance_from_front
        t_cut_t_bottom = -self.pad_offset - self.t_cut_t_height - self.t_cut_distance_from_front
        t_cut_t_left = -self.t_cut_t_width/2
        t_cut_t_right = self.t_cut_t_width/2
        t_cut_body_left = -self.t_cut_body_width/2
        t_cut_body_right = self.t_cut_body_width/2

        t_cut_pts = [
            pya.DPoint(t_cut_t_right, t_cut_t_top),
            pya.DPoint(t_cut_t_right, t_cut_body_top),
            pya.DPoint(t_cut_body_right, t_cut_body_top),
            pya.DPoint(t_cut_body_right, t_cut_body_bottom),
            pya.DPoint(t_cut_t_right, t_cut_body_bottom),
            pya.DPoint(t_cut_t_right, t_cut_t_bottom),
            pya.DPoint(t_cut_t_left, t_cut_t_bottom),
            pya.DPoint(t_cut_t_left, t_cut_body_bottom),
            pya.DPoint(t_cut_body_left, t_cut_body_bottom),
            pya.DPoint(t_cut_body_left, t_cut_body_top),
            pya.DPoint(t_cut_t_left, t_cut_body_top),
            pya.DPoint(t_cut_t_left, t_cut_t_top),
        ]


        t_cut = pya.Region(pya.DPolygon(t_cut_pts).to_itype(self.layout.dbu))
        return t_cut


    def get_wiring_pad_shape(self):
        gap_pts = [
            pya.DPoint(self.wiring_pad_width/2 + self.wiring_pad_gap, -self.pad_offset - self.wiring_pad_height - self.wiring_pad_gap),
            pya.DPoint(-self.wiring_pad_width/2 - self.wiring_pad_gap, -self.pad_offset - self.wiring_pad_height - self.wiring_pad_gap),
            pya.DPoint(-self.wiring_pad_width/2 - self.wiring_pad_gap, self.pad_offset + self.wiring_pad_height + self.wiring_pad_gap),
            pya.DPoint(self.wiring_pad_width/2 + self.wiring_pad_gap, self.pad_offset + self.wiring_pad_height + self.wiring_pad_gap),
        ]

        pad_top_pts = [
            pya.DPoint(self.wiring_pad_width/2, self.pad_offset),
            pya.DPoint(-self.wiring_pad_width/2, self.pad_offset),
            pya.DPoint(-self.wiring_pad_width/2, self.pad_offset + self.wiring_pad_height),
            pya.DPoint(self.wiring_pad_width/2, self.pad_offset + self.wiring_pad_height),
        ]
        
        pad_bottom_pts = [
            pya.DPoint(self.wiring_pad_width/2, -self.pad_offset),
            pya.DPoint(-self.wiring_pad_width/2, -self.pad_offset),
            pya.DPoint(-self.wiring_pad_width/2, -self.pad_offset - self.wiring_pad_height),
            pya.DPoint(self.wiring_pad_width/2, -self.pad_offset - self.wiring_pad_height),
        ]

        gap_region = pya.Region(pya.DPolygon(gap_pts).to_itype(self.layout.dbu))
        wiring_pad_top_region = pya.Region(pya.DPolygon(pad_top_pts).to_itype(self.layout.dbu))
        wiring_pad_bottom_region = pya.Region(pya.DPolygon(pad_bottom_pts).to_itype(self.layout.dbu))
        wiring_pads = wiring_pad_top_region + wiring_pad_bottom_region

        return gap_region - wiring_pads

