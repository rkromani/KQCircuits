# This code is part of KQCircuits
# Copyright (C) 2026 Roger Romani
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

from kqcircuits.chips.chip import Chip
from kqcircuits.pya_resolver import pya
from kqcircuits.elements.chip_frame import ChipFrame
from kqcircuits.elements.launcher import Launcher
from kqcircuits.elements.waveguide_coplanar import WaveguideCoplanar
from kqcircuits.elements.waveguide_composite import WaveguideComposite, Node
from kqcircuits.elements.waveguide_coplanar_splitter import WaveguideCoplanarSplitter, t_cross_parameters
from kqcircuits.elements.fin_met import FinMet
from kqcircuits.elements.bias_resonator_2 import BiasResonator2
from kqcircuits.elements.finger_capacitor_ground_v3 import FingerCapacitorGroundV3
from kqcircuits.util.parameters import Param, pdt, add_parameters_from, add_parameter
from kqcircuits.test_structures.profilometer import Profilometer
from kqcircuits.util.label import produce_label, LabelOrigin

from kqcircuits.test_structures.test_structure import TestStructure
from kqcircuits.elements.element import Element

from kqcircuits.util.library_helper import load_libraries

import os
import numpy as np


@add_parameters_from(
    ChipFrame,
    box=pya.DBox(pya.DPoint(0, 0), pya.DPoint(7500, 7500)),
    chip_dicing_width=50,
    chip_dicing_in_base_metal=True,
)
@add_parameters_from(
    Chip,
    face_boxes=[None, pya.DBox(pya.DPoint(0, 0), pya.DPoint(5200, 5200))],
    frames_dice_width=[50, 50],
    name_brand="RKR",
    name_brand_size = 200,
    name_chip="PRT",
    frames_marker_dist=[250, 250],
    name_mask="tt",
    name_copy="",
    marker_types=[""] * 8,
)

# @add_parameters_from(Junction, "junction_type")
# @add_parameters_from(Junction, "junction_type")


class PomeroyTestStructuresChip(Chip):
    # CPW parameters for resonator and capacitor
    

    def produce_ground_grid(self):
        # no ground grid on test junction chip
        pass

    def build(self):
        chip_region = pya.Region(pya.DPolygon(pya.DBox(0, 0, 7500e3, 7500e3)))



        # Load the RF SQUID design from OAS file, remapping layer 1 -> base_metal_gap_wo_grid
        testdie_layout = pya.Layout()
        testdie_path = os.path.join(os.path.dirname(__file__), "..", "elements", "PomeroyTestDie.gds")
        testdie_layout.read(testdie_path)
        testdie_cell = testdie_layout.top_cell()
        src_layer = testdie_layout.layer(1, 0)
        testdie_region = pya.Region(testdie_cell.begin_shapes_rec(src_layer))

        # Build 6mm x 6mm gap centered on chip, then subtract imported design
        src_dbu = testdie_layout.dbu
        offset = int(round(3750 / src_dbu))   # chip center in DB units
        half_size = int(round(3050 / src_dbu)) # 3000 um = half of 6mm
        testdie_region_centered = testdie_region.transformed(pya.Trans(offset, offset))
        gap_box = pya.Region(pya.Box(offset - half_size, offset - half_size, offset + half_size, offset + half_size))
        gap_result = gap_box - testdie_region_centered
        self.cell.shapes(self.get_layer("base_metal_gap_wo_grid", 0)).insert(gap_result)

        src_layer_2 = testdie_layout.layer(2, 0)
        sis_region = pya.Region(testdie_cell.begin_shapes_rec(src_layer_2))
        trans = pya.DTrans(pya.DVector(3750, 3750))
        self.cell.shapes(self.get_layer("SIS_junction", 0)).insert(sis_region, trans)
            