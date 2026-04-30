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

"""Wafer-level alignment markers element."""

import math

from kqcircuits.elements.element import Element
from kqcircuits.pya_resolver import pya
from kqcircuits.util.parameters import Param, pdt


class AlignmentMarkers(Element):
    """Wafer-level alignment markers at fixed positions relative to wafer center.

    Draws cross shapes on specified layers. All positions are in um from origin (wafer center).
    Edit marker_positions to set marker locations. Add or remove layers in build() as needed.
    Also draws a wafer outline with flat on the chip_dicing layer.
    """

    cross_arm_length = Param(pdt.TypeDouble, "Half-length of each cross arm (um)", 300)
    cross_arm_width = Param(pdt.TypeDouble, "Width of each cross arm (um)", 10)
    # Edit this list directly to set marker locations (pya.DPoint, um from wafer center)
    marker_positions = [
            pya.DPoint(30000, -2000),
            pya.DPoint(30000, 2000),
            pya.DPoint(30000, -4000),
            pya.DPoint(30000, 4000),
            pya.DPoint(32500, -2000),
            pya.DPoint(32500, 2000),
            pya.DPoint(32500, -4000),
            pya.DPoint(32500, 4000),
            pya.DPoint(-30000, -2000),
            pya.DPoint(-30000, 2000),
            pya.DPoint(-30000, -4000),
            pya.DPoint(-30000, 4000),
            pya.DPoint(-32500, -2000),
            pya.DPoint(-32500, 2000),
            pya.DPoint(-32500, -4000),
            pya.DPoint(-32500, 4000),
    ]
    wafer_rad = Param(pdt.TypeDouble, "Wafer radius (um)", 38100)
    wafer_bottom_flat_length = Param(pdt.TypeDouble, "Length of flat at wafer bottom (um)", 22000)
    wafer_outline_width = Param(pdt.TypeDouble, "Line width of wafer outline (um)", 200)

    def build(self):
        L = self.cross_arm_length
        W = self.cross_arm_width
        h_rect = pya.DBox(-L, -W/2, L, W/2)
        v_rect = pya.DBox(-W/2, -L, W/2, L)

        pts_around_cross_tl = [
            pya.DPoint(-W/2, W/2),
            pya.DPoint(-W/2, L),
            pya.DPoint(-3*W/2, L),
            pya.DPoint(-3*W/2, 3*W/2),
            pya.DPoint(-L, 3*W/2),
            pya.DPoint(-L, W/2),
        ]
        region_around_cross_tl = pya.Region(pya.DPolygon(pts_around_cross_tl).to_itype(self.layout.dbu))
        pts_around_cross_tr = [
            pya.DPoint(W/2, W/2),
            pya.DPoint(W/2, L),
            pya.DPoint(3*W/2, L),
            pya.DPoint(3*W/2, 3*W/2),
            pya.DPoint(L, 3*W/2),
            pya.DPoint(L, W/2),
        ]
        region_around_cross_tr = pya.Region(pya.DPolygon(pts_around_cross_tr).to_itype(self.layout.dbu))
        pts_around_cross_bl = [
            pya.DPoint(-W/2, -W/2),
            pya.DPoint(-W/2, -L),
            pya.DPoint(-3*W/2, -L),
            pya.DPoint(-3*W/2, -3*W/2),
            pya.DPoint(-L, -3*W/2),
            pya.DPoint(-L, -W/2),
        ]
        region_around_cross_bl = pya.Region(pya.DPolygon(pts_around_cross_bl).to_itype(self.layout.dbu))
        pts_around_cross_br = [
            pya.DPoint(W/2, -W/2),
            pya.DPoint(W/2, -L),
            pya.DPoint(3*W/2, -L),
            pya.DPoint(3*W/2, -3*W/2),
            pya.DPoint(L, -3*W/2),
            pya.DPoint(L, -W/2),
        ]
        region_around_cross_br = pya.Region(pya.DPolygon(pts_around_cross_br).to_itype(self.layout.dbu))
        region_around_cross = region_around_cross_tl + region_around_cross_tr + region_around_cross_bl + region_around_cross_br

        for pt in self.marker_positions:
            t = pya.DTrans(pya.DVector(pt))
            t_int = pya.Trans(pya.DVector(pt).to_itype(self.layout.dbu))
            self.cell.shapes(self.layout.layer(self.face()["base_metal_gap_wo_grid"])).insert(t * h_rect)
            self.cell.shapes(self.layout.layer(self.face()["base_metal_gap_wo_grid"])).insert(t * v_rect)

            self.cell.shapes(self.layout.layer(self.face()["SIS_shadow"])).insert(region_around_cross.transformed(t_int))


        # Wafer outline with flat on chip_dicing layer
        points = []
        for a in range(0, 257):
            x = math.cos(a / 128 * math.pi) * self.wafer_rad
            y = math.sin(a / 128 * math.pi) * self.wafer_rad
            if y < 0 and abs(x) <= self.wafer_bottom_flat_length / 2:
                continue
            points.append(pya.DPoint(x, y))
        if len(points) > 1:
            outline = pya.DPath(points, self.wafer_outline_width, 0, 0, True)
            dicing_layer = self.layout.layer(self.face()["chip_dicing"])
            self.cell.shapes(dicing_layer).insert(outline)
