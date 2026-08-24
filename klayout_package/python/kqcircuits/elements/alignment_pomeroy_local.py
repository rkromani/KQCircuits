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
import os

from kqcircuits.elements.element import Element
from kqcircuits.pya_resolver import pya
from kqcircuits.util.parameters import Param, pdt


class AlignmentPomeroyLocal(Element):

    # Edit this list directly to set marker locations (pya.DPoint, um from wafer center)
    marker_positions = [
            pya.DPoint(0 - 2500, 0 - 2500), #offset by 2500
    ]
    positive_marks = Param(pdt.TypeBoolean, "Whether the marks are positive or negative", False)

    def build(self):           
        # Load the RF SQUID design from OAS file, remapping layer 1 -> base_metal_gap_wo_grid
        marks_layout = pya.Layout()
        marks_path = os.path.join(os.path.dirname(__file__), "..", "elements", "PomeroyAlignmentLocal.gds")
        marks_layout.read(marks_path)
        marks_cell = marks_layout.top_cell()
        src_layer = marks_layout.layer(1, 0)
        src_dbu = marks_layout.dbu
        offset = int(round(0 / src_dbu))   # chip center in DB units
        half_size = int(round(300 / src_dbu))
        gap_box = pya.Region(pya.Box(offset - half_size, offset - half_size, offset + half_size, offset + half_size))
        marks_region = pya.Region(marks_cell.begin_shapes_rec(src_layer))
        t_int = pya.Trans(pya.DVector(self.marker_positions[0]).to_itype(self.layout.dbu))
        subtracted_marks_region = gap_box - marks_region.transformed(t_int)

        if self.positive_marks:
            self.cell.shapes(self.layout.layer(self.face()["base_metal_gap_wo_grid"])).insert(subtracted_marks_region)
        else:
            self.cell.shapes(self.layout.layer(self.face()["base_metal_gap_wo_grid"])).insert(marks_region.transformed(t_int))


        """# Wafer outline with flat on chip_dicing layer
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
            self.cell.shapes(dicing_layer).insert(outline)"""
