# This code is part of KQCircuits
# Copyright (C) 2021 IQM Finland Oy
#Roger Romani
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


@add_parameters_from(WaveguideCoplanar, "add_metal")
class BiasResonator(Element):

    feedline_length = Param(pdt.TypeDouble, "Feedline length", 1200, unit="μm")
    feedline_spacing = Param(pdt.TypeDouble, "Feedline spacing", 4, unit="μm")
    feedline_cutout = Param(pdt.TypeDouble, "Feedline cutout length", 50, unit="μm")
    feedline_cutout_bool = Param(pdt.TypeBoolean, "Whether to add feedline cutout", True)

    l_length = Param(pdt.TypeDouble, "Inductor length", 2885, unit="μm")
    l_width = Param(pdt.TypeDouble, "Inductor width", 4, unit="μm")
    l_gnd_cap_width = Param(pdt.TypeDouble, "Distance between inductor ground and capacitor connection", 700, unit="μm")
    l_coupling_length = Param(pdt.TypeDouble, "Inductor coupling length", 500, unit="μm")
    l_coupling_distance = Param(pdt.TypeDouble, "Inductor coupling distance", 16, unit="μm")
    l_coupling_step = Param(pdt.TypeDouble, "Inductor coupling step down away from coupling", 300, unit="μm")
    l_radius = Param(pdt.TypeDouble, "Inductor turn radius", 25, unit="μm")
    l_ground_gap = Param(pdt.TypeDouble, "Inductor ground gap", 200, unit="μm")
    l_junction_distance = Param(pdt.TypeDouble, "Inductor grounding distance from side of capacitor", 100, unit="μm")
    l_junction_width = Param(pdt.TypeDouble, "Inductor junction section width", 80, unit="μm")
    l_junction_height = Param(pdt.TypeDouble, "Center height of junction on inductor", 200, unit="μm")

    cap_center_width = Param(pdt.TypeDouble, "Capacitor center width", 200, unit="μm")
    cap_center_length = Param(pdt.TypeDouble, "Capacitor center length", 200, unit="μm")
    cap_gap = Param(pdt.TypeDouble, "Capacitor gap", 40, unit="μm")
    cap_inside_ground_distance = Param(pdt.TypeDouble, "Distance capacitor is inset into the ground", 50, unit="μm")

    """junction_bool = Param(pdt.TypeBoolean, "Whether to add junction", False)
    #total_junction_height = Param(pdt.TypeDouble, "Total junction height", 20, unit="μm", readonly=True)
    junction_pad_height = Param(pdt.TypeDouble, "Junction pad height", 10, unit="μm")
    junction_finger_length = Param(pdt.TypeDouble, "Length of junction finger", 5, unit="μm")
    junction_finger_tip_length = Param(pdt.TypeDouble, "Length of junction finger tip", 1, unit="μm")
    junction_overshoot = Param(pdt.TypeDouble, "Amount the junction hook extends beyond the finger width and finger beyond hook", 0.5, unit="μm")

    # Lumped model parameters for junction
    junction_use_lumped = Param(pdt.TypeBoolean, "Use lumped RLC model for junction instead of physical geometry", False)
    junction_lumped_inductance = Param(pdt.TypeDouble, "Junction inductance for lumped model (nH)", 16, unit="nH")
    junction_lumped_capacitance = Param(pdt.TypeDouble, "Junction capacitance for lumped model (fF)", 0.1, unit="fF")
    """

    include_inductor = Param(pdt.TypeBoolean, "Include inductor (disable for Q3D capacitance measurements)", True)
    include_capacitor = Param(pdt.TypeBoolean, "Include capacitor (disable for Q3D inductance measurements)", True)
    enable_mesh_layers = Param(pdt.TypeBoolean, "Enable mesh control layers (disable for Q3D ACRL due to ANSYS bug)", True)


    
    shadow_angle_1 = Param(pdt.TypeDouble, "Angle of shadow 1", 30, unit="deg")
    shadow_angle_2 = Param(pdt.TypeDouble, "Angle of shadow 2", 0, unit="deg")
    resist_thickness = Param(pdt.TypeDouble, "Thickness of resist", 3, unit="μm")

    n = Param(pdt.TypeInt, "Number of points for round curves", 64)

    def build(self):

        self.l_height = 0.5 * (self.l_length - self.l_gnd_cap_width - 8*self.l_radius*(np.pi/2 - 2) + self.cap_inside_ground_distance - 2 * (self.l_coupling_distance - self.l_junction_distance))
        
        self.cap_x = self.l_gnd_cap_width/2
        self.l_ground_x = -self.l_gnd_cap_width/2 

        self.ground_gap_top = -(self.b + self.a/2 + self.feedline_spacing)
        self.ground_gap_bottom = self.ground_gap_top - self.l_height - self.l_coupling_distance - self.l_width
        self.ground_gap_right = self.l_gnd_cap_width/2 + self.l_ground_gap
        self.ground_gap_left = -self.ground_gap_right

        pts = [
            pya.DPoint(self.ground_gap_left, self.ground_gap_top),
            pya.DPoint(self.ground_gap_left, self.ground_gap_bottom),
            pya.DPoint(self.ground_gap_right, self.ground_gap_bottom),
            pya.DPoint(self.ground_gap_right, self.ground_gap_top),
        ]
        ground_gap_region = pya.Region(pya.DPolygon(pts).to_itype(self.layout.dbu))


        # Conditionally create inductor region based on include_inductor flag
        if self.include_inductor:
            inductor_region = self._make_inductor()
        else:
            cutout_pts = [
                pya.DPoint(self.l_ground_x - self.l_width/2, self.ground_gap_bottom),
                pya.DPoint(self.l_ground_x - self.l_width/2, self.ground_gap_bottom + 2*self.cap_gap),
                pya.DPoint(self.l_ground_x + self.l_width/2, self.ground_gap_bottom + 2*self.cap_gap),
                pya.DPoint(self.l_ground_x + self.l_width/2, self.ground_gap_bottom),
            ]
            cutout_region = pya.Region(pya.DPolygon(cutout_pts).to_itype(self.layout.dbu))

            inductor_region = self._make_inductor() - cutout_region  # Empty region for Q3D capacitance measurements
            #inductor_region = pya.Region()

        # Conditionally create capacitor region based on include_capacitor flag
        if self.include_capacitor:
            cap_region = self._make_capacitor()
        else:
            pts = [
                pya.DPoint(self.cap_x - self.cap_gap, self.ground_gap_bottom),
                pya.DPoint(self.cap_x - self.cap_gap, self.ground_gap_bottom - self.cap_gap),
                pya.DPoint(self.cap_x + self.cap_gap, self.ground_gap_bottom - self.cap_gap),
                pya.DPoint(self.cap_x + self.cap_gap, self.ground_gap_bottom),
            ]
            cap_region = pya.Region(pya.DPolygon(pts).to_itype(self.layout.dbu))  # Empty region for Q3D capacitance measurements
        
        feedline_region = self._make_feedline()

        """if self.junction_bool:
            inductor_extension = self._make_junction()
        else:
            inductor_extension = pya.Region()"""
        

        self.cell.shapes(self.get_layer("base_metal_gap_wo_grid")).insert(
            ground_gap_region + feedline_region - inductor_region + cap_region
        )

        # Add mesh control regions for fine-grained ANSYS mesh refinement
        # Disabled for Q3D ACRL simulations due to ANSYS bug with mesh layer deletion
        if self.enable_mesh_layers:

            # mesh_2: Coarse mesh for inductor region (only when inductor is included)
            if self.include_inductor:
                self.cell.shapes(self.get_layer("mesh_2")).insert(
                    inductor_region
                )

            # mesh_3: Fine mesh in capacitor
            if self.include_capacitor:
                self.cell.shapes(self.get_layer("mesh_3")).insert(
                    cap_region
                )
        

        # add reference point
        self.add_port("feedline_a", pya.DPoint(-self.feedline_length/2, 0), pya.DVector(-1, 0))
        self.add_port("feedline_b", pya.DPoint(self.feedline_length/2, 0), pya.DVector(1, 0))
        self.refpoints["feedline_a"] = pya.DPoint(-self.feedline_length/2, 0)
        self.refpoints["feedline_b"] = pya.DPoint(self.feedline_length/2, 0)
        self.refpoints["inductor_ground"] = pya.DPoint(self.l_ground_x, self.ground_gap_bottom)

        # Add named ACRL source/sink refpoints for Q3D inductance measurements
        # These refpoints will be automatically detected by get_acrl_sim_class()
        # Format: acrl_source_<name> and acrl_sink_<name> where <name> is the net name
        if self.include_inductor:
            # Main inductor loop
            # Source: where inductor connects to capacitor (inductor endpoint)
            source_x = self.cap_x
            source_y = self.ground_gap_bottom - self.cap_inside_ground_distance
            self.refpoints["acrl_source_main_inductor"] = pya.DPoint(source_x, source_y)

            # Sink: where inductor connects to ground (placed in ground plane for good contact)
            # Place at the left edge of ground gap, extended into ground plane
            sink_x = self.ground_gap_left - 50  # 50 um into ground plane from gap edge
            sink_y = self.ground_gap_bottom - 100  # 100 um down into ground plane
            self.refpoints["acrl_sink_main_inductor"] = pya.DPoint(sink_x, sink_y)

            # Feedline to feedline measurement (if cutout enabled)
            if self.feedline_cutout_bool:
                self.refpoints["acrl_source_feedline"] = pya.DPoint(self.feedline_length/2, 0)
                self.refpoints["acrl_sink_feedline"] = pya.DPoint(-self.feedline_length/2, 0)

    @classmethod
    def get_sim_ports(cls, simulation):
        """Define simulation ports for non-ACRL simulations.

        For ACRL simulations, refpoints (acrl_source_N, acrl_sink_N) are used instead
        and automatically detected by get_acrl_sim_class().

        For non-ACRL simulations with lumped junction, this returns a lumped RLC port.
        """
        ports = []

        # If junction is in lumped model mode, add RLC port
        # (Currently junction support is commented out in BiasResonator)
        # if hasattr(simulation, 'junction_bool') and simulation.junction_bool and simulation.junction_use_lumped:
        #     ports.append(
        #         RefpointToInternalPort(
        #             refpoint="junction_signal",
        #             ground_refpoint="junction_ground",
        #             inductance=simulation.junction_lumped_inductance * 1e-9,  # nH to H
        #             capacitance=simulation.junction_lumped_capacitance * 1e-15,  # fF to F
        #             junction=True,  # Keep this for EPR calculations
        #             lumped_element=True,  # Also mark as lumped
        #             rlc_type="parallel",
        #         )
        #     )

        return ports
    
    def _arc_points(self, center_x, center_y, r, theta0, theta1, n):
        #theta = 0 is (1,0) directionreturn [
        return [
            pya.DPoint(
                center_x + r * np.cos(t),
                center_y + r * np.sin(t)
            )
            for t in [theta0 + i*(theta1-theta0)/(n-1) for i in range(int(n))]
        ]

    def _make_inductor(self):
        junction_jag_bottom_y = self.ground_gap_bottom + self.l_junction_height - self.l_junction_width/2
        junction_jag_top_y = self.ground_gap_bottom + self.l_junction_height + self.l_junction_width/2
        junction_jag_x = self.cap_x - self.l_junction_distance
        coupling_left_x = self.cap_x - self.l_coupling_length

        path_pts = [pya.DPoint(self.l_ground_x, self.ground_gap_bottom),
                    pya.DPoint(self.l_ground_x, junction_jag_bottom_y - self.l_radius)]
        path_pts += self._arc_points(self.l_ground_x + self.l_radius, junction_jag_bottom_y - self.l_radius, self.l_radius, np.pi, np.pi/2, self.n/4)
        path_pts += [pya.DPoint(self.l_ground_x + self.l_radius, junction_jag_bottom_y),
                     pya.DPoint(junction_jag_x - self.l_radius, junction_jag_bottom_y)]
        path_pts += self._arc_points(junction_jag_x - self.l_radius, junction_jag_bottom_y + self.l_radius, self.l_radius, -np.pi/2, 0, self.n/4)
        path_pts += [pya.DPoint(junction_jag_x, junction_jag_bottom_y + self.l_radius),
                     pya.DPoint(junction_jag_x, junction_jag_top_y - self.l_radius)]
        path_pts += self._arc_points(junction_jag_x - self.l_radius, junction_jag_top_y - self.l_radius, self.l_radius, 0, np.pi/2, self.n/4)
        path_pts += [pya.DPoint(junction_jag_x - self.l_radius, junction_jag_top_y),
                     pya.DPoint(self.l_ground_x + self.l_radius, junction_jag_top_y)]
        
        path_pts += self._arc_points(self.l_ground_x + self.l_radius, junction_jag_top_y + self.l_radius, self.l_radius, 3*np.pi/2, np.pi, self.n/4)
        path_pts += [pya.DPoint(self.l_ground_x, junction_jag_top_y + self.l_radius),
                     pya.DPoint(self.l_ground_x, self.ground_gap_top - self.l_coupling_distance - self.l_width - self.l_coupling_step - self.l_radius)]
        path_pts += self._arc_points(self.l_ground_x + self.l_radius, self.ground_gap_top - self.l_coupling_distance - self.l_width - self.l_coupling_step - self.l_radius, self.l_radius, np.pi, np.pi/2, self.n/4)
        path_pts += [pya.DPoint(self.l_ground_x + self.l_radius, self.ground_gap_top - self.l_coupling_distance - self.l_width - self.l_coupling_step),
                     pya.DPoint(coupling_left_x - self.l_radius, self.ground_gap_top - self.l_coupling_distance - self.l_width - self.l_coupling_step)]
        path_pts += self._arc_points(coupling_left_x - self.l_radius, self.ground_gap_top - self.l_coupling_distance - self.l_width + self.l_radius - self.l_coupling_step, self.l_radius, -np.pi/2, 0, self.n/4)
        path_pts += [pya.DPoint(coupling_left_x, self.ground_gap_top - self.l_coupling_distance - self.l_width + self.l_radius - self.l_coupling_step),
                     pya.DPoint(coupling_left_x, self.ground_gap_top - self.l_coupling_distance - self.l_width - self.l_radius)]
        path_pts += self._arc_points(coupling_left_x + self.l_radius, self.ground_gap_top - self.l_coupling_distance - self.l_width - self.l_radius, self.l_radius, np.pi, np.pi/2, self.n/4)
        path_pts += [pya.DPoint(coupling_left_x + self.l_radius, self.ground_gap_top - self.l_coupling_distance - self.l_width),
                     pya.DPoint(self.cap_x - self.l_radius, self.ground_gap_top - self.l_coupling_distance - self.l_width)]
        path_pts += self._arc_points(self.cap_x - self.l_radius, self.ground_gap_top - self.l_coupling_distance - self.l_width - self.l_radius, self.l_radius, np.pi/2, 0, self.n/4)
        path_pts += [pya.DPoint(self.cap_x, self.ground_gap_top - self.l_coupling_distance - self.l_width - self.l_radius),
                     pya.DPoint(self.cap_x, self.ground_gap_bottom - self.cap_inside_ground_distance)]
        
        

        l_dpath = pya.DPath(path_pts, self.l_width)
        l_polygon = l_dpath.to_itype(self.layout.dbu)
        l_region = pya.Region(l_polygon)
        

        return l_region
    
    def _make_capacitor(self):
        pts_cap_paddle = [
            pya.DPoint(self.cap_x - self.cap_center_width/2, self.ground_gap_bottom - self.cap_inside_ground_distance),
            pya.DPoint(self.cap_x + self.cap_center_width/2, self.ground_gap_bottom - self.cap_inside_ground_distance),
            pya.DPoint(self.cap_x + self.cap_center_width/2, self.ground_gap_bottom - self.cap_inside_ground_distance - self.cap_center_length),
            pya.DPoint(self.cap_x - self.cap_center_width/2, self.ground_gap_bottom - self.cap_inside_ground_distance - self.cap_center_length),
        ]

        cap_paddle_region = pya.Region(pya.DPolygon(pts_cap_paddle).to_itype(self.layout.dbu))

        pts_cap_gap = [
            pya.DPoint(self.cap_x - self.cap_center_width/2 - self.cap_gap, self.ground_gap_bottom - self.cap_inside_ground_distance + self.cap_gap),
            pya.DPoint(self.cap_x + self.cap_center_width/2 + self.cap_gap, self.ground_gap_bottom - self.cap_inside_ground_distance + self.cap_gap),
            pya.DPoint(self.cap_x + self.cap_center_width/2 + self.cap_gap, self.ground_gap_bottom - self.cap_inside_ground_distance - self.cap_center_length - self.cap_gap),
            pya.DPoint(self.cap_x - self.cap_center_width/2 - self.cap_gap, self.ground_gap_bottom - self.cap_inside_ground_distance - self.cap_center_length - self.cap_gap),
        ]

        cap_gap_region = pya.Region(pya.DPolygon(pts_cap_gap).to_itype(self.layout.dbu))

        pts_connection_wire = [
            pya.DPoint(self.cap_x - self.l_width/2, self.ground_gap_bottom),
            pya.DPoint(self.cap_x - self.l_width/2, self.ground_gap_bottom - self.cap_inside_ground_distance - self.cap_gap),
            pya.DPoint(self.cap_x + self.l_width/2, self.ground_gap_bottom - self.cap_inside_ground_distance - self.cap_gap),
            pya.DPoint(self.cap_x + self.l_width/2, self.ground_gap_bottom),
        ]
        cap_wire_region = pya.Region(pya.DPolygon(pts_connection_wire).to_itype(self.layout.dbu))

        pts_gap_wire_l = [
            pya.DPoint(self.cap_x - self.l_width/2, self.ground_gap_bottom),
            pya.DPoint(self.cap_x - self.l_width/2, self.ground_gap_bottom - self.cap_inside_ground_distance),
            pya.DPoint(self.cap_x - self.l_width/2 - self.cap_gap, self.ground_gap_bottom - self.cap_inside_ground_distance),
            pya.DPoint(self.cap_x - self.l_width/2 - self.cap_gap, self.ground_gap_bottom),
        ]
        cap_gap_wire_l_region = pya.Region(pya.DPolygon(pts_gap_wire_l).to_itype(self.layout.dbu))
        
        pts_gap_wire_r = [
            pya.DPoint(self.cap_x + self.l_width/2, self.ground_gap_bottom),
            pya.DPoint(self.cap_x + self.l_width/2, self.ground_gap_bottom - self.cap_inside_ground_distance),
            pya.DPoint(self.cap_x + self.l_width/2 + self.cap_gap, self.ground_gap_bottom - self.cap_inside_ground_distance),
            pya.DPoint(self.cap_x + self.l_width/2 + self.cap_gap, self.ground_gap_bottom),
        ]
        cap_gap_wire_r_region = pya.Region(pya.DPolygon(pts_gap_wire_r).to_itype(self.layout.dbu))
        

        return cap_gap_region - cap_paddle_region - cap_wire_region + cap_gap_wire_l_region + cap_gap_wire_r_region

    def _make_feedline(self):
        ground_gap_bottom = -(self.l_height + self.l_coupling_distance + self.feedline_spacing + self.b + self.a/2)
        ground_gap_top = -(self.b + self.a/2  +self.feedline_spacing)
    
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