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
class PomeroyCap(Element):

    ground_cutout_width = Param(pdt.TypeDouble, "Width of ground cutout", 100, unit="μm")
    ground_cutout_height = Param(pdt.TypeDouble, "Height of ground cutout", 100, unit="μm")
    ground_radius = Param(pdt.TypeDouble, "Radius of ground cutout corners", 5, unit="μm")

    cap_width = Param(pdt.TypeDouble, "Width of capacitor body", 10, unit="μm")
    cap_height = Param(pdt.TypeDouble, "Height of capacitor body", 10, unit="μm")

    lead_length = Param(pdt.TypeDouble, "Length of capacitor leads defined in e beam", 15, unit="μm")
    lead_width = Param(pdt.TypeDouble, "Width of capacitor leads defined in e beam", 0.1, unit="μm")

    connection_leg_length = Param(pdt.TypeDouble, "Length of legs on the wiring layer in the connection region", 5, unit="μm")
    connection_leg_width = Param(pdt.TypeDouble, "Width of legs on the wiring layer in the connection region", 4, unit="μm")
    connection_leg_offset = Param(pdt.TypeDouble, "Offset between the connection regions in the e beam and wiring layer, wiring layer is thinner", 1, unit="μm")
    connection_leadin_length = Param(pdt.TypeDouble, "Length of leadin wires on the wiring layer from ground gap to connection region", 20, unit="μm")

    include_ebeam = Param(pdt.TypeBoolean, "Whether to include the e beam capacitor definition layer", True)

    enable_mesh_layers = Param(pdt.TypeBoolean, "Enable mesh control layers for ANSYS", True)
    enable_rlc = Param(pdt.TypeBoolean, "Enable RLC layers for simulations", True)

    n = Param(pdt.TypeInt, "Number of points for rounding", 64)

    def build(self):

        #define bottom left corner of cap as origin (0,0)
        self.ground_gap_bottom = -self.lead_length - self.connection_leadin_length
        self.ground_gap_left = -self.lead_length - self.connection_leadin_length
        self.ground_gap_top = self.ground_gap_bottom + self.ground_cutout_height
        self.ground_gap_right = self.ground_gap_left + self.ground_cutout_width

        ground_cutout_pts = [
            pya.DPoint(self.ground_gap_left, self.ground_gap_bottom),
            pya.DPoint(self.ground_gap_right, self.ground_gap_bottom),
            pya.DPoint(self.ground_gap_right, self.ground_gap_top),
            pya.DPoint(self.ground_gap_left, self.ground_gap_top)
        ]
        ground_cutout = pya.DPolygon(ground_cutout_pts)
        ground_cutout = pya.Region(ground_cutout.to_itype(self.layout.dbu))
        ground_cutout.round_corners(self.ground_radius / self.layout.dbu, self.ground_radius / self.layout.dbu, self.n)

        region_coupler_wiring, region_coupler_ebeam = self._make_coupling_region()

        trans = pya.Trans(pya.Vector(0, 0))
        rotation = pya.Trans(pya.Trans.R270)
        
        region_coupler_wiring_rotated = region_coupler_wiring.transformed(rotation)
        region_coupler_ebeam_rotated = region_coupler_ebeam.transformed(rotation)
        #region_coupler_ebeam_rotated = region_coupler_ebeam.transformed(trans)

        self.cell.shapes(self.get_layer("base_metal_gap_wo_grid")).insert(
            ground_cutout - region_coupler_wiring - region_coupler_wiring_rotated
        )

        cap_pts = [
            pya.DPoint(-self.lead_width/2, -self.lead_width/2),
            pya.DPoint(-self.lead_width/2, self.cap_height-self.lead_width/2),
            pya.DPoint(self.cap_width-self.lead_width/2, self.cap_height-self.lead_width/2),
            pya.DPoint(self.cap_width-self.lead_width/2, -self.lead_width/2)
        ]
        cap_region = pya.DPolygon(cap_pts)
        cap_region = pya.Region(cap_region.to_itype(self.layout.dbu))

        if self.include_ebeam:
            self.cell.shapes(self.get_layer("SIS_junction")).insert(
                cap_region + region_coupler_ebeam + region_coupler_ebeam_rotated
            )

        """coupling_mesh_pts = [
            pya.DPoint(self.l_coupling_length/2 + self.l_radius, self.a/2 + self.b),
            pya.DPoint(self.l_coupling_length/2 + self.l_radius, self.ground_gap_top - self.l_coupling_distance - self.l_width),
            pya.DPoint(-self.l_coupling_length/2 - self.l_radius, self.ground_gap_top - self.l_coupling_distance - self.l_width),
            pya.DPoint(-self.l_coupling_length/2 - self.l_radius, self.a/2 + self.b)
        ]
        coupling_mesh_region = pya.Region(pya.DPolygon(coupling_mesh_pts).to_itype(self.layout.dbu))"""
        """
        # Add mesh control regions for fine-grained ANSYS mesh refinement
        # Disabled for Q3D ACRL simulations due to ANSYS bug with mesh layer deletion
        if self.enable_mesh_layers:
            # mesh_2: Mesh over inductor region
            #self.cell.shapes(self.get_layer("mesh_2")).insert(inductor_region)
            self.cell.shapes(self.get_layer("mesh_1")).insert(coupling_mesh_region)"""

        if self.enable_rlc:
            rlc_pts = [
                pya.DPoint(-self.connection_leg_width/2, -self.lead_length),
                pya.DPoint(self.connection_leg_width/2, -self.lead_length),
                pya.DPoint(self.connection_leg_width/2, self.connection_leg_width/2),
                pya.DPoint(-self.lead_length, self.connection_leg_width/2),
                pya.DPoint(-self.lead_length, -self.connection_leg_width/2),
                pya.DPoint(-self.connection_leg_width/2, -self.connection_leg_width/2),
            ]
            rlc_region = pya.Region(pya.DPolygon(rlc_pts).to_itype(self.layout.dbu))
            self.cell.shapes(self.get_layer("lumped_rlc")).insert(rlc_region)

            # Refpoints for InternalPort placement in ANSYS eigenmode simulations.
            # Signal is on the center conductor (y=0); ground is on the bottom ground plane.
            # Placed at the inner edge of each cutout so they sit on actual metal.
            self.refpoints["cap_signal"] = pya.DPoint(-self.lead_length, 0)
            self.refpoints["cap_ground"] = pya.DPoint(0, -self.lead_length)

        self.refpoints["cap_a"] = pya.DPoint(-self.connection_leadin_length - self.lead_length, 0)
        self.refpoints["cap_b"] = pya.DPoint(0, -self.connection_leadin_length - self.lead_length)
    

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
    
    def _make_coupling_region(self):
        pts_lead_in = [
            pya.DPoint(-self.connection_leg_width/2, self.ground_gap_bottom),
            pya.DPoint(self.connection_leg_width/2, self.ground_gap_bottom),
            pya.DPoint(self.connection_leg_width/2, self.ground_gap_bottom + self.connection_leadin_length),
            pya.DPoint(-self.connection_leg_width/2, self.ground_gap_bottom + self.connection_leadin_length),
        ]
        region_lead_in = pya.Region(pya.DPolygon(pts_lead_in).to_itype(self.layout.dbu))

        pts_horizontal_leg_wiring = [
            pya.DPoint(-self.connection_leg_length, self.ground_gap_bottom + self.connection_leadin_length - self.connection_leg_width/2),
            pya.DPoint(-self.connection_leg_length, self.ground_gap_bottom + self.connection_leadin_length + self.connection_leg_width/2),
            pya.DPoint(self.connection_leg_length, self.ground_gap_bottom + self.connection_leadin_length + self.connection_leg_width/2),
            pya.DPoint(self.connection_leg_length, self.ground_gap_bottom + self.connection_leadin_length - self.connection_leg_width/2),
        ]
        region_horizontal_leg_wiring = pya.Region(pya.DPolygon(pts_horizontal_leg_wiring).to_itype(self.layout.dbu))
        region_horizontal_leg_wiring.round_corners(self.connection_leg_width/(2 * self.layout.dbu), self.connection_leg_width/(2 * self.layout.dbu), self.n)

        region_coupler_wiring = region_lead_in + region_horizontal_leg_wiring

        pts_lead = [
            pya.DPoint(-self.lead_width/2, -self.lead_width/2),
            pya.DPoint(-self.lead_width/2, -self.lead_length),
            pya.DPoint(self.lead_width/2, -self.lead_length),
            pya.DPoint(self.lead_width/2, -self.lead_width/2)
        ]
        region_lead = pya.Region(pya.DPolygon(pts_lead).to_itype(self.layout.dbu))

        pts_connection_horizontal_leg_ebeam = [
            pya.DPoint(-self.connection_leg_length - self.connection_leg_offset, self.ground_gap_bottom + self.connection_leadin_length - self.connection_leg_width/2 - self.connection_leg_offset),
            pya.DPoint(-self.connection_leg_length - self.connection_leg_offset, self.ground_gap_bottom + self.connection_leadin_length + self.connection_leg_width/2 + self.connection_leg_offset),
            pya.DPoint(self.connection_leg_length + self.connection_leg_offset, self.ground_gap_bottom + self.connection_leadin_length + self.connection_leg_width/2 + self.connection_leg_offset),
            pya.DPoint(self.connection_leg_length + self.connection_leg_offset, self.ground_gap_bottom + self.connection_leadin_length - self.connection_leg_width/2 - self.connection_leg_offset),
        ]
        region_connection_horizontal_leg_ebeam = pya.Region(pya.DPolygon(pts_connection_horizontal_leg_ebeam).to_itype(self.layout.dbu))
        region_connection_horizontal_leg_ebeam.round_corners((self.connection_leg_width + 2 * self.connection_leg_offset)/(2 * self.layout.dbu), (self.connection_leg_width + 2 * self.connection_leg_offset)/(2 * self.layout.dbu), self.n)
        
        pts_connection_vertical_leg_ebeam = [
            pya.DPoint(-self.connection_leg_width/2 - self.connection_leg_offset, self.ground_gap_bottom + self.connection_leadin_length + self.connection_leg_width/2 + self.connection_leg_offset),
            pya.DPoint(self.connection_leg_width/2 + self.connection_leg_offset, self.ground_gap_bottom + self.connection_leadin_length + self.connection_leg_width/2 + self.connection_leg_offset),
            pya.DPoint(self.connection_leg_width/2 + self.connection_leg_offset, self.ground_gap_bottom + self.connection_leadin_length - self.connection_leg_width/2 - self.connection_leg_length - self.connection_leg_offset),
            pya.DPoint(-self.connection_leg_width/2 - self.connection_leg_offset, self.ground_gap_bottom + self.connection_leadin_length - self.connection_leg_width/2 - self.connection_leg_length - self.connection_leg_offset),
        ]
        region_connection_vertical_leg_ebeam = pya.Region(pya.DPolygon(pts_connection_vertical_leg_ebeam).to_itype(self.layout.dbu))
        region_connection_vertical_leg_ebeam.round_corners((self.connection_leg_width + 2 * self.connection_leg_offset)/(2 * self.layout.dbu), (self.connection_leg_width + 2 * self.connection_leg_offset)/(2 * self.layout.dbu), self.n)

        region_coupler_ebeam = region_lead + region_connection_horizontal_leg_ebeam + region_connection_vertical_leg_ebeam

        region_coupler_ebeam.merge()
        region_coupler_wiring.merge()

        return region_coupler_wiring, region_coupler_ebeam

