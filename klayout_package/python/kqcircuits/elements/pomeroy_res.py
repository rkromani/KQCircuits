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
from kqcircuits.util.refpoints import RefpointToInternalPort

import numpy as np
import math


@add_parameters_from(WaveguideCoplanar, "add_metal")
class PomeroyRes(Element):

    l_ground_cutout_width = Param(pdt.TypeDouble, "Width of ground cutout", 600, unit="μm")
    l_ground_cutout_height = Param(pdt.TypeDouble, "Height of ground cutout", 1000, unit="μm")
    l_ground_radius = Param(pdt.TypeDouble, "Radius of ground cutout corners", 10, unit="μm")

    feedline_length = Param(pdt.TypeDouble, "Feedline length", 1600, unit="μm")
    feedline_spacing = Param(pdt.TypeDouble, "Feedline spacing", 10, unit="μm")
    feedline_coupling_ground_spacing = Param(pdt.TypeDouble, "Feedline coupling ground spacing", 10, unit="μm")
    feedline_cutout = Param(pdt.TypeDouble, "Feedline cutout length", 50, unit="μm")
    feedline_cutout_bool = Param(pdt.TypeBoolean, "Whether to add feedline cutout", False)

    l_tot_length = Param(pdt.TypeDouble, "Total length of inductor", 5000, unit="μm")
    l_coupling_length = Param(pdt.TypeDouble, "Length of inductor coupling region", 150, unit="μm")
    l_coupling_distance = Param(pdt.TypeDouble, "Distance between inductor and ground in coupling region", 10, unit="μm")
    l_width = Param(pdt.TypeDouble, "Inductor width", 4, unit="μm")
    l_radius = Param(pdt.TypeDouble, "Radius of inductor bends", 25, unit="μm")
    l_ground_sep = Param(pdt.TypeDouble, "Separation between inductor and ground cutout", 100, unit="μm")
    l_middle_sep = Param(pdt.TypeDouble, "Separation between one side and the other of the inductor", 100, unit="μm")
    l_connection_spacing = Param(pdt.TypeDouble, "Spacing between inductors two connections", 200, unit="μm")

    enable_mesh_layers = Param(pdt.TypeBoolean, "Enable mesh control layers for ANSYS", True)
    enable_feedline_termination = Param(pdt.TypeBoolean, "Whether to terminate the feedline with RLC sim elements", False)
    sim_gap = Param(pdt.TypeBoolean, "Gap for ACRL simulation", False)

    c_ground_cutout_width = Param(pdt.TypeDouble, "Width of ground cutout", 100, unit="μm")
    c_ground_cutout_height = Param(pdt.TypeDouble, "Height of ground cutout", 100, unit="μm")
    c_ground_radius = Param(pdt.TypeDouble, "Radius of ground cutout corners", 5, unit="μm")

    cap_width = Param(pdt.TypeDouble, "Width of capacitor body", 10, unit="μm")
    cap_height = Param(pdt.TypeDouble, "Height of capacitor body", 10, unit="μm")

    lead_length = Param(pdt.TypeDouble, "Length of capacitor leads defined in e beam", 15, unit="μm")
    lead_width = Param(pdt.TypeDouble, "Width of capacitor leads defined in e beam", 0.1, unit="μm")

    connection_leg_length = Param(pdt.TypeDouble, "Length of legs on the wiring layer in the connection region", 5, unit="μm")
    connection_leg_width = Param(pdt.TypeDouble, "Width of legs on the wiring layer in the connection region", 4, unit="μm")
    connection_leg_offset = Param(pdt.TypeDouble, "Offset between the connection regions in the e beam and wiring layer, wiring layer is thinner", 1, unit="μm")
    connection_leadin_length = Param(pdt.TypeDouble, "Length of leadin wires on the wiring layer from ground gap to connection region", 20, unit="μm")

    include_ebeam = Param(pdt.TypeBoolean, "Whether to include the e beam capacitor definition layer", True)

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

        self.insert_cell(PomeroyCap, pya.DCplxTrans(1, 180, False, self.l_connection_spacing/2,
                                                     self.l_ground_bottom-self.connection_leg_length-self.lead_length - self.extra_cap_height), "main_cap",
                         ground_cutout_height=self.c_ground_cutout_height,
                         ground_cutout_width=self.c_ground_cutout_width,
                         cap_width=self.cap_width,
                         cap_height=self.cap_height,
                         lead_length=self.lead_length,
                         lead_width=self.lead_width,
                         connection_leg_length=self.connection_leg_length,
                         connection_leg_width=self.connection_leg_width,
                         connection_leg_offset=self.connection_leg_offset,
                         connection_leadin_length=self.connection_leadin_length,
                         include_ebeam=self.include_ebeam, 
                         enable_mesh_layers=self.enable_mesh_layers,
                         enable_feedline_termination=self.enable_feedline_termination,
                         n=self.n)

        self.cap_ground_gap_left = self.l_connection_spacing/2 - self.c_ground_cutout_width + self.lead_length + self.connection_leadin_length
        self.cap_ground_gap_right = self.l_connection_spacing/2 + self.lead_length + self.connection_leadin_length
        pts_add_gap = [
            pya.DPoint(self.cap_ground_gap_left, self.l_ground_bottom),
            pya.DPoint(self.cap_ground_gap_left, self.l_ground_bottom - self.extra_cap_height),
            pya.DPoint(self.cap_ground_gap_right, self.l_ground_bottom - self.extra_cap_height),
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

        self.cell.shapes(self.get_layer("base_metal_gap_wo_grid")).insert(
            extra_gap_region - extra_cap_region
        )

        """self.cell.shapes(self.get_layer("SIS_junction")).insert(
            
        )"""


        self.add_port("feedline_a", pya.DPoint(-self.feedline_length/2, 0), pya.DVector(-1, 0))
        self.add_port("feedline_b", pya.DPoint(self.feedline_length/2, 0), pya.DVector(1, 0))
        self.refpoints["feedline_a"] = pya.DPoint(-self.feedline_length/2, 0)
        self.refpoints["feedline_b"] = pya.DPoint(self.feedline_length/2, 0)

