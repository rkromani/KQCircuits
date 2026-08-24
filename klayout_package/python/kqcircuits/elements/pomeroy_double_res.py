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
from kqcircuits.elements.waveguide_coplanar_splitter import WaveguideCoplanarSplitter, t_cross_parameters
from kqcircuits.elements.coupled_inductor import CoupledInductor
from kqcircuits.elements.pomeroy_cap import PomeroyCap
from kqcircuits.elements.waveguide_composite import WaveguideComposite, Node
from kqcircuits.util.refpoints import RefpointToInternalPort

import numpy as np
import math


@add_parameters_from(WaveguideCoplanar, "add_metal")
class PomeroyDoubleRes(Element):

    l_ground_cutout_width = Param(pdt.TypeDouble, "Width of ground cutout", 1100, unit="μm")
    l_ground_cutout_height = Param(pdt.TypeDouble, "Height of ground cutout", 1000, unit="μm")
    l_ground_radius = Param(pdt.TypeDouble, "Radius of ground cutout corners", 10, unit="μm")

    feedline_length = Param(pdt.TypeDouble, "Feedline length", 1600, unit="μm")
    feedline_spacing = Param(pdt.TypeDouble, "Feedline spacing", 10, unit="μm")
    feedline_coupling_ground_spacing = Param(pdt.TypeDouble, "Feedline coupling ground spacing", 10, unit="μm")
    feedline_cutout = Param(pdt.TypeDouble, "Feedline cutout length", 50, unit="μm")
    feedline_cutout_bool = Param(pdt.TypeBoolean, "Whether to add feedline cutout", False)

    l_tot_length = Param(pdt.TypeDouble, "Total length of inductor", 10000, unit="μm")
    l_coupling_length = Param(pdt.TypeDouble, "Length of inductor coupling region", 600, unit="μm")
    l_coupling_distance = Param(pdt.TypeDouble, "Distance between inductor and ground in coupling region", 10, unit="μm")
    l_width = Param(pdt.TypeDouble, "Inductor width", 4, unit="μm")
    l_radius = Param(pdt.TypeDouble, "Radius of inductor bends", 25, unit="μm")
    l_ground_sep = Param(pdt.TypeDouble, "Separation between inductor and ground cutout", 100, unit="μm")
    l_middle_sep = Param(pdt.TypeDouble, "Separation between one side and the other of the inductor", 100, unit="μm")
    l_connection_spacing = Param(pdt.TypeDouble, "Spacing between inductors two connections", 600, unit="μm")

    enable_mesh_layers = Param(pdt.TypeBoolean, "Enable mesh control layers for ANSYS", True)
    enable_feedline_termination = Param(pdt.TypeBoolean, "Whether to terminate the feedline with RLC sim elements", False)
    sim_gap = Param(pdt.TypeBoolean, "Gap for ACRL simulation", False)

    c_ground_cutout_width = Param(pdt.TypeDouble, "Width of ground cutout", 80, unit="μm")
    c_ground_cutout_height = Param(pdt.TypeDouble, "Height of ground cutout", 80, unit="μm")
    c_ground_radius = Param(pdt.TypeDouble, "Radius of ground cutout corners", 5, unit="μm")

    cap_width = Param(pdt.TypeDouble, "Width of capacitor body", 1.5, unit="μm")
    cap_height = Param(pdt.TypeDouble, "Height of capacitor body", 1.5, unit="μm")

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

        c1_x = self.l_connection_spacing/2 + self.c_ground_cutout_width*1.5
        c2_x = self.l_connection_spacing/2 - self.c_ground_cutout_width*1.5
        c3_x = -self.l_connection_spacing/2 + self.c_ground_cutout_width*1.5
        c4_x = -self.l_connection_spacing/2 - self.c_ground_cutout_width*1.5
        c_y = self.l_ground_bottom + self.connection_leg_width + self.connection_leg_offset - self.connection_leadin_length*5 - self.connection_leg_length - self.lead_length

        self.insert_cell(PomeroyCap, pya.DCplxTrans(1, 180, False, c1_x, c_y), "c1",
                         ground_cutout_height=self.c_ground_cutout_height,
                         ground_cutout_width=self.c_ground_cutout_width,
                         #ground_radius=0,
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
        
        self.insert_cell(PomeroyCap, pya.DCplxTrans(1, 180, False, c2_x, c_y), "c2",
                         ground_cutout_height=self.c_ground_cutout_height,
                         ground_cutout_width=self.c_ground_cutout_width,
                         #ground_radius=0,
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
        
        self.insert_cell(PomeroyCap, pya.DCplxTrans(1, 180, False, c3_x, c_y), "c3",
                         ground_cutout_height=self.c_ground_cutout_height,
                         ground_cutout_width=self.c_ground_cutout_width,
                         #ground_radius=0,
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
        
        self.insert_cell(PomeroyCap, pya.DCplxTrans(1, 180, False, c4_x, c_y), "c4",
                         ground_cutout_height=self.c_ground_cutout_height,
                         ground_cutout_width=self.c_ground_cutout_width,
                         #ground_radius=0,
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
        
        self.insert_cell(WaveguideCoplanarSplitter,
            pya.DTrans(2, False, self.l_connection_spacing/2, self.l_ground_bottom - self.b*4 - self.l_width/2),
            f"TR",
            **t_cross_parameters(
                a=self.l_width,
                b=self.b*4,
                a2=self.l_width,
                b2=self.b*4,
                length_extra=5,
                length_extra_side=5
            )
        )
        self.insert_cell(
            WaveguideComposite, 
            nodes=[
                Node(self.refpoints["TR_port_left"]),
                Node((self.refpoints["c1_cap_b"].x, self.refpoints["TR_port_left"].y)),
                Node(self.refpoints["c1_cap_b"])
            ],
            b=self.b*4,
            a=self.l_width, 
            r=self.b, 
        )
        self.insert_cell(
            WaveguideComposite, 
            nodes=[
                Node(self.refpoints["TR_port_right"]),
                Node((self.refpoints["c2_cap_b"].x, self.refpoints["TR_port_left"].y)),
                Node(self.refpoints["c2_cap_b"])
            ],
            b=self.b*4,
            a=self.l_width, 
            r=self.b, 
        )

        self.insert_cell(WaveguideCoplanarSplitter,
            pya.DTrans(2, False, -self.l_connection_spacing/2, self.l_ground_bottom - self.b*4 - self.l_width/2),
            f"TL",
            **t_cross_parameters(
                a=self.l_width,
                b=self.b*4,
                a2=self.l_width,
                b2=self.b*4,
                length_extra=5,
                length_extra_side=5
            )
        )
        self.insert_cell(
            WaveguideComposite, 
            nodes=[
                Node(self.refpoints["TL_port_left"]),
                Node((self.refpoints["c3_cap_b"].x, self.refpoints["TL_port_left"].y)),
                Node(self.refpoints["c3_cap_b"])
            ],
            b=self.b*4,
            a=self.l_width, 
            r=self.b, 
        )
        self.insert_cell(
            WaveguideComposite, 
            nodes=[
                Node(self.refpoints["TL_port_right"]),
                Node((self.refpoints["c4_cap_b"].x, self.refpoints["TL_port_left"].y)),
                Node(self.refpoints["c4_cap_b"])
            ],
            b=self.b*4,
            a=self.l_width, 
            r=self.b, 
        )

        self.insert_cell(WaveguideCoplanarSplitter,
            pya.DTrans(0, False, 0, c_y - self.connection_leadin_length*5),
            f"TB",
            **t_cross_parameters(
                a=self.l_width,
                b=self.b*4,
                a2=self.l_width,
                b2=self.b*4,
                length_extra=5,
                length_extra_side=5
            )
        )
        self.insert_cell(
            WaveguideComposite, 
            nodes=[
                Node(self.refpoints["TB_port_left"]),
                Node(((self.refpoints["c3_cap_a"].x + self.refpoints["TB_port_left"].x)/2, self.refpoints["TB_port_left"].y)),
                Node(((self.refpoints["c3_cap_a"].x + self.refpoints["TB_port_left"].x)/2, self.refpoints["c3_cap_a"].y)),
                Node(self.refpoints["c3_cap_a"])
            ],
            b=self.b*4,
            a=self.l_width, 
            r=self.b, 
        )
        self.insert_cell(
            WaveguideComposite, 
            nodes=[
                Node(self.refpoints["TB_port_right"]),
                Node((self.refpoints["c2_cap_a"].x + self.connection_leadin_length, self.refpoints["TB_port_left"].y)),
                Node((self.refpoints["c2_cap_a"].x + self.connection_leadin_length, self.refpoints["c2_cap_a"].y)),
                Node(self.refpoints["c2_cap_a"])
            ],
            b=self.b*4,
            a=self.l_width, 
            r=self.b, 
        )
        

        """self.cell.shapes(self.get_layer("base_metal_gap_wo_grid")).insert(
            extra_gap_r_region
        )"""

        """self.cell.shapes(self.get_layer("SIS_junction")).insert(
            
        )"""


        self.add_port("feedline_a", pya.DPoint(-self.feedline_length/2, 0), pya.DVector(-1, 0))
        self.add_port("feedline_b", pya.DPoint(self.feedline_length/2, 0), pya.DVector(1, 0))
        self.refpoints["feedline_a"] = pya.DPoint(-self.feedline_length/2, 0)
        self.refpoints["feedline_b"] = pya.DPoint(self.feedline_length/2, 0)
        self.refpoints["bias"] = self.refpoints["TB_port_bottom"]

