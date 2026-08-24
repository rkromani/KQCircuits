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
from kqcircuits.junctions.rkr_hook_junction import RKRHook
from kqcircuits.util.refpoints import RefpointToInternalPort

import numpy as np
import math


@add_parameters_from(WaveguideCoplanar, "add_metal")
class JunctionTest(Element):

    ground_cutout_width = Param(pdt.TypeDouble, "Width of ground cutout", 360, unit="μm")
    ground_cutout_height = Param(pdt.TypeDouble, "Height of ground cutout", 600, unit="μm")
    ground_radius = Param(pdt.TypeDouble, "Radius of ground cutout corners", 10, unit="μm")

    big_pad_width = Param(pdt.TypeDouble, "Width of pad for probe", 200, unit="μm")
    big_pad_height = Param(pdt.TypeDouble, "Height of pad for probe", 200, unit="μm")

    #junction parameters
    pad_width = Param(pdt.TypeDouble, "Width of pad connecting to the circuit", 8, unit="μm")
    pad_height = Param(pdt.TypeDouble, "Height of pad connecting to the circuit", 5, unit="μm")
    
    finger_length = Param(pdt.TypeDouble, "Length of junction finger", 5, unit="μm")
    finger_tip_length = Param(pdt.TypeDouble, "Length of junction finger tip", 2, unit="μm")
    finger_width = Param(pdt.TypeDouble, "Width of junction finger a.k.a. bridge length", 0.1, unit="μm")
    hook_width = Param(pdt.TypeDouble, "Width of hook", 0.1, unit="μm")
    finger_taper_base_width = Param(pdt.TypeDouble, "Width of junction finger taper at base", 5, unit="μm")
    finger_spacing = Param(pdt.TypeDouble, "Spacing between junction fingers", 1, unit="μm")
    overshoot = Param(pdt.TypeDouble, "Amount the hook extends beyond the finger width and finger beyond hook", 0.25, unit="μm")
    
    #bridge_width = Param(pdt.TypeDouble, "Width of bridge connecting junction fingers", 1.5, unit="μm")
    junction_length = Param(pdt.TypeDouble, "Length of junction", 0.1, unit="μm")
    
    shadow_angle_1 = Param(pdt.TypeDouble, "Angle of shadow 1", -45, unit="deg")
    shadow_angle_2 = Param(pdt.TypeDouble, "Angle of shadow 2", 45, unit="deg")
    resist_thickness = Param(pdt.TypeDouble, "Thickness of resist", 0.5, unit="μm")

    t_cut_body_width = Param(pdt.TypeDouble, "Width of T-cut", 4, unit="μm")
    t_cut_distance_from_back = Param(pdt.TypeDouble, "Distance of T-cut from back of Al deposition", 1, unit="μm")
    t_cut_t_width = Param(pdt.TypeDouble, "Width of T-cut T", 6, unit="μm")
    t_cut_t_height = Param(pdt.TypeDouble, "Height of T-cut T", 2, unit="μm")

    n = Param(pdt.TypeInt, "Number of points for rounding", 64)

    def build(self):

        self.junction_pad_spacing = 2 * self.finger_length + 2 * self.finger_tip_length + self.finger_spacing
        self.pad_bottom_top = self.pad_height
        self.pad_top_bottom = self.pad_height + self.junction_pad_spacing
        
        ground_cutout_pts = [
            pya.DPoint(self.ground_cutout_width/2, self.ground_cutout_height/2),
            pya.DPoint(self.ground_cutout_width/2, -self.ground_cutout_height/2),
            pya.DPoint(-self.ground_cutout_width/2, -self.ground_cutout_height/2),
            pya.DPoint(-self.ground_cutout_width/2, self.ground_cutout_height/2)
        ]
        ground_cutout = pya.DPolygon(ground_cutout_pts)
        ground_cutout = pya.Region(ground_cutout.to_itype(self.layout.dbu))
        ground_cutout.round_corners(self.ground_radius / self.layout.dbu, self.ground_radius / self.layout.dbu, self.n)

        pad_top_pts = [
            pya.DPoint(self.big_pad_width/2, self.pad_top_bottom),
            pya.DPoint(self.big_pad_width/2, self.pad_top_bottom + self.big_pad_height),
            pya.DPoint(-self.big_pad_width/2, self.pad_top_bottom + self.big_pad_height),
            pya.DPoint(-self.big_pad_width/2, self.pad_top_bottom),
        ]
        pad_top = pya.DPolygon(pad_top_pts)
        pad_top = pya.Region(pad_top.to_itype(self.layout.dbu))

        pad_bottom_pts =[
            pya.DPoint(self.big_pad_width/2, self.pad_bottom_top), 
            pya.DPoint(self.big_pad_width/2, self.pad_bottom_top - self.big_pad_height),
            pya.DPoint(-self.big_pad_width/2, self.pad_bottom_top - self.big_pad_height),
            pya.DPoint(-self.big_pad_width/2, self.pad_bottom_top),
        ]
        pad_bottom = pya.DPolygon(pad_bottom_pts)
        pad_bottom = pya.Region(pad_bottom.to_itype(self.layout.dbu))

        pads_region = pad_bottom + pad_top
        pads_region.round_corners(self.ground_radius / self.layout.dbu, self.ground_radius / self.layout.dbu, self.n)

        self.cell.shapes(self.get_layer("base_metal_gap_wo_grid")).insert(
            ground_cutout - pads_region
        )

        self.insert_cell(RKRHook, pya.DCplxTrans(1, 0, False, 0, 0), "j1",
                        pad_width=self.pad_width,
                        pad_height=self.pad_height,
                        finger_length=self.finger_length,
                        finger_tip_length=self.finger_tip_length,
                        finger_width=self.finger_width,
                        hook_width=self.hook_width,
                        finger_taper_base_width=self.finger_taper_base_width,
                        finger_spacing=self.finger_spacing,
                        overshoot=self.overshoot, 
                        junction_length=self.junction_length, 
                        shadow_angle_1=self.shadow_angle_1, 
                        shadow_angle_2=self.shadow_angle_2,
                        resist_thickness=self.resist_thickness, 
                        t_cut_body_width=self.t_cut_body_width, 
                        t_cut_distance_from_back=self.t_cut_distance_from_back, 
                        t_cut_t_width=self.t_cut_t_width, 
                        t_cut_t_height=self.t_cut_t_height, 
                        n=self.n
                        )

        

        

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
    
