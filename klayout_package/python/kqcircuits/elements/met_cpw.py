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
from kqcircuits.junctions.rkr_hook_junction import RKRHook
from kqcircuits.util.refpoints import RefpointToInternalPort

import numpy as np
import math


@add_parameters_from(WaveguideCoplanar, "add_metal")
class METCPW(Element):

    feedline_length = Param(pdt.TypeDouble, "Feedline length", 700, unit="μm")
    feedline_spacing = Param(pdt.TypeDouble, "Feedline spacing", 10, unit="μm")
    feedline_cutout = Param(pdt.TypeDouble, "Feedline cutout length", 50, unit="μm")
    feedline_cutout_bool = Param(pdt.TypeBoolean, "Whether to add feedline cutout", True)

    cpw_length = Param(pdt.TypeDouble, "Length of CPW Resonator", 4800, unit="μm")
    cpw_coupling_length = Param(pdt.TypeDouble, "Length of CPW coupling region", 250, unit="μm")
    cpw_coupling_distance = Param(pdt.TypeDouble, "Distance between CPW resonator and feedline", 5, unit="μm")
    cpw_fold_length = Param(pdt.TypeDouble, "Length of CPW folds region", 500, unit="μm")
    cpw_radius = Param(pdt.TypeDouble, "Radius of CPW bends", 50, unit="μm")
    cpw_a = Param(pdt.TypeDouble, "CPW center conductor width (a)", 10, unit="μm")
    cpw_b = Param(pdt.TypeDouble, "CPW gap width (b)", 4.5, unit="μm")

    gap_width = Param(pdt.TypeDouble, "Width of gap around MET", 40, unit="μm")
    gap_finger = Param(pdt.TypeDouble, "Length of finger leading to MET", 15, unit="μm")

    met_width = Param(pdt.TypeDouble, "Width of MET", 1.25, unit="μm") # post undercut
    met_height = Param(pdt.TypeDouble, "Height of MET", 1.25, unit="μm") # post undercut
    met_bridge_length = Param(pdt.TypeDouble, "Length of MET bridge", 10, unit="μm") 
    met_bridge_width = Param(pdt.TypeDouble, "Width of MET bridge", 2, unit="μm")

    coupler_width = Param(pdt.TypeDouble, "Width of coupler junction", 3, unit="μm") #post undercut
    coupler_height = Param(pdt.TypeDouble, "Height of coupler junction", 3, unit="μm") #post undercut

    al_undercut = Param(pdt.TypeDouble, "Aluminum undercut length", 1.5, unit="μm") # undercut distance
    ta_undercut = Param(pdt.TypeDouble, "Tantalum undercut length", 0.5, unit="μm") # undercut distance

    enable_mesh_layers = Param(pdt.TypeBoolean, "Enable mesh control layers for ANSYS", False)

    n = Param(pdt.TypeInt, "Number of points for rounding", 64)

    def build(self):

        self.cpw_n_folds = math.floor((self.cpw_length - self.cpw_coupling_length - 3 * self.cpw_radius * np.pi/2) / ((np.pi * self.cpw_radius + self.cpw_fold_length )))
        self.cpw_extra_length = self.cpw_length - self.cpw_n_folds * (np.pi * self.cpw_radius + self.cpw_fold_length )
        self.cpw_end_x = self.cpw_coupling_length/2 + self.cpw_radius + self.cpw_n_folds * 2 * self.cpw_radius
        self.cpw_end_y = self.a/2 + self.b + self.cpw_coupling_distance + self.cpw_b + self.cpw_a/2 + self.cpw_extra_length
        self.cpw_end_y = -self.cpw_end_y
        if self.cpw_n_folds % 2 == 0:
            self.cpw_end_y -= self.cpw_fold_length

        feedline_region = self._make_feedline()
        cpw_region = self._make_cpw_region()

        met_gap_region = self._get_met_gap_region()
        top_electrode_region = self._make_top_electrode()
        aluminum_region = self._make_al_region(top_electrode_region)
        bottom_electrode_region = self._make_bottom_electrode(top_electrode_region)

        self.cell.shapes(self.get_layer("airbridge_flyover")).insert(top_electrode_region)
        self.cell.shapes(self.get_layer("SIS_junction")).insert(aluminum_region)

        self.cell.shapes(self.get_layer("base_metal_gap_wo_grid")).insert(
            feedline_region + cpw_region + met_gap_region - bottom_electrode_region

        )

        # Add mesh control regions for fine-grained ANSYS mesh refinement
        # Disabled for Q3D ACRL simulations due to ANSYS bug with mesh layer deletion
        if self.enable_mesh_layers:
            # mesh_1: Fine mesh around spike regions
            spikes_meshing_region = self._make_spike_meshing_region()
            self.cell.shapes(self.get_layer("mesh_1")).insert(
                spikes_meshing_region
            )

            # mesh_2: Coarse mesh for inductor region (only when inductor is included)
            if self.include_inductor:
                self.cell.shapes(self.get_layer("mesh_2")).insert(
                    inductor_region
                )

            # mesh_3: Fine mesh in capacitor
            cap_meshing_region = self._make_cap_meshing_region()
            self.cell.shapes(self.get_layer("mesh_3")).insert(
                cap_meshing_region
            )
        

        # add reference point
        #self.add_port("feedline_a", pya.DPoint(-self.feedline_length/2, 0), pya.DVector(-1, 0))
        #self.add_port("feedline_b", pya.DPoint(self.feedline_length/2, 0), pya.DVector(1, 0))
        #self.refpoints["inductor_ground"] = pya.DPoint(self.end_box_far_left - self.l_grounding_distance, self.ground_gap_bottom)

        # Add named ACRL source/sink refpoints for Q3D inductance measurements
        # These refpoints will be automatically detected by get_acrl_sim_class()
        # Format: acrl_source_<name> and acrl_sink_<name> where <name> is the net name
        """if self.include_inductor:
            # Main inductor loop
            source_x = (self.end_box_left + self.end_box_right) / 2  # Center of end box
            source_y = self.end_box_bottom
            self.refpoints["acrl_source_main_inductor"] = pya.DPoint(source_x, source_y)

            sink_x = self.end_box_far_left - self.l_grounding_distance  # Center of inductor at ground
            sink_y = self.ground_gap_bottom - 2 * self.a  # Match actual inductor bottom
            self.refpoints["acrl_sink_main_inductor"] = pya.DPoint(sink_x, sink_y)

            # Feedline to feedline measurement (if cutout enabled)
            if self.feedline_cutout_bool:
                self.refpoints["acrl_source_feedline"] = pya.DPoint(self.feedline_length/2, 0)
                self.refpoints["acrl_sink_feedline"] = pya.DPoint(-self.feedline_length/2, 0)"""

    @classmethod
    def get_sim_ports(cls, simulation):
        """Define simulation ports for non-ACRL simulations.

        For ACRL simulations, refpoints (acrl_source_N, acrl_sink_N) are used instead
        and automatically detected by get_acrl_sim_class().

        For non-ACRL simulations with lumped junction, this returns a lumped RLC port.
        """
        ports = []

        # If junction is in lumped model mode, add RLC port
        if simulation.junction_bool and simulation.junction_use_lumped:
            ports.append(
                RefpointToInternalPort(
                    refpoint="junction_signal",
                    ground_refpoint="junction_ground",
                    inductance=simulation.junction_lumped_inductance * 1e-9,  # nH to H
                    capacitance=simulation.junction_lumped_capacitance * 1e-15,  # fF to F
                    junction=True,  # Keep this for EPR calculations
                    lumped_element=True,  # Also mark as lumped
                    rlc_type="parallel",
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


    def _make_cpw_region(self):
        coupling_y = self.a/2 + self.b + self.cpw_coupling_distance + self.cpw_b + self.cpw_a/2
        coupling_y = - coupling_y

        path_pts = [pya.DPoint(-self.cpw_coupling_length/2, coupling_y),
                    pya.DPoint(self.cpw_coupling_length/2, coupling_y),
                    ]

        path_pts += self._arc_points(self.cpw_coupling_length/2, coupling_y - self.cpw_radius, self.cpw_radius, np.pi/2, 0, self.n/4)
        cpw_folds_top_y = - coupling_y - self.cpw_radius - self.cpw_extra_length
        cpw_folds_start_x = self.cpw_coupling_length/2 + self.cpw_radius
        path_pts += [pya.DPoint(cpw_folds_start_x, cpw_folds_top_y)]

        i = 0
        while i < self.cpw_n_folds:
            if i % 2 == 1:
                #down
                path_pts += self._arc_points(cpw_folds_start_x + (2*i + 1)*self.cpw_radius, cpw_folds_top_y, self.cpw_radius, np.pi, 0, self.n/2)
                path_pts += [pya.DPoint(cpw_folds_start_x + 2*(i+1)*self.cpw_radius, cpw_folds_top_y - self.cpw_fold_length)]
            else:
                #up
                path_pts += self._arc_points(cpw_folds_start_x + (2*i + 1)*self.cpw_radius, cpw_folds_top_y - self.cpw_fold_length, self.cpw_radius, np.pi, 2*np.pi, self.n/2)
                path_pts += [pya.DPoint(cpw_folds_start_x + 2*(i+1)*self.cpw_radius, cpw_folds_top_y)]
            i += 1

        cpw_center_dpath = pya.DPath(path_pts, self.cpw_a)
        cpw_center_polygon = cpw_center_dpath.to_itype(self.layout.dbu)
        cpw_center_region = pya.Region(cpw_center_polygon)

        cpw_gap_dpath = pya.DPath(path_pts, self.cpw_a + 2*self.cpw_b)
        cpw_gap_polygon = cpw_gap_dpath.to_itype(self.layout.dbu)
        cpw_gap_region = pya.Region(cpw_gap_polygon)

        return cpw_gap_region - cpw_center_region
    
    def _get_met_gap_region(self):
        met_gap_height = self.gap_finger + self.met_height + self.met_bridge_length + self.coupler_height

        gap_region_pts = [
            pya.DPoint(self.cpw_end_x - self.met_width/2 - self.gap_width/2, self.cpw_end_y),
            pya.DPoint(self.cpw_end_x + self.met_width/2 + self.gap_width/2, self.cpw_end_y),
            pya.DPoint(self.cpw_end_x + self.met_width/2 + self.gap_width/2, self.cpw_end_y - met_gap_height),
            pya.DPoint(self.cpw_end_x - self.met_width/2 - self.gap_width/2, self.cpw_end_y - met_gap_height),
        ] 

        return pya.Region(pya.DPolygon(gap_region_pts).to_itype(self.layout.dbu))
    
    def _make_top_electrode(self):
        return pya.Region()
    
    def _make_al_region(self, top_electrode_region):
        return pya.Region()
    
    def _make_bottom_electrode(self, top_electrode_region):
        return pya.Region()
        
