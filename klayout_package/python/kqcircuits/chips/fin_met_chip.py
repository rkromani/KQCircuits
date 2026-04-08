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
    name_chip="FM1",
    frames_marker_dist=[250, 250],
    name_mask="tt",
    name_copy="",
    marker_types=[""] * 8,
)

# @add_parameters_from(Junction, "junction_type")
# @add_parameters_from(Junction, "junction_type")


class FinMetChip(Chip):
    # CPW parameters for resonator and capacitor
    a = Param(pdt.TypeDouble, "CPW center conductor width", 10, unit="μm")
    b = Param(pdt.TypeDouble, "CPW gap width", 5.85, unit="μm")

    a_launcher = Param(pdt.TypeDouble, "Pad CPW trace center", 200, unit="μm")
    b_launcher = Param(pdt.TypeDouble, "Pad CPW trace gap", 153, unit="μm")
    launcher_width = Param(pdt.TypeDouble, "Pad extent", 250, unit="μm")
    taper_length = Param(pdt.TypeDouble, "Tapering length", 200, unit="μm")
    launcher_frame_gap = Param(pdt.TypeDouble, "Gap at chip frame", 100, unit="μm")
    launcher_indent = Param(pdt.TypeDouble, "Chip edge to pad port", 975, unit="μm")

    cap_x_distance = Param(pdt.TypeDouble, "Capacitor horizontal distance from inductor", 400, unit="μm")
    cap_y_distance = Param(pdt.TypeDouble, "Capacitor vertical distance from inductor", 1000, unit="μm")
    launcher_turn_x = Param(pdt.TypeDouble, "Distance from tip of bias launcher to turn", 300, unit="μm")
    bias_rail_y = Param(pdt.TypeDouble, "Y position of bias rail", 300, unit="μm")
    

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

        self.insert_cell(Profilometer, pya.DTrans(0, False,
                                                  test_structure_region_x - 112.5,
                                                  test_structure_region_y - 450),
                                                  "pro")
        
        
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



        self.insert_cell(
            Launcher, pya.DTrans(2, False, self.launcher_indent, 7500/2 + 5), f"W1",
            a=self.a, b=self.b,
        )
        self.insert_cell(
            Launcher, pya.DTrans(0, False, 7500-self.launcher_indent, 7500/2 + 5), f"E1",
            a=self.a, b=self.b,
        )



        BR_coords = []

        center_y = 7500/2 + 5
        start_x = 1437.22 + 0.35/2 - 25.095
        double_spacing = 1396.036
        single_spacing = 1396.036 - 912.536
        n_elements = 8        
        
        base_length = 3950
        spacing = 0.025
        element_params = [{'feedline_length': 10, 'res_length': base_length*(1-3*spacing), 'coupler_width': 27}, {'feedline_length': 10, 'res_length': base_length*(1-2*spacing), 'coupler_width': 27}, 
                          {'feedline_length': 10, 'res_length': base_length*(1-1*spacing), 'coupler_width': 27}, {'feedline_length': 10, 'res_length': base_length*1, 'coupler_width': 27},
                          {'feedline_length': 10, 'res_length': base_length*(1+1*spacing), 'coupler_width': 48}, {'feedline_length': 10, 'res_length': base_length*(1+2*spacing), 'coupler_width': 48}, 
                          {'feedline_length': 10, 'res_length': base_length*(1+3*spacing), 'coupler_width': 48}, {'feedline_length': 10, 'res_length': base_length*(1+4*spacing), 'coupler_width': 48},]
        i = 0
        while i < n_elements:
            if i % 2 == 0:
                distance_from_start = double_spacing * i/2
                flip = 0
                mirror = True
            else:
                distance_from_start = double_spacing * (i-1)/2 + single_spacing
                flip = 0
                mirror = False
            coord = pya.DTrans(flip, mirror, start_x + distance_from_start, center_y)

            self.insert_cell(
            FinMet, coord, f"FM{i}", 
            feedline_cutout_bool=False,
            **element_params[i],
            ) 

            
            """produce_label(
                self.cell,
                label="l_coupling_length " + str(res_params[i]["l_coupling_length"]),
                location=pya.DPoint(center_x - (i - (n_res-1)/2)*spacing + offset_x, center_y + offset_y),
                origin=LabelOrigin.TOPLEFT,
                origin_offset=0,
                margin=10,
                layers=[self.face()["base_metal_gap_wo_grid"]],
                layer_protection=self.face()["ground_grid_avoidance"],
                size=50,
            )
            produce_label(
                self.cell,
                label="l_tot_length " + str(res_params[i]["l_tot_length"]),
                location=pya.DPoint(center_x - (i - (n_res-1)/2)*spacing + offset_x, center_y + offset_y + 100),
                origin=LabelOrigin.TOPLEFT,
                origin_offset=0,
                margin=10,
                layers=[self.face()["base_metal_gap_wo_grid"]],
                layer_protection=self.face()["ground_grid_avoidance"],
                size=50,
            )"""

            i += 1

        launcher_feed_middle = ((-self.refpoints["W1_port"].x + self.refpoints["E1_port"].x)/2)
        self.refpoints["launcher_feed_middle_l1"] = pya.DPoint(self.refpoints["E1_port"].x - launcher_feed_middle, self.refpoints["E1_port"].y)
        self.refpoints["launcher_feed_middle_l2"] = pya.DPoint(self.refpoints["E1_port"].x - launcher_feed_middle, self.refpoints["FM0_feedline_b"].y)
        self.refpoints["launcher_feed_middle_r1"] = pya.DPoint(self.refpoints["W1_port"].x + launcher_feed_middle, self.refpoints["W1_port"].y)
        self.refpoints["launcher_feed_middle_r2"] = pya.DPoint(self.refpoints["W1_port"].x + launcher_feed_middle, self.refpoints[f"FM{n_elements-1}_feedline_b"].y)
        left_ref_names = ["W1_port"]
        right_ref_names = []
        i = 0
        while i < n_elements:
            left_ref_names.append(f"FM{i}_feedline_a")
            right_ref_names.append(f"FM{i}_feedline_b")
            i += 1
        right_ref_names.append("E1_port")


        for i in range(len(left_ref_names)):
            self.insert_cell(
                WaveguideComposite, 
                nodes=[
                    Node(self.refpoints[left_ref_names[i]]),
                    #Node(self.refpoints['launcher_feed_middle_r1']),
                    #Node(self.refpoints['launcher_feed_middle_r2']),
                    Node(self.refpoints[right_ref_names[i]])
                ],
            )
            