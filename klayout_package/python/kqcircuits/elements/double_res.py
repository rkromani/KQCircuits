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
class DoubleRes(Element):

    ground_cutout_width = Param(pdt.TypeDouble, "Width of ground cutout", 1400, unit="μm")
    ground_cutout_height = Param(pdt.TypeDouble, "Height of ground cutout", 800, unit="μm")
    ground_radius = Param(pdt.TypeDouble, "Radius of ground cutout corners", 10, unit="μm")

    feedline_length = Param(pdt.TypeDouble, "Feedline length", 1500, unit="μm")
    feedline_spacing = Param(pdt.TypeDouble, "Feedline spacing", 10, unit="μm")
    feedline_coupling_ground_spacing = Param(pdt.TypeDouble, "Feedline coupling ground spacing", 5, unit="μm")
    feedline_cutout = Param(pdt.TypeDouble, "Feedline cutout length", 50, unit="μm")
    feedline_cutout_bool = Param(pdt.TypeBoolean, "Whether to add feedline cutout", True)

    l_tot_length = Param(pdt.TypeDouble, "Total length of inductor", 9000, unit="μm")
    l_coupling_length = Param(pdt.TypeDouble, "Length of inductor coupling region", 80, unit="μm")
    l_coupling_distance = Param(pdt.TypeDouble, "Distance between inductor and feedline", 10, unit="μm")
    l_ground_sep = Param(pdt.TypeDouble, "Separation between inductor and ground", 50, unit="μm")
    l_width = Param(pdt.TypeDouble, "Width of inductor", 4, unit="μm")
    l_radius = Param(pdt.TypeDouble, "Radius of inductor bends", 25, unit="μm")

    cap_wide_height = Param(pdt.TypeDouble, "Height of wide capacitor section", 250, unit="μm")
    cap_narrow_height = Param(pdt.TypeDouble, "Height of narrow capacitor section", 10, unit="μm")
    cap_wide_gap = Param(pdt.TypeDouble, "Gap of wide capacitor section", 4, unit="μm")
    cap_narrow_gap = Param(pdt.TypeDouble, "Gap of narrow capacitor section", 0.1, unit="μm")
    cap_inner_width = Param(pdt.TypeDouble, "Inner width of capacitor plates", 20, unit="μm")
    cap_outer_width = Param(pdt.TypeDouble, "Outer width of capacitor plates", 20, unit="μm")
    cap_bias_length = Param(pdt.TypeDouble, "Length of bias lead", 50, unit="μm")

    include_inductor = Param(pdt.TypeBoolean, "Include inductor (disable for Q3D capacitance measurements)", True)
    include_bias_resistor = Param(pdt.TypeBoolean, "Whether to include resistance on bias line", False)
    ground_bias = Param(pdt.TypeBoolean, "Whether to ground bias line", True)
    enable_mesh_layers = Param(pdt.TypeBoolean, "Enable mesh control layers for ANSYS", False)

    n = Param(pdt.TypeInt, "Number of points for rounding", 64)

    def build(self):

        self.ground_gap_top = -(self.a/2 + self.b + self.feedline_coupling_ground_spacing)
        self.ground_gap_bottom = self.ground_gap_top - self.ground_cutout_height

        self.cap_region_total_width = self.cap_inner_width + 2 * self.cap_outer_width + 2 * self.cap_wide_gap

        ground_cutout_pts = [
            pya.DPoint(self.ground_cutout_width/2, self.ground_gap_top),
            pya.DPoint(self.ground_cutout_width/2, self.ground_gap_bottom),
            pya.DPoint(-self.ground_cutout_width/2, self.ground_gap_bottom),
            pya.DPoint(-self.ground_cutout_width/2, self.ground_gap_top)
        ]
        ground_cutout = pya.DPolygon(ground_cutout_pts)
        ground_cutout = pya.Region(ground_cutout.to_itype(self.layout.dbu))
        ground_cutout.round_corners(self.ground_radius / self.layout.dbu, self.ground_radius / self.layout.dbu, self.n)
        

        feedline_region = self._make_feedline()

        # Conditionally create inductor region based on include_inductor flag
        if self.include_inductor:
            inductor_region = self._make_inductor_region()
        else:
            inductor_region = pya.Region()  # Empty region for Q3D capacitance measurements

        capacitor_region_wide = self._make_wide_capacitor_region()
        capacitor_region_narrow = self._make_narrow_capacitor_region()
        bias_line, bias_line_gap = self._make_bias_leads()

        self.cell.shapes(self.get_layer("base_metal_gap_wo_grid")).insert(
            feedline_region + ground_cutout - inductor_region - capacitor_region_wide - capacitor_region_narrow + bias_line_gap - bias_line
        )

        if self.include_bias_resistor:
            resistor_top_y = self.ground_gap_bottom - self.cap_bias_length + self.a
            resistor_bottom_y = self.ground_gap_bottom - self.cap_bias_length - self.a - self.b
            resistor_pts = [
                pya.DPoint(-self.a/2, resistor_top_y),
                pya.DPoint(self.a/2, resistor_top_y),
                pya.DPoint(self.a/2, resistor_bottom_y),
                pya.DPoint(-self.a/2, resistor_bottom_y),
            ]
            resistor_region = pya.Region(pya.DPolygon(resistor_pts).to_itype(self.layout.dbu))
            self.cell.shapes(self.get_layer("lumped_rlc")).insert(resistor_region)

            # Add refpoints at resistor edges for debugging
            self.refpoints["resistor_signal"] = pya.DPoint(0, resistor_top_y)
            self.refpoints["resistor_ground"] = pya.DPoint(0, resistor_bottom_y)

        # Add mesh control regions for fine-grained ANSYS mesh refinement
        # Disabled for Q3D ACRL simulations due to ANSYS bug with mesh layer deletion
        if self.enable_mesh_layers:
            # mesh_1: Fine mesh in capacitor gaps (between plates)
            cap_gap_region = self._make_capacitor_gap_region()
            self.cell.shapes(self.get_layer("mesh_1")).insert(cap_gap_region)

            # mesh_2: Mesh over inductor region
            if self.include_inductor:
                self.cell.shapes(self.get_layer("mesh_2")).insert(inductor_region)

        # Add named ACRL source/sink refpoints for Q3D inductance measurements
        # These refpoints will be automatically detected by get_acrl_sim_class()
        # Format: acrl_source_<name> and acrl_sink_<name> where <name> is the net name
        if self.include_inductor:
            # Main inductor measurement: from capacitor junction to ground connection
            # Source: at top edge of left capacitor paddle (where inductor connects)
            cap_bottom = self.ground_gap_bottom + self.l_ground_sep - self.l_width/2
            cap_top = cap_bottom + self.cap_wide_height
            source_x = -self.cap_region_total_width/2 + self.l_width/2
            source_y = cap_top
            self.refpoints["acrl_source_main_inductor"] = pya.DPoint(source_x, source_y)

            # Sink: at inductor ground connection (top center)
            sink_x = 0
            sink_y = self.ground_gap_top
            self.refpoints["acrl_sink_main_inductor"] = pya.DPoint(sink_x, sink_y)

            # Feedline measurement (if cutout enabled)
            if self.feedline_cutout_bool:
                self.refpoints["acrl_source_feedline"] = pya.DPoint(self.feedline_length/2, 0)
                self.refpoints["acrl_sink_feedline"] = pya.DPoint(-self.feedline_length/2, 0)

        # Capacitor internal port refpoint for Q3D capacitance measurements
        cap_bottom = self.ground_gap_bottom + self.l_ground_sep - self.l_width/2
        cap_center_y = cap_bottom + self.cap_wide_height/2
        self.refpoints["capacitor_signal"] = pya.DPoint(0, cap_center_y)

        self.add_port("feedline_a", pya.DPoint(-self.feedline_length/2, 0), pya.DVector(-1, 0))
        self.add_port("feedline_b", pya.DPoint(self.feedline_length/2, 0), pya.DVector(1, 0))
        self.refpoints["feedline_a"] = pya.DPoint(-self.feedline_length/2, 0)
        self.refpoints["feedline_b"] = pya.DPoint(self.feedline_length/2, 0)
        self.refpoints["bias"] = pya.DPoint(0, self.ground_gap_bottom)


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
        l_mandatory_length = 2 * self.l_coupling_length + 2 * (self.ground_cutout_height - 2 * self.l_ground_sep - 2 * self.l_radius) + 2 * np.pi * self.l_radius
        l_foldable_length = self.l_tot_length - l_mandatory_length
        max_fold_height = (self.ground_cutout_height - 2 * self.l_ground_sep - 2 * self.l_radius)
        max_length_per_fold = 2 * max_fold_height + 2 * np.pi * self.l_radius
        n_folds = math.ceil(l_foldable_length / (2 * max_length_per_fold))
        h_folds = l_foldable_length / (4 * n_folds) - np.pi * self.l_radius

        path_pts = [pya.DPoint(0, self.ground_gap_top - self.l_coupling_distance),
                    pya.DPoint(-self.l_coupling_length/2, self.ground_gap_top - self.l_coupling_distance),
                    ]

        path_pts += self._arc_points(-self.l_coupling_length/2, self.ground_gap_top - self.l_coupling_distance - self.l_radius, self.l_radius, np.pi/2, np.pi, self.n/4)
        
        l_folds_start_y = self.ground_gap_bottom + 2 * self.l_ground_sep + self.l_radius
        l_folds_start_x = -self.l_coupling_length/2 - self.l_radius
        path_pts += [pya.DPoint(l_folds_start_x, l_folds_start_y)]
        
        i = 0
        while i < n_folds:
            path_pts += self._arc_points(l_folds_start_x - (1 + 4*i)*self.l_radius, l_folds_start_y, self.l_radius, 0, -np.pi, self.n/2)
            path_pts += [pya.DPoint(l_folds_start_x - (2 + 4*i)*self.l_radius, l_folds_start_y + h_folds)]
            path_pts += self._arc_points(l_folds_start_x - (3 + 4*i)*self.l_radius, l_folds_start_y + h_folds, self.l_radius, 0, np.pi, self.n/2)
            path_pts += [pya.DPoint(l_folds_start_x - (4 + 4*i)*self.l_radius, l_folds_start_y)]
            i += 1

        path_pts += self._arc_points(l_folds_start_x - (4*n_folds - 1)*self.l_radius, self.ground_gap_bottom + self.l_ground_sep + self.l_radius, self.l_radius, np.pi, 3*np.pi/2, self.n/4)
        path_pts += [pya.DPoint(-self.cap_region_total_width/2, self.ground_gap_bottom + self.l_ground_sep)]     
        
        l_dpath = pya.DPath(path_pts, self.l_width)
        l_polygon = l_dpath.to_itype(self.layout.dbu)
        l_region = pya.Region(l_polygon)

        path_pts_mirrored = [pya.DPoint(-pt.x, pt.y) for pt in path_pts]
        l_dpath_mirrored = pya.DPath(path_pts_mirrored, self.l_width)
        l_polygon_mirrored = l_dpath_mirrored.to_itype(self.layout.dbu)
        mirrored_region = pya.Region(l_polygon_mirrored)

        ground_path = [pya.DPoint(0, self.ground_gap_top - self.l_ground_sep),
                       pya.DPoint(0, self.ground_gap_top)]
        ground_dpath = pya.DPath(ground_path, self.l_width)
        ground_polygon = ground_dpath.to_itype(self.layout.dbu)
        ground_region = pya.Region(ground_polygon)


        return l_region + mirrored_region #+ ground_region
    
    def _make_wide_capacitor_region(self):
        cap_bottom = self.ground_gap_bottom + self.l_ground_sep - self.l_width/2
        cap_top = cap_bottom + self.cap_wide_height

        left_pad_pts = [
            pya.DPoint(-self.cap_region_total_width/2, cap_bottom),
            pya.DPoint(-self.cap_region_total_width/2, cap_top),
            pya.DPoint(-self.cap_region_total_width/2 + self.cap_inner_width, cap_top),
            pya.DPoint(-self.cap_region_total_width/2 + self.cap_inner_width, cap_bottom),
        ]

        right_pad_pts = [
            pya.DPoint(self.cap_region_total_width/2 - self.cap_inner_width, cap_bottom),
            pya.DPoint(self.cap_region_total_width/2 - self.cap_inner_width, cap_top),
            pya.DPoint(self.cap_region_total_width/2, cap_top),
            pya.DPoint(self.cap_region_total_width/2, cap_bottom),
        ]

        center_pad_pts = [
            pya.DPoint(-self.cap_inner_width/2, cap_bottom),
            pya.DPoint(-self.cap_inner_width/2, cap_top),
            pya.DPoint(self.cap_inner_width/2, cap_top),
            pya.DPoint(self.cap_inner_width/2, cap_bottom),
        ]

        bias_lead_pts = [
            pya.DPoint(-self.l_width/2, cap_bottom),
            pya.DPoint(-self.l_width/2, self.ground_gap_bottom),
            pya.DPoint(self.l_width/2, self.ground_gap_bottom),
            pya.DPoint(self.l_width/2, cap_bottom),
        ]

        left_region = pya.Region(pya.DPolygon(left_pad_pts).to_itype(self.layout.dbu))
        right_region = pya.Region(pya.DPolygon(right_pad_pts).to_itype(self.layout.dbu))
        center_region = pya.Region(pya.DPolygon(center_pad_pts).to_itype(self.layout.dbu))
        bias_lead_region = pya.Region(pya.DPolygon(bias_lead_pts).to_itype(self.layout.dbu))

        return left_region + right_region + center_region #+ bias_lead_region

    def _make_narrow_capacitor_region(self):
        return pya.Region()

    def _make_capacitor_gap_region(self):
        """Create mesh refinement region in capacitor gaps between plates."""
        cap_bottom = self.ground_gap_bottom + self.l_ground_sep - self.l_width/2
        cap_top = cap_bottom + self.cap_wide_height

        # Gap between left and center plates
        gap_left_pts = [
            pya.DPoint(-self.cap_region_total_width/2 + self.cap_outer_width, cap_bottom),
            pya.DPoint(-self.cap_region_total_width/2 + self.cap_outer_width + self.cap_wide_gap, cap_bottom),
            pya.DPoint(-self.cap_region_total_width/2 + self.cap_outer_width + self.cap_wide_gap, cap_top),
            pya.DPoint(-self.cap_region_total_width/2 + self.cap_outer_width, cap_top),
        ]
        gap_left_region = pya.Region(pya.DPolygon(gap_left_pts).to_itype(self.layout.dbu))

        # Gap between center and right plates
        gap_right_pts = [
            pya.DPoint(self.cap_inner_width/2, cap_bottom),
            pya.DPoint(self.cap_inner_width/2 + self.cap_wide_gap, cap_bottom),
            pya.DPoint(self.cap_inner_width/2 + self.cap_wide_gap, cap_top),
            pya.DPoint(self.cap_inner_width/2, cap_top),
        ]
        gap_right_region = pya.Region(pya.DPolygon(gap_right_pts).to_itype(self.layout.dbu))

        return gap_left_region + gap_right_region
    
    def _make_bias_leads(self):
        cap_bottom = self.ground_gap_bottom + self.l_ground_sep - self.l_width/2

        bias_lead_pts = [
            pya.DPoint(-self.a/2, cap_bottom),
            pya.DPoint(-self.a/2, self.ground_gap_bottom - self.cap_bias_length),
            pya.DPoint(self.a/2, self.ground_gap_bottom),
            pya.DPoint(self.a/2, cap_bottom),
        ]

        bias_lead_region = pya.Region(pya.DPolygon(bias_lead_pts).to_itype(self.layout.dbu))

        bias_gap_left_pts = [
            pya.DPoint(-self.a/2 - self.b, self.ground_gap_bottom - self.cap_bias_length),
            pya.DPoint(-self.a/2, self.ground_gap_bottom - self.cap_bias_length),
            pya.DPoint(-self.a/2, self.ground_gap_bottom),
            pya.DPoint(-self.a/2 - self.b, self.ground_gap_bottom),
        ]

        bias_gap_right_pts = [
            pya.DPoint(self.a/2 + self.b, self.ground_gap_bottom - self.cap_bias_length),
            pya.DPoint(self.a/2, self.ground_gap_bottom - self.cap_bias_length),
            pya.DPoint(self.a/2, self.ground_gap_bottom),
            pya.DPoint(self.a/2 + self.b, self.ground_gap_bottom),
        ]

        bias_gap_bottom_pts = [
            pya.DPoint(-self.a/2 - self.b, self.ground_gap_bottom - self.cap_bias_length),
            pya.DPoint(self.a/2 + self.b, self.ground_gap_bottom - self.cap_bias_length),
            pya.DPoint(self.a/2 + self.b, self.ground_gap_bottom - self.cap_bias_length - self.b),
            pya.DPoint(-self.a/2 - self.b, self.ground_gap_bottom - self.cap_bias_length - self.b),
        ]

        bias_gap_left_region = pya.Region(pya.DPolygon(bias_gap_left_pts).to_itype(self.layout.dbu))
        bias_gap_right_region = pya.Region(pya.DPolygon(bias_gap_right_pts).to_itype(self.layout.dbu))

        if self.ground_bias and not self.include_bias_resistor:
            bias_gap_bottom_region = pya.Region()  # No gap region if bias line is grounded without resistor
        else:
            bias_gap_bottom_region = pya.Region(pya.DPolygon(bias_gap_bottom_pts).to_itype(self.layout.dbu))

        return bias_lead_region, bias_gap_left_region + bias_gap_right_region + bias_gap_bottom_region