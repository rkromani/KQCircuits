# This code is part of KQCircuits
# Copyright (C) 2025 Zachary Parrott
# Copyright (C) 2023 IQM Finland Oy
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation, either version 3 of the License, or (at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see https://www.gnu.org/licenses/gpl-3.0.html.
#
# Contributions are made under the IQM Individual Contributor License Agreement.
# For more information, see: https://meetiqm.com/iqm-individual-contributor-license-agreement


from kqcircuits.pya_resolver import pya
from kqcircuits.util.parameters import Param, pdt

from kqcircuits.test_structures.test_structure import TestStructure


class Profilometer(TestStructure):
    """PCell declaration for profilometer of of Nb base and Al JJ metal layers. 
    """

    def build(self):

        layer_base_metal = self.get_layer("base_metal_gap_wo_grid")
        jj_metal = self.get_layer("SIS_junction")


        width = 450 + 50
        height = 90 + 50
        protect = pya.Region([pya.DPolygon([
            pya.DPoint(-width/2, -height/2),
            pya.DPoint(-width/2, height/2),
            pya.DPoint(width/2, height/2),
            pya.DPoint(width/2, -height/2)
            ]).to_itype(self.layout.dbu)])
        
        self.cell.shapes(self.get_layer("ground_grid_avoidance")).insert(protect)

        width = 450
        height = 90
        outer = pya.Region([pya.DPolygon([
            pya.DPoint(-width/2, -height/2),
            pya.DPoint(-width/2, height/2),
            pya.DPoint(width/2, height/2),
            pya.DPoint(width/2, -height/2)
            ]).to_itype(self.layout.dbu)])

        bars = []
        for i in range(5):
            trans = i * 40
            bars.append(pya.DPolygon([
            pya.DPoint(-width/2 + 20 + trans, -height/2 + 20),
            pya.DPoint(-width/2 + 20 + trans, -height/2 + 70),
            pya.DPoint(-width/2 + 40 + trans, -height/2 + 70),
            pya.DPoint(-width/2 + 40 + trans, -height/2 + 20),
            ]))

        bar = pya.Region([poly.to_itype(self.layout.dbu) for poly in bars])

        block = pya.DPolygon([
            pya.DPoint(10, -20),
            pya.DPoint(10, 20),
            pya.DPoint(60, 20),
            pya.DPoint(60, -20),
        ]).to_itype(self.layout.dbu)

        block2 = pya.DPolygon([
            pya.DPoint(10+110, -20),
            pya.DPoint(10+110, 20),
            pya.DPoint(60+110, 20),
            pya.DPoint(60+110, -20),
        ]).to_itype(self.layout.dbu)
        blocks = pya.Region([block, block2])
                
        nb = outer - bar - blocks
        self.cell.shapes(layer_base_metal).insert(nb)

        pad1 = pya.DPolygon([
            pya.DPoint(40 , -15),
            pya.DPoint(40 , 15),
            pya.DPoint(40 + 50, 15),
            pya.DPoint(40 + 50, -15),
        ]).to_itype(self.layout.dbu)

        pad2 = pya.DPolygon([
            pya.DPoint(40 +110, -15),
            pya.DPoint(40 +110, 15),
            pya.DPoint(40 + 50+110, 15),
            pya.DPoint(40 + 50+110, -15),
        ]).to_itype(self.layout.dbu)

        pads = pya.Region([pad1, pad2])

        self.cell.shapes(jj_metal).insert(pads)
