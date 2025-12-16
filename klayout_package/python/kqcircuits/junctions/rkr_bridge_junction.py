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


class RKRBridge(Junction):
    """The PCell declaration for a test single junction.
    """
    pad_width = Param(pdt.TypeDouble, "Width of pad connecting to to circuit", 10, unit="μm")
    pad_height = Param(pdt.TypeDouble, "Height of pad connecting to to circuit", 5, unit="μm")
    
    base_length = Param(pdt.TypeDouble, "Length of junction base", 5, unit="μm")
    
    finger_length = Param(pdt.TypeDouble, "Length of junction finger", 5, unit="μm")
    finger_tip_length = Param(pdt.TypeDouble, "Length of junction finger tip", 2, unit="μm")
    finger_width = Param(pdt.TypeDouble, "Width of junction finger a.k.a. bridge length", 0.1, unit="μm")
    finger_taper_base_width = Param(pdt.TypeDouble, "Width of junction finger taper at base", 5, unit="μm")
    
    #bridge_width = Param(pdt.TypeDouble, "Width of bridge connecting junction fingers", 1.5, unit="μm")
    junction_length = Param(pdt.TypeDouble, "Length of junction", 0.1, unit="μm")
    
    shadow_angle = Param(pdt.TypeDouble, "Angle of shadow", 30, unit="deg")
    resist_thickness = Param(pdt.TypeDouble, "Thickness of resist", 3, unit="μm")

    def build(self, **kwargs):

        default_layers["SIS_junction_area"] = pya.LayerInfo(138, 0, "SIS_junction_area")

        angle_extension = 2*self.resist_thickness * np.sin(np.radians(self.shadow_angle))
        self.bridge_width = angle_extension - self.junction_length

        self.total_junction_height = self.pad_height + self.base_length + self.finger_length + self.finger_tip_length + self.bridge_width

        junction_shape = self.get_junction_shape()
        self.cell.shapes(self.get_layer("SIS_junction")).insert(junction_shape)

        junction_shadow = self.get_junction_shadow()
        self.cell.shapes(self.get_layer("SIS_shadow")).insert(junction_shadow)

        junction_combined = (junction_shape + junction_shadow).merge()
        self.cell.shapes(self.get_layer("SIS_junction_2")).insert(junction_combined)

    def get_junction_shape(self):
        finger_shape = self.get_finger_shape()
        base_shape = self.get_base_shape()
        return finger_shape + base_shape
    
    def get_junction_shadow(self):
        shift_y = -1 * self.resist_thickness * np.sin(np.radians(self.shadow_angle))
        shift_y_dbu = shift_y / self.layout.dbu

        finger_shape = self.get_finger_shape()
        base_shape = self.get_base_shape()

        trans_1 = pya.DTrans(0, False, 0, int(shift_y_dbu))
        trans_2 = pya.DTrans(0, False, 0, int(-shift_y_dbu))

        shadow_1 = (finger_shape + base_shape).transformed(trans_1)
        shadow_2 = (finger_shape + base_shape).transformed(trans_2)

        return shadow_1 + shadow_2
    
    def get_finger_shape(self):
            finger_pts = [
                pya.DPoint(- self.pad_width / 2, self.total_junction_height),
                pya.DPoint(self.pad_width / 2, self.total_junction_height),
                pya.DPoint(self.pad_width / 2, self.total_junction_height - self.pad_height),
                pya.DPoint(self.finger_taper_base_width / 2, self.total_junction_height - self.pad_height),
                pya.DPoint(self.finger_width / 2, self.total_junction_height - self.pad_height - self.finger_length),
                pya.DPoint(self.finger_width / 2, self.total_junction_height - self.pad_height - self.finger_length - self.finger_tip_length),
                pya.DPoint(- self.finger_width / 2, self.total_junction_height - self.pad_height - self.finger_length - self.finger_tip_length),
                pya.DPoint(- self.finger_width / 2, self.total_junction_height - self.pad_height - self.finger_length),
                pya.DPoint(- self.finger_taper_base_width / 2, self.total_junction_height - self.pad_height),
                pya.DPoint(- self.pad_width / 2, self.total_junction_height - self.pad_height),
            ] 

            return pya.Region(pya.DPolygon(finger_pts).to_itype(self.layout.dbu))

    def get_base_shape(self):
            base_pts = [
                pya.DPoint(- self.pad_width / 2, 0),
                pya.DPoint(self.pad_width / 2, 0),
                pya.DPoint(self.pad_width / 2, self.base_length),
                pya.DPoint(- self.pad_width / 2, self.base_length),
            ] 

            return pya.Region(pya.DPolygon(base_pts).to_itype(self.layout.dbu))




