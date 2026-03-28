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
from kqcircuits.junctions.rkr_hook_junction import RKRHook
from kqcircuits.util.refpoints import RefpointToInternalPort

import numpy as np
import math


@add_parameters_from(WaveguideCoplanar, "add_metal")
class BiasResonator3(Element):
    l_ground_cutout_height = Param(pdt.TypeDouble, "Height of ground cutout for inductor", 1500, unit="μm")
    
    feedline_spacing = Param(pdt.TypeDouble, "Feedline spacing", 10, unit="μm")
    feedline_coupling_ground_spacing = Param(pdt.TypeDouble, "Feedline coupling ground spacing", 10, unit="μm")
    
    l_tot_length = Param(pdt.TypeDouble, "Total length of inductor", 12000, unit="μm")
    l_coupling_length = Param(pdt.TypeDouble, "Length of inductor coupling region", 80, unit="μm")
    l_coupling_distance = Param(pdt.TypeDouble, "Distance between inductor and ground in coupling region", 10, unit="μm")
    l_width = Param(pdt.TypeDouble, "Inductor width", 4, unit="μm")
    l_connection_spacing = Param(pdt.TypeDouble, "Spacing between inductors two connections", 200, unit="μm")

    c_main_gap = Param(pdt.TypeDouble, "Main capacitor gap", 20, unit="μm")
    c_main_width = Param(pdt.TypeDouble, "Main capacitor pad width", 300, unit="μm")
    c_main_length = Param(pdt.TypeDouble, "Main capacitor pad length", 200, unit="μm")

    c_ground_gap = Param(pdt.TypeDouble, "Grounding capacitor finger gap", 4, unit="μm")
    c_ground_finger_length = Param(pdt.TypeDouble, "Grounding capacitor finger length", 100, unit="μm")
    c_ground_finger_width = Param(pdt.TypeDouble, "Grounding capacitor finger width", 4, unit="μm")
    c_ground_finger_number_start = Param(pdt.TypeInt, "Number of grounding capacitor fingers, first section", 10)
    c_ground_finger_number_end = Param(pdt.TypeInt, "Number of grounding capacitor fingers, last section", 20)


    enable_mesh_layers = Param(pdt.TypeBoolean, "Enable mesh control layers for ANSYS", False)

    n = Param(pdt.TypeInt, "Number of points for rounding", 64)

    def build(self):

        self.insert_cell(CoupledInductor, pya.DCplxTrans(1, 0, False, 0.0, 0.0), "main_inductor",
                         ground_cutout_height=self.l_ground_cutout_height,
                         feedline_spacing=self.feedline_spacing,
                         feedline_coupling_ground_spacing=self.feedline_coupling_ground_spacing,
                         l_tot_length=self.l_tot_length,
                         l_coupling_length=self.l_coupling_length,
                         l_coupling_distance=self.l_coupling_distance,
                         l_width=self.l_width,
                         l_connection_spacing=self.l_connection_spacing,
                         enable_mesh_layers=self.enable_mesh_layers,
                         n=self.n)

        self.ground_gap_bottom = -self.l_ground_cutout_height - self.feedline_spacing - self.a/2 - self.b
        self.ground_gap_top =  - self.feedline_spacing - self.a/2 - self.b


        
        cap_main_start_x = -self.l_connection_spacing/2
        cap_main_bottom = self.ground_gap_bottom - self.c_main_length - 2 * self.c_main_gap
        cap_main_center_pts = [
            pya.DPoint(cap_main_start_x + self.l_width/2, self.ground_gap_bottom),
            pya.DPoint(cap_main_start_x + self.l_width/2, cap_main_bottom),
            pya.DPoint(cap_main_start_x - self.l_width/2 - self.c_main_width, cap_main_bottom),
            pya.DPoint(cap_main_start_x - self.l_width/2 - self.c_main_width, self.ground_gap_bottom - 2 * self.c_main_gap),
            pya.DPoint(cap_main_start_x - self.l_width/2, self.ground_gap_bottom - 2 * self.c_main_gap),
            pya.DPoint(cap_main_start_x - self.l_width/2, self.ground_gap_bottom),
        ]
        cap_main_gap_pts = [
            pya.DPoint(cap_main_start_x + self.l_width/2 + self.c_main_gap, self.ground_gap_bottom),
            pya.DPoint(cap_main_start_x + self.l_width/2 + self.c_main_gap, cap_main_bottom - self.c_main_gap),
            pya.DPoint(cap_main_start_x - self.l_width/2 - self.c_main_gap - self.c_main_width, cap_main_bottom - self.c_main_gap),
            pya.DPoint(cap_main_start_x - self.l_width/2 - self.c_main_gap - self.c_main_width, self.ground_gap_bottom - self.c_main_gap),
            pya.DPoint(cap_main_start_x - self.l_width/2 - self.c_main_gap, self.ground_gap_bottom - self.c_main_gap),
            pya.DPoint(cap_main_start_x - self.l_width/2 - self.c_main_gap, self.ground_gap_bottom),
        ]
        cap_main_center_region = pya.Region(pya.DPolygon(cap_main_center_pts).to_itype(self.layout.dbu))
        cap_main_gap_region = pya.Region(pya.DPolygon(cap_main_gap_pts).to_itype(self.layout.dbu))
        cap_main_region = cap_main_gap_region - cap_main_center_region



        i = 0
        cap_ground_start_x = self.l_connection_spacing/2 + self.c_ground_finger_width/2
        finger_spacing_y = 2*self.c_ground_finger_width + 2*self.c_ground_gap
        cap_ground_gap_inside_pts = [pya.DPoint(cap_ground_start_x, self.ground_gap_bottom)]
        cap_ground_gap_outside_pts = [pya.DPoint(cap_ground_start_x + self.c_ground_gap, self.ground_gap_bottom)]
        while i < self.c_ground_finger_number_start:
            cap_ground_gap_inside_pts += [pya.DPoint(cap_ground_start_x, self.ground_gap_bottom - finger_spacing_y * (i - 1) - 2 * self.c_ground_finger_width - self.c_ground_gap),
                                          pya.DPoint(cap_ground_start_x, self.ground_gap_bottom - finger_spacing_y * i - self.c_ground_finger_width - self.c_ground_gap), 
                                          pya.DPoint(cap_ground_start_x + self.c_ground_finger_length, self.ground_gap_bottom - finger_spacing_y * i - self.c_ground_finger_width - self.c_ground_gap), 
                                          pya.DPoint(cap_ground_start_x + self.c_ground_finger_length, self.ground_gap_bottom - finger_spacing_y * i - 2 * self.c_ground_finger_width - self.c_ground_gap), 
                                          ]
            
            cap_ground_gap_outside_pts += [pya.DPoint(cap_ground_start_x + self.c_ground_gap, self.ground_gap_bottom - finger_spacing_y * i - self.c_ground_finger_width),
                                          pya.DPoint(cap_ground_start_x + self.c_ground_gap + self.c_ground_finger_length, self.ground_gap_bottom - finger_spacing_y * i - self.c_ground_finger_width),
                                          pya.DPoint(cap_ground_start_x + self.c_ground_gap + self.c_ground_finger_length, self.ground_gap_bottom - finger_spacing_y * (i + 1)),
                                          pya.DPoint(cap_ground_start_x + self.c_ground_gap, self.ground_gap_bottom - finger_spacing_y * (i + 1)), 
                                          ]
            i += 1
        cap_ground_gap_inside_pts.append(pya.DPoint(cap_ground_start_x, self.ground_gap_bottom - finger_spacing_y * (i - 1) - 2 * self.c_ground_finger_width - self.c_ground_gap))
        cap_ground_gap_inside_pts.append(pya.DPoint(cap_ground_start_x, self.ground_gap_bottom - finger_spacing_y * (i)))
        cap_ground_gap_outside_pts.reverse()
        cap_ground_gap_pts = cap_ground_gap_inside_pts + cap_ground_gap_outside_pts
        cap_ground_gap_region = pya.Region(pya.DPolygon(cap_ground_gap_pts).to_itype(self.layout.dbu))

        cap_ground_gap_left_pts = [pya.DPoint(cap_ground_start_x - self.c_ground_finger_width, self.ground_gap_bottom),
                                  pya.DPoint(cap_ground_start_x - self.c_ground_finger_width, self.ground_gap_bottom - finger_spacing_y * (self.c_ground_finger_number_start - 1) - 2 * self.c_ground_finger_width - self.c_ground_gap),
                                  pya.DPoint(cap_ground_start_x - self.c_ground_finger_width - self.c_ground_gap, self.ground_gap_bottom - finger_spacing_y * (self.c_ground_finger_number_start - 1) - 2 * self.c_ground_finger_width - self.c_ground_gap),
                                  pya.DPoint(cap_ground_start_x - self.c_ground_finger_width - self.c_ground_gap, self.ground_gap_bottom - finger_spacing_y * (self.c_ground_finger_number_start - 1) - 2 * self.c_ground_finger_width - self.c_ground_gap),
                                  ]


        self.cell.shapes(self.get_layer("base_metal_gap_wo_grid")).insert(
            cap_main_region + cap_ground_gap_region
        )

        #self.cell.shapes(self.get_layer("base_metal_gap_wo_grid")).insert(
        #    feedline_region + ground_cutout - inductor_region
        #)

        # Add mesh control regions for fine-grained ANSYS mesh refinement
        # Disabled for Q3D ACRL simulations due to ANSYS bug with mesh layer deletion
        if self.enable_mesh_layers:
            # mesh_2: Mesh over inductor region
            self.cell.shapes(self.get_layer("mesh_2")).insert(inductor_region)

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

        # Capacitor internal port refpoint for Q3D capacitance measurements
        #self.refpoints["capacitor_signal"] = pya.DPoint(0, (self.ground_gap_bottom_cap + self.ground_gap_bottom)/2)

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

    def _arc_points(self, center_x, center_y, r, theta0, theta1, n):
        #theta = 0 is (1,0) directionreturn [
        return [
            pya.DPoint(
                center_x + r * np.cos(t),
                center_y + r * np.sin(t)
            )
            for t in [theta0 + i*(theta1-theta0)/(n-1) for i in range(int(n))]
        ]


    def _make_inductor_region(self):
        l_mandatory_length = 2 * (self.ground_cutout_width - 2 * self.l_ground_sep) - self.l_connection_spacing + self.ground_cutout_height - self.l_coupling_distance + 10 * self.l_radius * (2 - np.pi/4)
        l_foldable_length = self.l_tot_length - l_mandatory_length
        max_length_per_fold = 2 * (self.l_radius * (np.pi - 4) + (self.ground_cutout_width/2 - self.l_ground_sep - self.l_middle_sep/2))  # Max length that can fit in one set of two folds (S-shape)
        n_folds = math.ceil(l_foldable_length / (2 * max_length_per_fold))
        h_folds = l_foldable_length / (4 * n_folds)
        #h_folds = self.l_middle_sep * 5
        #n_folds = 3

        coupling_y_center = self.ground_gap_top - self.l_coupling_distance

        path_pts = [pya.DPoint(0, coupling_y_center),
                    pya.DPoint(self.l_coupling_length/2 - self.l_radius, coupling_y_center)
                    ]
        
        path_pts += self._arc_points(self.l_coupling_length/2 - self.l_radius, coupling_y_center - self.l_radius, self.l_radius, np.pi/2, 0, self.n/4)
        
        path_pts += [pya.DPoint(self.l_coupling_length/2, coupling_y_center - self.l_radius),
                     pya.DPoint(self.l_coupling_length/2, coupling_y_center + self.l_radius - self.l_ground_sep)]
        path_pts += self._arc_points(self.l_coupling_length/2 + self.l_radius, coupling_y_center - self.l_ground_sep + self.l_radius, self.l_radius, np.pi, 3 * np.pi/2, self.n/4)
        
        path_pts += [pya.DPoint(self.l_coupling_length/2 + self.l_radius, coupling_y_center - self.l_ground_sep),
                     pya.DPoint(self.ground_cutout_width/2 - self.l_ground_sep - self.l_radius, coupling_y_center - self.l_ground_sep)]
        path_pts += self._arc_points(self.ground_cutout_width/2 - self.l_ground_sep - self.l_radius, coupling_y_center - self.l_ground_sep - self.l_radius, self.l_radius, np.pi/2, 0, self.n/4)
        
        path_pts += [pya.DPoint(self.ground_cutout_width/2 - self.l_ground_sep, coupling_y_center - self.l_ground_sep - self.l_radius),
                     pya.DPoint(self.ground_cutout_width/2 - self.l_ground_sep, coupling_y_center - 2 * self.l_ground_sep + self.l_radius)]
        path_pts += self._arc_points(self.ground_cutout_width/2 - self.l_ground_sep - self.l_radius, coupling_y_center - 2 * self.l_ground_sep + self.l_radius, self.l_radius, 2 * np.pi, 3 * np.pi/2, self.n/4)
        
        path_pts += [pya.DPoint(self.ground_cutout_width/2 - self.l_ground_sep - self.l_radius, coupling_y_center - 2 * self.l_ground_sep),
                     pya.DPoint(self.l_connection_spacing/2 + self.l_radius, coupling_y_center - 2 * self.l_ground_sep)]

        #start of folds
        fold_start_x = self.l_connection_spacing/2 + self.l_radius
        fold_start_y = coupling_y_center - 2 * self.l_ground_sep

        i = 0
        while i < n_folds:
            path_pts += [pya.DPoint(fold_start_x, fold_start_y - 4*self.l_radius*i),
                         pya.DPoint(self.l_middle_sep/2 + self.l_radius, fold_start_y - 4*self.l_radius*i)]
            path_pts += self._arc_points(self.l_middle_sep/2 + self.l_radius, fold_start_y - 4*self.l_radius*i - self.l_radius, self.l_radius, np.pi/2, 3 * np.pi/2, self.n/2)
        
            path_pts += [pya.DPoint(self.l_middle_sep/2 + self.l_radius, fold_start_y - 4*self.l_radius*(i + 0.5)),
                         pya.DPoint(self.l_middle_sep/2 + h_folds - self.l_radius, fold_start_y - 4*self.l_radius*(i + 0.5))]
            path_pts += self._arc_points(self.l_middle_sep/2 + h_folds - self.l_radius, fold_start_y - 4*self.l_radius*(i + 0.5) - self.l_radius, self.l_radius, np.pi/2, -np.pi/2, self.n/2)
            
            path_pts += [pya.DPoint(self.l_middle_sep/2 + h_folds - self.l_radius, fold_start_y - 4*self.l_radius*(i + 1)),
                         pya.DPoint(self.l_connection_spacing/2 + self.l_radius, fold_start_y - 4*self.l_radius*(i + 1))]
            
            i += 1

        path_pts += self._arc_points(self.l_connection_spacing/2 + self.l_radius, fold_start_y - 4*self.l_radius*n_folds - self.l_radius, self.l_radius, np.pi/2, np.pi, self.n/4)
        path_pts += [pya.DPoint(self.l_connection_spacing/2, fold_start_y - 4*self.l_radius*n_folds - self.l_radius),
                     pya.DPoint(self.l_connection_spacing/2, self.ground_gap_bottom)]
            

        l_dpath = pya.DPath(path_pts, self.l_width)
        l_polygon = l_dpath.to_itype(self.layout.dbu)
        l_region = pya.Region(l_polygon)
        l_region_mirrored = l_region.transformed(pya.Trans(pya.Trans.M90))

        return l_region + l_region_mirrored
    
    def _make_capacitor_region(self):
        
        pts_paddle = [
            pya.DPoint(self.cap_inset + self.cap_gap, self.cap_center_y - self.cap_center_height/2),
            pya.DPoint(self.cap_inset + self.cap_gap + self.cap_center_width, self.cap_center_y - self.cap_center_height/2),
            pya.DPoint(self.cap_inset + self.cap_gap + self.cap_center_width, self.cap_center_y + self.cap_center_height/2),
            pya.DPoint(self.cap_inset + self.cap_gap, self.cap_center_y + self.cap_center_height/2)
        ]
        region_paddle = pya.Region(pya.DPolygon(pts_paddle).to_itype(self.layout.dbu))
        
        pts_gap_paddle = [
            pya.DPoint(self.cap_inset, self.cap_center_y - self.cap_center_height/2 - self.cap_gap),
            pya.DPoint(self.cap_inset + 2*self.cap_gap + self.cap_center_width, self.cap_center_y - self.cap_center_height/2 - self.cap_gap),
            pya.DPoint(self.cap_inset + 2*self.cap_gap + self.cap_center_width, self.cap_center_y + self.cap_center_height/2 + self.cap_gap),
            pya.DPoint(self.cap_inset, self.cap_center_y + self.cap_center_height/2 + self.cap_gap)
        ]
        region_gap_paddle = pya.Region(pya.DPolygon(pts_gap_paddle).to_itype(self.layout.dbu))

        pts_leads = [
            pya.DPoint(0, self.cap_center_y - self.l_width/2),
            pya.DPoint(self.cap_inset + self.cap_gap, self.cap_center_y - self.l_width/2),
            pya.DPoint(self.cap_inset + self.cap_gap, self.cap_center_y + self.l_width/2),
            pya.DPoint(0, self.cap_center_y + self.l_width/2)
        ]
        region_leads = pya.Region(pya.DPolygon(pts_leads).to_itype(self.layout.dbu))

        pts_leads_gap = [
            pya.DPoint(0, self.cap_center_y - self.l_width/2 - self.cap_gap),
            pya.DPoint(self.cap_inset + self.cap_gap, self.cap_center_y - self.l_width/2 - self.cap_gap),
            pya.DPoint(self.cap_inset + self.cap_gap, self.cap_center_y + self.l_width/2 + self.cap_gap),
            pya.DPoint(0, self.cap_center_y + self.l_width/2 + self.cap_gap)
        ]
        region_leads_gap = pya.Region(pya.DPolygon(pts_leads_gap).to_itype(self.layout.dbu))

        return region_gap_paddle - region_paddle + region_leads_gap - region_leads
    def _make_capacitor_gap_region(self):
        return pya.Region()

