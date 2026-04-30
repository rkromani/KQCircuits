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
from kqcircuits.elements.finger_capacitor_ground_v3 import FingerCapacitorGroundV3
from kqcircuits.junctions.rkr_hook_junction import RKRHook
from kqcircuits.util.refpoints import RefpointToInternalPort

import numpy as np
import math


@add_parameters_from(WaveguideCoplanar, "add_metal")
class BiasResonator4(Element):
    l_ground_cutout_height = Param(pdt.TypeDouble, "Height of ground cutout for inductor", 1000, unit="μm")
    l_ground_cutout_width = Param(pdt.TypeDouble, "Width of ground cutout for inductor", 1000, unit="μm")

    feedline_spacing = Param(pdt.TypeDouble, "Feedline spacing", 10, unit="μm")
    feedline_coupling_ground_spacing = Param(pdt.TypeDouble, "Feedline coupling ground spacing", 5, unit="μm")
    feedline_cutout = Param(pdt.TypeDouble, "Feedline cutout length", 50, unit="μm")
    feedline_cutout_bool = Param(pdt.TypeBoolean, "Whether to add feedline cutout", True)
    
    l_tot_length = Param(pdt.TypeDouble, "Total length of inductor", 9000, unit="μm")
    l_coupling_length = Param(pdt.TypeDouble, "Length of inductor coupling region", 80, unit="μm")
    l_coupling_distance = Param(pdt.TypeDouble, "Distance between inductor and ground in coupling region", 5, unit="μm")
    l_width = Param(pdt.TypeDouble, "Inductor width", 4, unit="μm")
    l_connection_spacing = Param(pdt.TypeDouble, "Spacing between inductors two connections", 600, unit="μm")

    c_gap = Param(pdt.TypeDouble, "Capacitor gap", 20, unit="μm")
    c_width = Param(pdt.TypeDouble, "Capacitor pad width", 200, unit="μm")
    c_length = Param(pdt.TypeDouble, "Capacitor pad length", 200, unit="μm")
    c_ground_spacing = Param(pdt.TypeDouble, "Spacing from capacitor pad to ground gap", 50, unit="μm")

    gc_fingers_number = Param(pdt.TypeInt, "Number of fingers in grounding capacitor", 40)
    gc_fingers_length = Param(pdt.TypeDouble, "Length of fingers in grounding capacitor", 400, unit="μm")
    gc_fingers_gap = Param(pdt.TypeDouble, "Gap in grounding capacitor", 4, unit="μm")
    gc_fingers_width = Param(pdt.TypeDouble, "Width of fingers in grounding capacitor", 15, unit="μm")


    enable_mesh_layers = Param(pdt.TypeBoolean, "Enable mesh control layers for ANSYS", True)
    enable_feedline_termination = Param(pdt.TypeBoolean, "Whether to terminate the feedline with RLC sim elements", True)
    enable_gc_termination = Param(pdt.TypeBoolean, "Whether to terminate the grounding capacitor with RLC sim elements", True)

    n = Param(pdt.TypeInt, "Number of points for rounding", 64)

    def build(self):

        self.insert_cell(CoupledInductor, pya.DCplxTrans(1, 0, False, 0.0, 0.0), "main_inductor",
                         ground_cutout_height=self.l_ground_cutout_height,
                         ground_cutout_width=self.l_ground_cutout_width,
                         feedline_spacing=self.feedline_spacing,
                         feedline_coupling_ground_spacing=self.feedline_coupling_ground_spacing,
                         feedline_cutout=self.feedline_cutout,
                         feedline_cutout_bool=self.feedline_cutout_bool,
                         l_tot_length=self.l_tot_length,
                         l_coupling_length=self.l_coupling_length,
                         l_coupling_distance=self.l_coupling_distance,
                         l_width=self.l_width,
                         l_connection_spacing=self.l_connection_spacing,
                         enable_mesh_layers=self.enable_mesh_layers,
                         enable_feedline_termination=self.enable_feedline_termination,
                         n=self.n)
        
        self.ground_gap_top = -(self.a/2 + self.b + self.feedline_coupling_ground_spacing)
        self.ground_gap_bottom = self.ground_gap_top - self.l_ground_cutout_height
        
        self.insert_cell(FingerCapacitorGroundV3, pya.DCplxTrans(1, 0, False, self.l_connection_spacing/2, self.ground_gap_bottom), "grounding_cap",
                        finger_number=self.gc_fingers_number,
                        finger_length=self.gc_fingers_length,
                        finger_gap=self.gc_fingers_gap,
                        finger_width=self.gc_fingers_width,
                        a=self.a, b=self.b, n=self.n)

        ground_cutout_cap_pts = [
            pya.DPoint(-self.l_connection_spacing/2 + self.l_width/2 + self.c_gap, self.ground_gap_bottom),
            pya.DPoint(-self.l_connection_spacing/2 - self.l_width/2 - self.c_gap, self.ground_gap_bottom),
            pya.DPoint(-self.l_connection_spacing/2 - self.l_width/2 - self.c_gap, self.ground_gap_bottom - self.c_ground_spacing),
            pya.DPoint(-self.l_connection_spacing/2 + self.l_width/2 - self.c_gap - self.c_width, self.ground_gap_bottom - self.c_ground_spacing),
            pya.DPoint(-self.l_connection_spacing/2 + self.l_width/2 - self.c_gap - self.c_width, self.ground_gap_bottom - self.c_ground_spacing - 2*self.c_gap - self.c_length),
            pya.DPoint(-self.l_connection_spacing/2 + self.l_width/2 + self.c_gap, self.ground_gap_bottom - self.c_ground_spacing - 2*self.c_gap - self.c_length),
        ]
        ground_cutout_cap = pya.DPolygon(ground_cutout_cap_pts)
        ground_cutout_cap = pya.Region(ground_cutout_cap.to_itype(self.layout.dbu))
        #ground_cutout.round_corners(self.ground_radius / self.layout.dbu, self.ground_radius / self.layout.dbu, self.n)

        cap_pts = [
            pya.DPoint(-self.l_connection_spacing/2 + self.l_width/2, self.ground_gap_bottom),
            pya.DPoint(-self.l_connection_spacing/2 - self.l_width/2, self.ground_gap_bottom),
            pya.DPoint(-self.l_connection_spacing/2 - self.l_width/2, self.ground_gap_bottom - self.c_ground_spacing - self.c_gap),
            pya.DPoint(-self.l_connection_spacing/2 - self.l_width/2 - self.c_width, self.ground_gap_bottom - self.c_ground_spacing - self.c_gap),
            pya.DPoint(-self.l_connection_spacing/2 - self.l_width/2 - self.c_width, self.ground_gap_bottom - self.c_ground_spacing - self.c_gap - self.c_length),
            pya.DPoint(-self.l_connection_spacing/2 + self.l_width/2, self.ground_gap_bottom - self.c_ground_spacing - self.c_gap - self.c_length),
        ]
        cap_polygon = pya.DPolygon(cap_pts)
        cap_region = pya.Region(cap_polygon.to_itype(self.layout.dbu))

        if self.enable_gc_termination:
            gc_bottom = self.ground_gap_bottom - 2*self.gc_fingers_number * (self.gc_fingers_gap + self.gc_fingers_width) - self.gc_fingers_width
            gc_termination_cutout_pts = [
                pya.DPoint(self.l_connection_spacing/2 + self.a/2 + self.b, gc_bottom),
                pya.DPoint(self.l_connection_spacing/2 + self.a/2 + self.b, gc_bottom - self.gc_fingers_width),
                pya.DPoint(self.l_connection_spacing/2 - self.a/2 - self.b, gc_bottom - self.gc_fingers_width),
                pya.DPoint(self.l_connection_spacing/2 - self.a/2 - self.b, gc_bottom),
            ]
            gc_termination_cutout = pya.DPolygon(gc_termination_cutout_pts)
            gc_termination_cutout = pya.Region(gc_termination_cutout.to_itype(self.layout.dbu))

            gc_termination_rlc_points = [
                pya.DPoint(self.l_connection_spacing/2 + self.a/2 , gc_bottom + self.a/2),
                pya.DPoint(self.l_connection_spacing/2 + self.a/2 , gc_bottom - self.gc_fingers_width - self.a/2),
                pya.DPoint(self.l_connection_spacing/2 - self.a/2 , gc_bottom - self.gc_fingers_width - self.a/2),
                pya.DPoint(self.l_connection_spacing/2 - self.a/2 , gc_bottom + self.a/2),
            ]
            gc_termination_rlc = pya.DPolygon(gc_termination_rlc_points)
            gc_termination_rlc = pya.Region(gc_termination_rlc.to_itype(self.layout.dbu))

            self.refpoints["gc_termination_signal"] = pya.DPoint(self.l_connection_spacing/2, gc_bottom)
            self.refpoints["gc_termination_ground"] = pya.DPoint(self.l_connection_spacing/2, gc_bottom - self.gc_fingers_width)
        else:
            gc_termination_cutout = pya.Region()
            gc_termination_rlc = pya.Region()

        

        self.cell.shapes(self.get_layer("base_metal_gap_wo_grid")).insert(
            ground_cutout_cap + gc_termination_cutout - cap_region
        )

        self.cell.shapes(self.get_layer("lumped_rlc")).insert(
            gc_termination_rlc
        )

    

        # Add mesh control regions for fine-grained ANSYS mesh refinement
        # Disabled for Q3D ACRL simulations due to ANSYS bug with mesh layer deletion
        #if self.enable_mesh_layers:
            # mesh_2: Mesh over inductor region
        #    self.cell.shapes(self.get_layer("mesh_2")).insert(inductor_region)

        # Add named ACRL source/sink refpoints for Q3D inductance measurements
        # These refpoints will be automatically detected by get_acrl_sim_class()
        # Format: acrl_source_<name> and acrl_sink_<name> where <name> is the net name

        # Main inductor measurement: from capacitor junction to ground connection
        # Source: at top edge of left capacitor paddle (where inductor connects)
        source_x = -self.l_connection_spacing/2
        source_y = self.ground_gap_bottom
        self.refpoints["acrl_source_main_inductor"] = pya.DPoint(source_x, source_y)

        # Sink: at inductor ground connection (top center)
        sink_x = self.l_connection_spacing/2
        sink_y = self.ground_gap_bottom
        self.refpoints["acrl_sink_main_inductor"] = pya.DPoint(sink_x, sink_y)

        #self.add_port("feedline_a", pya.DPoint(-self.feedline_length/2, 0), pya.DVector(-1, 0))
        #self.add_port("feedline_b", pya.DPoint(self.feedline_length/2, 0), pya.DVector(1, 0))
        #self.refpoints["feedline_a"] = pya.DPoint(-self.feedline_length/2, 0)
        #self.refpoints["feedline_b"] = pya.DPoint(self.feedline_length/2, 0)
        #self.refpoints["inductor_ground"] = pya.DPoint(0, self.ground_gap_top - self.l_coupling_distance - 8 * self.l_radius)


    @classmethod
    def get_sim_ports(cls, simulation):
        """Define simulation ports for non-ACRL simulations.

        For ACRL simulations, refpoints (acrl_source_N, acrl_sink_N) are used instead
        and automatically detected by get_acrl_sim_class().

        For Q3D capacitance measurements with include_inductor=False, this returns
        an internal port at the capacitor center plate.
        """
        ports = []

        # For Q3D capacitance measurements (inductor disabled)
        if hasattr(simulation, 'include_inductor') and not simulation.include_inductor:
            ports.append(
                RefpointToInternalPort(
                    refpoint="capacitor_signal",
                    ground_refpoint=None,
                )
            )

        return ports
    
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

