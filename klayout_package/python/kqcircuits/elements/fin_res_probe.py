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
class FinResistanceProbe(Element):

    ground_cutout_gap = Param(pdt.TypeDouble, "Distance from features to edge of ground cutout", 50, unit="μm")

    fin_thickness = Param(pdt.TypeDouble, "Nominal fin thickness", 0.150, unit="μm")
    fin_length = Param(pdt.TypeDouble, "Fin length", 350, unit="μm")
    fin_overetch_width = Param(pdt.TypeDouble, "Width of fin overetch region", 20, unit="μm")

    probe_width = Param(pdt.TypeDouble, "Width of region probing fin resistance", 10, unit="μm")

    lead_length = Param(pdt.TypeDouble, "Length of probe leads", 400, unit="μm")
    lead_width = Param(pdt.TypeDouble, "Width of probe leads", 10, unit="μm")

    pad_width = Param(pdt.TypeDouble, "Width of probe leads", 200, unit="μm")
    pad_spacing = Param(pdt.TypeDouble, "Space between pads", 50, unit="μm")

    include_fin = Param(pdt.TypeBoolean, "Whether to include the fin in the design", True)

    n = Param(pdt.TypeInt, "Number of points for rounding", 64)

    def build(self):

        #define bottom left corner of cap as origin (0,0)
        self.ground_gap_bottom = -self.lead_length - self.ground_cutout_gap - self.pad_width
        self.ground_gap_left = -2*self.pad_width - 2*self.pad_spacing - self.ground_cutout_gap
        self.ground_gap_top = self.fin_length/2 + self.ground_cutout_gap
        self.ground_gap_right = 2*self.pad_width + 2*self.pad_spacing + self.ground_cutout_gap

        ground_cutout_pts = [
            pya.DPoint(self.ground_gap_left, self.ground_gap_bottom),
            pya.DPoint(self.ground_gap_right, self.ground_gap_bottom),
            pya.DPoint(self.ground_gap_right, self.ground_gap_top),
            pya.DPoint(self.ground_gap_left, self.ground_gap_top)
        ]
        ground_cutout = pya.DPolygon(ground_cutout_pts)
        ground_cutout = pya.Region(ground_cutout.to_itype(self.layout.dbu))

        probe_half_length = self.pad_width + 2*self.pad_spacing + self.lead_width
        probe_pts = [
            pya.DPoint(probe_half_length, self.probe_width/2),
            pya.DPoint(-probe_half_length, self.probe_width/2),
            pya.DPoint(-probe_half_length, -self.probe_width/2),
            pya.DPoint(probe_half_length, -self.probe_width/2),
            ]
        probe_region = pya.DPolygon(probe_pts)
        probe_region = pya.Region(probe_region.to_itype(self.layout.dbu))

        pad_lead_pts = [
            pya.DPoint(self.pad_spacing, self.probe_width/2),
            pya.DPoint(self.pad_spacing + self.lead_width, self.probe_width/2),
            pya.DPoint(self.pad_spacing + self.lead_width, -self.lead_length),
            pya.DPoint(self.pad_spacing + self.pad_width, -self.lead_length),
            pya.DPoint(self.pad_spacing + self.pad_width, -self.lead_length - self.pad_width),
            pya.DPoint(self.pad_spacing, -self.lead_length - self.pad_width),
        ]
        pad_lead_region = pya.DPolygon(pad_lead_pts)
        pad_lead_region = pya.Region(pad_lead_region.to_itype(self.layout.dbu))

        pad_lead_outside_pts = [
            pya.DPoint(2*self.pad_spacing + self.pad_width, self.probe_width/2),
            pya.DPoint(2*self.pad_spacing + self.lead_width + self.pad_width, self.probe_width/2),
            pya.DPoint(2*self.pad_spacing + self.lead_width + self.pad_width, -self.lead_length),
            pya.DPoint(2*(self.pad_spacing + self.pad_width), -self.lead_length),
            pya.DPoint(2*(self.pad_spacing + self.pad_width), -self.lead_length - self.pad_width),
            pya.DPoint(2*self.pad_spacing + self.pad_width, -self.lead_length - self.pad_width),
        ]
        pad_lead_outside_region = pya.DPolygon(pad_lead_outside_pts)
        pad_lead_outside_region = pya.Region(pad_lead_outside_region.to_itype(self.layout.dbu))

        pad_leads_region = pad_lead_region + pad_lead_outside_region
        mirrored = pya.Trans(pya.Trans.M90)
        pad_leads_mirrored_region = pad_leads_region.transformed(mirrored)

        self.cell.shapes(self.get_layer("base_metal_gap_wo_grid")).insert(
            ground_cutout - probe_region - pad_leads_region - pad_leads_mirrored_region
        )

        fin_pts = [
            pya.DPoint(-self.fin_thickness/2, -self.fin_length/2),
            pya.DPoint(-self.fin_thickness/2, self.fin_length/2),
            pya.DPoint(self.fin_thickness/2, self.fin_length/2),
            pya.DPoint(self.fin_thickness/2, -self.fin_length/2),
        ]
        fin_region = pya.DPolygon(fin_pts)
        fin_region = pya.Region(fin_region.to_itype(self.layout.dbu))

        if self.include_fin:
            self.cell.shapes(self.get_layer("SIS_junction")).insert(
                fin_region
            )

        fin_overetch_top_pts = [
            pya.DPoint(-self.fin_overetch_width/2, self.probe_width/2),
            pya.DPoint(-self.fin_overetch_width/2, self.fin_length/2),
            pya.DPoint(self.fin_overetch_width/2, self.fin_length/2),
            pya.DPoint(self.fin_overetch_width/2, self.probe_width/2),
        ]
        fin_overetch_top_region = pya.DPolygon(fin_overetch_top_pts)
        fin_overetch_top_region = pya.Region(fin_overetch_top_region.to_itype(self.layout.dbu))

        fin_overetch_bottom_pts = [
            pya.DPoint(-self.fin_overetch_width/2, -self.probe_width/2),
            pya.DPoint(-self.fin_overetch_width/2, -self.fin_length/2),
            pya.DPoint(self.fin_overetch_width/2, -self.fin_length/2),
            pya.DPoint(self.fin_overetch_width/2, -self.probe_width/2),
        ]
        fin_overetch_bottom_region = pya.DPolygon(fin_overetch_bottom_pts)
        fin_overetch_bottom_region = pya.Region(fin_overetch_bottom_region.to_itype(self.layout.dbu))

        self.cell.shapes(self.get_layer("SIS_shadow")).insert(
            fin_overetch_top_region + fin_overetch_bottom_region
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

