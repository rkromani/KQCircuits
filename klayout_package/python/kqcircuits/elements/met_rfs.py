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


from os import path

from kqcircuits.elements.element import Element
from kqcircuits.pya_resolver import pya
from kqcircuits.util.parameters import Param, pdt, add_parameters_from
from kqcircuits.elements.waveguide_coplanar import WaveguideCoplanar
from kqcircuits.elements.coupled_inductor import CoupledInductor
from kqcircuits.elements.pomeroy_cap import PomeroyCap
from kqcircuits.junctions.rkr_bridge_junction_2 import RKRBridge2
from kqcircuits.util.refpoints import RefpointToInternalPort

import numpy as np
import math


@add_parameters_from(WaveguideCoplanar, "add_metal")
class MetRfs(Element):

    l_ground_cutout_width = Param(pdt.TypeDouble, "Width of ground cutout", 1300, unit="μm")
    l_ground_cutout_height = Param(pdt.TypeDouble, "Height of ground cutout", 1500, unit="μm")
    l_ground_radius = Param(pdt.TypeDouble, "Radius of ground cutout corners", 10, unit="μm")

    feedline_length = Param(pdt.TypeDouble, "Feedline length", 1600, unit="μm")
    feedline_spacing = Param(pdt.TypeDouble, "Feedline spacing", 10, unit="μm")
    feedline_coupling_ground_spacing = Param(pdt.TypeDouble, "Feedline coupling ground spacing", 20, unit="μm")
    feedline_cutout = Param(pdt.TypeDouble, "Feedline cutout length", 50, unit="μm")
    feedline_cutout_bool = Param(pdt.TypeBoolean, "Whether to add feedline cutout", False)

    l_tot_length = Param(pdt.TypeDouble, "Total length of inductor", 6000, unit="μm")
    l_coupling_length = Param(pdt.TypeDouble, "Length of inductor coupling region", 200, unit="μm")
    l_coupling_distance = Param(pdt.TypeDouble, "Distance between inductor and ground in coupling region", 40, unit="μm")
    l_width = Param(pdt.TypeDouble, "Inductor width", 4, unit="μm")
    l_radius = Param(pdt.TypeDouble, "Radius of inductor bends", 25, unit="μm")
    l_ground_sep = Param(pdt.TypeDouble, "Separation between inductor and ground cutout", 300, unit="μm")
    l_middle_sep = Param(pdt.TypeDouble, "Separation between one side and the other of the inductor", 300, unit="μm")
    l_connection_spacing = Param(pdt.TypeDouble, "Spacing between inductors two connections", 400, unit="μm")\

    met_bridge_width = Param(pdt.TypeDouble, "Width/thickness of the MET bridge", 0.15, unit="μm")
    met_bridge_length = Param(pdt.TypeDouble, "Length of the MET bridge", 4, unit="μm")
    met_length = Param(pdt.TypeDouble, "Length of the MET (pad to pad)", 12, unit="μm")
    met_pad_width = Param(pdt.TypeDouble, "Width of the MET pads", 15, unit="μm")
    met_pad_height = Param(pdt.TypeDouble, "Height of the MET pads", 10, unit="μm")
    met_ground_cutout_width = Param(pdt.TypeDouble, "Width of ground cutout for MET", 40, unit="μm")
    met_ground_cutout_height = Param(pdt.TypeDouble, "Height of ground cutout for MET", 50, unit="μm")
    met_ground_radius = Param(pdt.TypeDouble, "Radius of ground cutout corners for MET", 5, unit="μm")

    enable_mesh_layers = Param(pdt.TypeBoolean, "Enable mesh control layers for ANSYS", True)
    enable_rlc = Param(pdt.TypeBoolean, "Whether to add RLC elements for modeling", True)
    enable_feedline_termination = Param(pdt.TypeBoolean, "Whether to terminate the feedline with RLC sim elements", False)
    sim_gap = Param(pdt.TypeBoolean, "Gap for ACRL simulation", False)

    rlc_junction_c = Param(pdt.TypeDouble, "Junction capacitance for RLC model", 10, unit="fF")
    rlc_junction_l = Param(pdt.TypeDouble, "Junction inductance for RLC model", 10, unit="nH")
    rlc_junction_r = Param(pdt.TypeDouble, "Junction parallel resistance (0=lossless; Q_int=R/omega0/L)", 0, unit="Ohm")

    extra_cap_spacing = Param(pdt.TypeDouble, "Spacing between ground gap and extra capacitor", 5, unit="μm")
    extra_cap_height = Param(pdt.TypeDouble, "Height of extra capacitor pad", 80, unit="μm")

    n = Param(pdt.TypeInt, "Number of points for rounding", 64)

    def build(self):

        self.insert_cell(CoupledInductor, pya.DCplxTrans(1, 0, False, 0.0, 0.0), "main_inductor",
                         ground_cutout_height=self.l_ground_cutout_height,
                         ground_cutout_width=self.l_ground_cutout_width,
                         feedline_spacing=self.feedline_spacing,
                         feedline_coupling_ground_spacing=self.feedline_coupling_ground_spacing,
                         feedline_cutout=self.feedline_cutout,
                         feedline_cutout_bool=self.feedline_cutout_bool,
                         feedline_length=self.feedline_length, 
                         l_tot_length=self.l_tot_length,
                         l_coupling_length=self.l_coupling_length,
                         l_coupling_distance=self.l_coupling_distance,
                         l_width=self.l_width,
                         l_connection_spacing=self.l_connection_spacing,
                         enable_mesh_layers=self.enable_mesh_layers,
                         enable_feedline_termination=self.enable_feedline_termination,
                         n=self.n)

        self.l_ground_bottom = -self.l_ground_cutout_height -self.a/2 -self.b -self.feedline_coupling_ground_spacing

        met_center_x = self.l_connection_spacing/2 + self.met_length/2
        met_center_y = self.l_ground_bottom - self.extra_cap_height - self.met_ground_cutout_height/2
        coord = pya.DTrans(1, False, met_center_x, met_center_y)
        palm_width = 7
        taper_width = 10
        if not self.enable_rlc: 
            self.insert_cell(
                RKRBridge2, coord, f"JJ", 
                wiring_pad_bool=False,
                pad_height=self.met_pad_height, pad_width=self.met_pad_width, 
                pad_offset = self.met_length/2, 
                palm_width=palm_width, taper_base=taper_width, 
                bridge_length=self.met_bridge_length,
                bridge_width=self.met_bridge_width, 
                #pad_offset = self.cap_gap/2 + 1, 
                #taper_height = self.cap_gap/2, 
                taper_width = taper_width,
                #**element_params[i],
            )

        self.cap_ground_gap_left = self.l_connection_spacing/2 - self.met_ground_cutout_width + self.met_length
        self.cap_ground_gap_right = self.l_connection_spacing/2 + self.met_length
        pts_add_gap = [
            pya.DPoint(self.cap_ground_gap_left, self.l_ground_bottom),
            pya.DPoint(self.cap_ground_gap_left, self.l_ground_bottom - self.extra_cap_height - self.met_ground_cutout_height),
            pya.DPoint(self.cap_ground_gap_right, self.l_ground_bottom - self.extra_cap_height - self.met_ground_cutout_height),
            pya.DPoint(self.cap_ground_gap_right, self.l_ground_bottom),
        ]
        extra_gap_region = pya.DPolygon(pts_add_gap)
        extra_gap_region = pya.Region(extra_gap_region.to_itype(self.layout.dbu))

        pts_add_cap = [
            pya.DPoint(self.cap_ground_gap_left + self.extra_cap_spacing, self.l_ground_bottom),
            pya.DPoint(self.cap_ground_gap_left + self.extra_cap_spacing, self.l_ground_bottom - self.extra_cap_height),
            pya.DPoint(self.cap_ground_gap_right - self.extra_cap_spacing, self.l_ground_bottom - self.extra_cap_height),
            pya.DPoint(self.cap_ground_gap_right - self.extra_cap_spacing, self.l_ground_bottom),
        ]
        extra_cap_region = pya.DPolygon(pts_add_cap)
        extra_cap_region = pya.Region(extra_cap_region.to_itype(self.layout.dbu))

        met_wire_pts = [
            pya.DPoint(met_center_x - self.met_pad_height - self.met_length/2, self.l_ground_bottom - self.extra_cap_height),
            pya.DPoint(met_center_x - self.met_pad_height - self.met_length/2, met_center_y - self.met_pad_width/2),
            pya.DPoint(met_center_x - self.met_length/2, met_center_y - self.met_pad_width/2),
            pya.DPoint(met_center_x - self.met_length/2, self.l_ground_bottom - self.extra_cap_height),
        ]
        met_wire_region = pya.DPolygon(met_wire_pts)
        met_wire_region = pya.Region(met_wire_region.to_itype(self.layout.dbu))

        self.cell.shapes(self.get_layer("base_metal_gap_wo_grid")).insert(
            extra_gap_region - extra_cap_region - met_wire_region
        )

        rlc_junction_pts = [
            pya.DPoint(met_center_x - self.met_length, met_center_y - self.met_pad_width/2),
            pya.DPoint(met_center_x - self.met_length, met_center_y + self.met_pad_width/2),
            pya.DPoint(met_center_x + self.met_length, met_center_y + self.met_pad_width/2),
            pya.DPoint(met_center_x + self.met_length, met_center_y - self.met_pad_width/2),
        ]

        if self.enable_rlc:
            rlc_junction_region = pya.Region(pya.DPolygon(rlc_junction_pts).to_itype(self.layout.dbu))
        else:
            rlc_junction_region = pya.Region()

        self.cell.shapes(self.get_layer("lumped_rlc")).insert(
            rlc_junction_region
        )

        self.add_port("feedline_a", pya.DPoint(-self.feedline_length/2, 0), pya.DVector(-1, 0))
        self.add_port("feedline_b", pya.DPoint(self.feedline_length/2, 0), pya.DVector(1, 0))
        self.refpoints["feedline_a"] = pya.DPoint(-self.feedline_length/2, 0)
        self.refpoints["feedline_b"] = pya.DPoint(self.feedline_length/2, 0)
        
        self.refpoints["rlc_junction_signal"] = pya.DPoint(met_center_x - self.met_length, met_center_y)
        self.refpoints["rlc_junction_ground"] = pya.DPoint(met_center_x + self.met_length, met_center_y)

