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
from kqcircuits.junctions.rkr_hook_junction_2 import RKRHook2
from kqcircuits.elements.alignment_pomeroy_local import AlignmentPomeroyLocal
from kqcircuits.util.parameters import Param, pdt, add_parameters_from, add_parameter
from kqcircuits.test_structures.profilometer import Profilometer
from kqcircuits.util.label import produce_label, LabelOrigin

from kqcircuits.test_structures.test_structure import TestStructure
from kqcircuits.elements.element import Element

from kqcircuits.util.library_helper import load_libraries

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
    name_chip="JTH",
    frames_marker_dist=[250, 250],
    name_mask="tt",
    name_copy="",
    marker_types=[""] * 8,
)

# @add_parameters_from(Junction, "junction_type")
# @add_parameters_from(Junction, "junction_type")


class JunctionHookTestChip(Chip):
    # CPW parameters for resonator and capacitor
    a = Param(pdt.TypeDouble, "CPW center conductor width", 10, unit="μm")
    b = Param(pdt.TypeDouble, "CPW gap width", 5.85, unit="μm")

    a_launcher = Param(pdt.TypeDouble, "Pad CPW trace center", 200, unit="μm")
    b_launcher = Param(pdt.TypeDouble, "Pad CPW trace gap", 153, unit="μm")
    launcher_width = Param(pdt.TypeDouble, "Pad extent", 250, unit="μm")
    taper_length = Param(pdt.TypeDouble, "Tapering length", 200, unit="μm")
    launcher_frame_gap = Param(pdt.TypeDouble, "Gap at chip frame", 100, unit="μm")
    launcher_indent = Param(pdt.TypeDouble, "Chip edge to pad port", 975, unit="μm")

    wiring_pads = Param(pdt.TypeBoolean, "Whether to use wiring layer pads", True)
    
    date_label = Param(pdt.TypeString, "Date/version label printed on chip", "")
    label_text = Param(pdt.TypeString, "Text to label chip with", "")
    

    # parameters to pass to junctions
    # small junctions
    #Q_finger_width = Param(pdt.TypeDouble, "Width of the finger.", 0.136, unit="μm")
    #Q_bridge_gap = Param(pdt.TypeDouble, "Gap between finger and hook.", 0.15, unit="μm")
    #Q_hook_thickness = Param(pdt.TypeDouble, "Thickness of hook on catch.", 0.100, unit="μm")

    # SQUID junctions
    #S_finger_width = Param(pdt.TypeDouble, "Width of the finger.", 1.496, unit="μm")
    #S_bridge_gap = Param(pdt.TypeDouble, "Gap between finger and hook.", 0.15, unit="μm")
    #S_taper = Param(pdt.TypeDouble, "Width of fixed finger.", 2.0, unit="μm")

    def produce_ground_grid(self):
        # no ground grid on test junction chip
        pass

    def build(self):
        # when not running as a macro in KLayout have to load the kqc libraries
        #load_libraries(path=Qubit.LIBRARY_PATH)
        #qubit_cell = self.layout.create_cell("BR1", Qubit.LIBRARY_NAME)

        # create a box to subtract from, all the move and Box dimensions need to be in nanometers?
        chip_region = pya.Region(pya.DPolygon(pya.DBox(0, 0, 7500e3, 7500e3)))

        # layer 1/0 as exported from HFSS
        # Get the different layers that are exported
        #qubit_shapes_base_metal_gap_wo_grid = qubit_cell.shapes(self.layout.layer(1, 0))
        #qubit_shapes_ground_grid_avoidance = qubit_cell.shapes(self.layout.layer(2, 0))

        #pattern = pya.Region(qubit_shapes_base_metal_gap_wo_grid).moved(2600e3, 2600e3)
        #difference_pattern = chip_region - pattern
        #protection_pattern = pya.Region(qubit_shapes_ground_grid_avoidance).moved(2600e3, 2600e3)

        #self.cell.shapes(self.get_layer("base_metal_gap_wo_grid", 0)).insert(difference_pattern)
        #self.cell.shapes(self.get_layer("ground_grid_avoidance", 0)).insert(protection_pattern)

        test_structure_region_x = 620
        test_structure_region_y = 2000
        resolution = self.layout.create_cell("ResolutionTestStructure_NB", TestStructure.LIBRARY_NAME)
        self.insert_cell(resolution, pya.DTrans(0, False, 
                                                test_structure_region_x, 
                                                test_structure_region_y - 300), 
                                                "res")
        self.insert_cell(resolution, pya.DTrans(1, False, 
                                                test_structure_region_x - 400, 
                                                test_structure_region_y - 155), 
                                                "res")

        """ self.insert_cell(Profilometer, pya.DTrans(0, False,
                                                  test_structure_region_x - 112.5,
                                                  test_structure_region_y - 450),
                                                  "pro")"""
        
        
        load_libraries(path=TestStructure.LIBRARY_PATH)
        AMPLogo = self.layout.create_cell("AMPlogo", TestStructure.LIBRARY_NAME)

        self.insert_cell(AMPLogo, pya.DCplxTrans(0.5, 0, False,
                                                  test_structure_region_x - 30, 
                                                  test_structure_region_y - 90), 
                                                  "logo")

        load_libraries(path=Element.LIBRARY_PATH)
        NISTlogo = self.layout.create_cell("NISTlogo", Element.LIBRARY_NAME)

        # measured from crap GDS logo file
        scaleFactor = 40 / 158.016
        self.insert_cell(NISTlogo, pya.DCplxTrans(scaleFactor, 0, False,
                                                  test_structure_region_x, 
                                                  test_structure_region_y + 80), 
                                                  "logo")

        produce_label(
            self.cell,
            label="R K Romani",
            location=pya.DPoint(test_structure_region_x - 320, test_structure_region_y - 150),
            origin=LabelOrigin.TOPLEFT,
            origin_offset=0,
            margin=10,
            layers=[self.face()["base_metal_gap_wo_grid"]],
            layer_protection=self.face()["ground_grid_avoidance"],
            size=50,
        )

        produce_label(
            self.cell,
            label="Hook Junctions",
            location=pya.DPoint(1000, 6500),
            origin=LabelOrigin.TOPLEFT,
            origin_offset=0,
            margin=10,
            layers=[self.face()["base_metal_gap_wo_grid"]],
            layer_protection=self.face()["ground_grid_avoidance"],
            size=100,
        )

        
        produce_label(
            self.cell,
            label=self.label_text,
            location=pya.DPoint(3000, 6500),
            origin=LabelOrigin.TOPLEFT,
            origin_offset=0,
            margin=10,
            layers=[self.face()["base_metal_gap_wo_grid"]],
            layer_protection=self.face()["ground_grid_avoidance"],
            size=100,
        )




        #pad_width = 200
        #pad_height = 200
        pad_width = 14
        pad_height = 6
        taper_width = 10
        lead_offset = 2
        hook_overshoot = 3
        bridge_lengths = np.asarray([0.1, 0.25, 0.5, 1, 1.5, 2, 2.5, 3, 4])
        hook_widths = np.asarray([0.1, 0.196, 0.3, 0.5])


        chip_center_x = 7500/2
        chip_center_y = 7500/2
        n_junction_x_group = 5
        n_junction_x = n_junction_x_group * len(hook_widths)
        n_junction_y = len(bridge_lengths)
        spacing_x = 250
        spacing_x_big = 1400
        spacing_y = 500
        start_x = chip_center_x - (n_junction_x_group - 1)/2 * spacing_x - (len(hook_widths)-1)/2 * spacing_x_big
        start_y = chip_center_y - n_junction_y/2 * spacing_y
        stop_x = chip_center_x + (n_junction_x)/2 * spacing_x
        stop_y = chip_center_y + (n_junction_y)/2 * spacing_y
        #pos_x = np.linspace(start_x, stop_x, n_junction_x)
        pos_y = np.linspace(start_y, stop_y, n_junction_y)

        pos_x = np.array([
                          start_x + i*spacing_x + j*spacing_x_big 
                          for i in range(n_junction_x_group) 
                          for j in range(len(hook_widths))
                          ])
        pos_x = np.sort(pos_x)

        i = 0
        while i < n_junction_x:
            j = 0
            while j < n_junction_y:
                coord = pya.DTrans(0, False, pos_x[i], pos_y[j])
                self.insert_cell(
                    RKRHook2, coord, f"JJ_{i}_{j}", 
                    wiring_pad_bool=self.wiring_pads,
                    pad_height=pad_height, pad_width=pad_width, 
                    lead_offset=lead_offset, taper_base=taper_width, hook_overshoot=hook_overshoot, 
                    bridge_length=bridge_lengths[j],
                    hook_width=hook_widths[int(i/5)]
                    #**element_params[i],
                )

                if i % (n_junction_x_group) == 0:
                    produce_label(
                        self.cell,
                        label=str(bridge_lengths[j]) + " x " + str(hook_widths[int(i/5)]),
                        location=pya.DPoint(pos_x[i], pos_y[j] - spacing_y/2),
                        origin=LabelOrigin.TOPLEFT,
                        origin_offset=0,
                        margin=10,
                        layers=[self.face()["base_metal_gap_wo_grid"]],
                        layer_protection=self.face()["ground_grid_avoidance"],
                        size=50,
                    )

                j += 1
            i += 1


