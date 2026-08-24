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
from kqcircuits.elements.waveguide_composite import WaveguideComposite, Node
from kqcircuits.junctions.rkr_bridge_junction_2 import RKRBridge2
from kqcircuits.util.refpoints import RefpointToInternalPort
from kqcircuits.util.label import produce_label, LabelOrigin

import numpy as np
import math


@add_parameters_from(WaveguideCoplanar, "add_metal")
class MetCircle(Element):
    feedline_length = Param(pdt.TypeDouble, "Feedline length", 1200, unit="μm")
    feedline_spacing = Param(pdt.TypeDouble, "Feedline spacing", 10, unit="μm")
    feedline_coupling_ground_spacing = Param(pdt.TypeDouble, "Feedline coupling ground spacing", 10, unit="μm")
    feedline_cutout = Param(pdt.TypeDouble, "Feedline cutout length", 50, unit="μm")
    feedline_cutout_bool = Param(pdt.TypeBoolean, "Whether to add feedline cutout", False)

    res_length = Param(pdt.TypeDouble, "Length of readout resonator CPW", 3950, unit="μm")
    res_coupling_length = Param(pdt.TypeDouble, "Length of readout resonator coupling section", 250, unit="μm")
    res_coupling_spacing = Param(pdt.TypeDouble, "Spacing of readout resonator coupling section", 26, unit="μm")
    include_res = Param(pdt.TypeBoolean, "Whether to include readout resonator", True)

    coupler_angle = Param(pdt.TypeDouble, "Angle of the coupler section", 60, unit="deg")
    coupler_gap_angle = Param(pdt.TypeDouble, "Angle of the coupler gap section", 10, unit="deg")
    coupler_cap_spacing = Param(pdt.TypeDouble, "Distance between the coupler and capacitor", 7, unit="μm")
    coupler_gap = Param(pdt.TypeDouble, "Ground gap around the coupler", 10, unit="μm")
    coupler_width = Param(pdt.TypeDouble, "Width of the coupler section", 30, unit="μm")
    coupler_lead_in = Param(pdt.TypeDouble, "Length of the coupler lead-in section", 150, unit="μm")

    cap_diameter = Param(pdt.TypeDouble, "Diameter of the capacitor", 100, unit="μm")
    cap_gap = Param(pdt.TypeDouble, "Gap of the capacitor", 20, unit="μm")
    cap_center_y = Param(pdt.TypeDouble, "Center y-coordinate of the capacitor", -1500, unit="μm")

    met_bridge_width = Param(pdt.TypeDouble, "Width/thickness of the MET bridge", 0.15, unit="μm")
    met_bridge_length = Param(pdt.TypeDouble, "Length of the MET bridge", 4, unit="μm")


    enable_mesh_layers = Param(pdt.TypeBoolean, "Enable mesh control layers for ANSYS", False)
    enable_rlc = Param(pdt.TypeBoolean, "Whether to add RLC elements for modeling", False)
    rlc_coupler_c = Param(pdt.TypeDouble, "Coupling capacitor value for RLC model", 8.8, unit="fF")
    rlc_met_c = Param(pdt.TypeDouble, "MET capacitor value for RLC model", 154, unit="fF")
    rlc_met_l = Param(pdt.TypeDouble, "MET inductor value for RLC model", 8.1, unit="nH")

    n = Param(pdt.TypeInt, "Number of points for rounding", 64)

    def build(self):

        feedline_region = self._make_feedline()
        
        self.coupler_end_x = self.cap_diameter/2 + self.coupler_cap_spacing + self.coupler_width + self.coupler_gap
        node_coupling_feedline_start = Node(pya.DPoint(self.coupler_end_x + self.coupler_lead_in - self.res_coupling_length, -self.res_coupling_spacing))
        node_coupling_feedline_end = Node(pya.DPoint(self.coupler_end_x + self.coupler_lead_in, -self.res_coupling_spacing))
        node_coupling_cap_start = Node(pya.DPoint(self.coupler_end_x + self.coupler_lead_in, self.cap_center_y))
        node_coupling_cap_end = Node(pya.DPoint(self.coupler_end_x - self.coupler_gap, self.cap_center_y))
        
        def my_route(extra_length):
            return [
                node_coupling_feedline_start,
                node_coupling_feedline_end,
                Node(pya.DPoint(self.coupler_end_x + self.coupler_lead_in, self.cap_center_y), length_before=extra_length),
                node_coupling_cap_end
            ]

        if self.include_res:
            WaveguideComposite.produce_fixed_length_waveguide(
                self, 
                my_route, initial_guess=300.0, length=self.res_length, 
                r=100
            )

        """if self.res_cap_coupling:
            self.insert_cell(
                    WaveguideComposite, 
                    nodes=[
                        Node(pya.DPoint(self.fin_center_spacing/2 + self.coupler_lead_in - self.res_coupling_length*1.1, -self.res_coupling_spacing)),
                        node_coupling_feedline_start
                    ],
                a = 0,
                b = self.b + self.a/2
            )"""

        cap_inner_pts = self._circle_points(0, self.cap_center_y, self.cap_diameter/2, self.n)
        cap_outer_pts = self._circle_points(0, self.cap_center_y, self.cap_diameter/2 + self.cap_gap, self.n)
        cap_inner_region = pya.Region(pya.DPolygon(cap_inner_pts).to_itype(self.layout.dbu))
        cap_outer_region = pya.Region(pya.DPolygon(cap_outer_pts).to_itype(self.layout.dbu))
        cap_gap_region = cap_outer_region - cap_inner_region

        coupler_inner_ir = self.cap_diameter/2 + self.coupler_cap_spacing
        coupler_inner_or = coupler_inner_ir + self.coupler_width
        coupler_inner_pts = self._arc_annulus_points(0, self.cap_center_y, coupler_inner_ir, coupler_inner_or,
                                                      np.deg2rad(-self.coupler_angle/2), np.deg2rad(self.coupler_angle/2), self.n)
        if coupler_inner_ir - self.coupler_gap > self.cap_diameter/2:
            coupler_outer_ir = coupler_inner_ir - self.coupler_gap
        else:
            coupler_outer_ir = self.cap_diameter/2
        coupler_outer_pts = self._arc_annulus_points(0, self.cap_center_y, coupler_outer_ir, coupler_inner_or + self.coupler_gap,
                                                      np.deg2rad(-self.coupler_angle/2 - self.coupler_gap_angle), np.deg2rad(self.coupler_angle/2 + self.coupler_gap_angle), self.n)
        coupler_cpw_extension_pts = [
            pya.DPoint(coupler_inner_ir, self.cap_center_y - self.a/2),
            pya.DPoint(coupler_inner_or + self.coupler_lead_in, self.cap_center_y - self.a/2),
            pya.DPoint(coupler_inner_or + self.coupler_lead_in, self.cap_center_y + self.a/2),
            pya.DPoint(coupler_inner_ir, self.cap_center_y + self.a/2)
        ]
        coupler_inner_region = pya.Region(pya.DPolygon(coupler_inner_pts).to_itype(self.layout.dbu))
        coupler_outer_region = pya.Region(pya.DPolygon(coupler_outer_pts).to_itype(self.layout.dbu))
        if self.include_res:
            coupler_cpw_extension_region = pya.Region(pya.DPolygon(coupler_cpw_extension_pts).to_itype(self.layout.dbu))
        else:
            coupler_cpw_extension_region = pya.Region()
        coupler_region = coupler_outer_region - coupler_inner_region - coupler_cpw_extension_region

        met_coupler_metal = coupler_inner_region + coupler_cpw_extension_region + cap_inner_region
        met_coupler_gap = coupler_outer_region + cap_outer_region
        met_coupler_etch_region = met_coupler_gap - met_coupler_metal

        coord = pya.DTrans(1, False, -self.cap_diameter/2 - self.cap_gap/2, self.cap_center_y)
        pad_height = 6
        pad_width = 10
        palm_width = 7
        taper_width = 10
        if not self.enable_rlc: 
            self.insert_cell(
                RKRBridge2, coord, f"JJ", 
                wiring_pad_bool=False,
                pad_height=pad_height, pad_width=pad_width, 
                palm_width=palm_width, taper_base=taper_width, 
                bridge_length=self.met_bridge_length,
                bridge_width=self.met_bridge_width, 
                pad_offset = self.cap_gap/2 + 1, 
                taper_height = self.cap_gap/2, 
                taper_width = taper_width,
                #**element_params[i],
            )


        self.cell.shapes(self.get_layer("base_metal_gap_wo_grid")).insert(
            feedline_region + met_coupler_etch_region
        )


        rlc_met_pts = [
            pya.DPoint(-self.cap_diameter/2 + self.cap_gap/2, self.cap_center_y + pad_width/2),
            pya.DPoint(-self.cap_diameter/2 + self.cap_gap/2, self.cap_center_y - pad_width/2),
            pya.DPoint(-self.cap_diameter/2 - 3*self.cap_gap/2, self.cap_center_y - pad_width/2),
            pya.DPoint(-self.cap_diameter/2 - 3*self.cap_gap/2, self.cap_center_y + pad_width/2),
        ]
        if self.enable_rlc:
            rlc_met_region = pya.Region(pya.DPolygon(rlc_met_pts).to_itype(self.layout.dbu))
        else:
            rlc_met_region = pya.Region()

        self.cell.shapes(self.get_layer("lumped_rlc")).insert(
            rlc_met_region
        )

        """mesh_coupler_pts = [
            pya.DPoint(self.fin_center_spacing/2 + self.coupler_lead_in - self.res_coupling_length, self.a + self.b),
            pya.DPoint(self.fin_center_spacing/2 + self.coupler_lead_in, self.a + self.b),
            pya.DPoint(self.fin_center_spacing/2 + self.coupler_lead_in, -self.res_coupling_spacing -2*self.a - 2*self.b),
            pya.DPoint(self.fin_center_spacing/2 + self.coupler_lead_in - self.res_coupling_length, -self.res_coupling_spacing -2*self.a - 2*self.b),
            ]
        mesh_coupler_region = pya.Region(pya.DPolygon(mesh_coupler_pts).to_itype(self.layout.dbu))
        self.cell.shapes(self.get_layer("mesh_1")).insert(
            mesh_coupler_region
        )"""

        # Feedline ports for wave simulations
        self.add_port("feedline_a", pya.DPoint(-self.feedline_length/2, 0), pya.DVector(-1, 0))
        self.add_port("feedline_b", pya.DPoint(self.feedline_length/2, 0), pya.DVector(1, 0))

        # RLC port locations for lumped element boundaries in ANSYS.
        # The fin gaps cut through the metal strips in the X direction, so the directed
        # line (signal -> ground) must span the rlc face horizontally (left to right edge).
        # MET (inductor + capacitor in parallel): left and right edges of rlc_met_region
        self.refpoints["rlc_met_signal"] = pya.DPoint(
            -self.cap_diameter/2 - 3*self.cap_gap/2,
            self.cap_center_y - pad_width/2
        )
        self.refpoints["rlc_met_ground"] = pya.DPoint(
            -self.cap_diameter/2 + self.cap_gap/2,
            self.cap_center_y - pad_width/2
        )
        self.refpoints["coupler"] = pya.DPoint( (coupler_inner_or + coupler_inner_ir)/2,0)

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
        #source_x = -self.l_connection_spacing/2
        #source_y = self.ground_gap_bottom
        #self.refpoints["acrl_source_main_inductor"] = pya.DPoint(source_x, source_y)

        # Sink: at inductor ground connection (top center)
        #sink_x = self.l_connection_spacing/2
        #sink_y = self.ground_gap_bottom
        #self.refpoints["acrl_sink_main_inductor"] = pya.DPoint(sink_x, sink_y)

        # Capacitor internal port refpoint for Q3D capacitance measurements
        #self.refpoints["capacitor_signal"] = pya.DPoint(0, (self.ground_gap_bottom_cap + self.ground_gap_bottom)/2)

        #self.refpoints["bias_port"] = pya.DPoint(0, bias_line_end_y)

        self.add_port("feedline_a", pya.DPoint(-self.feedline_length/2, 0), pya.DVector(-1, 0))
        self.add_port("feedline_b", pya.DPoint(self.feedline_length/2, 0), pya.DVector(1, 0))
        self.refpoints["feedline_a"] = pya.DPoint(-self.feedline_length/2, 0)
        self.refpoints["feedline_b"] = pya.DPoint(self.feedline_length/2, 0)
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
                float(center_x + r * np.cos(t)),
                float(center_y + r * np.sin(t))
            )
            for t in [theta0 + i*(theta1-theta0)/(n-1) for i in range(int(n))]
        ]

    def _circle_points(self, center_x, center_y, r, n):
        return self._arc_points(center_x, center_y, r, 0, 2*np.pi, n)

    def _arc_annulus_points(self, center_x, center_y, r_i, r_o, theta0, theta1, n):
        #theta = 0 is (1,0) direction
        return [
            pya.DPoint(
                float(center_x + r_i * np.cos(t)),
                float(center_y + r_i * np.sin(t))
            )
            for t in [theta0 + i*(theta1-theta0)/(n-1) for i in range(int(n))]
        ] + [
            pya.DPoint(
                float(center_x + r_o * np.cos(t)),
                float(center_y + r_o * np.sin(t))
            )
            for t in [theta1 - i*(theta1-theta0)/(n-1) for i in range(int(n))]
        ]

