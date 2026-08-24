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
from kqcircuits.elements.pomeroy_double_res import PomeroyDoubleRes
from kqcircuits.elements.alignment_pomeroy_local import AlignmentPomeroyLocal
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
    name_date_x_offset=1200,
)
@add_parameters_from(
    Chip,
    face_boxes=[None, pya.DBox(pya.DPoint(0, 0), pya.DPoint(5200, 5200))],
    frames_dice_width=[50, 50],
    name_brand="RKR",
    name_chip="PDR",
    frames_marker_dist=[250, 250],
    name_mask="tt",
    name_copy="",
    marker_types=[""] * 8,
)

# @add_parameters_from(Junction, "junction_type")
# @add_parameters_from(Junction, "junction_type")


class PomeroyDoubleResChip(Chip):
    # CPW parameters for resonator and capacitor
    a = Param(pdt.TypeDouble, "CPW center conductor width", 10, unit="μm")
    b = Param(pdt.TypeDouble, "CPW gap width", 5.85, unit="μm")

    a_launcher = Param(pdt.TypeDouble, "Pad CPW trace center", 200, unit="μm")
    b_launcher = Param(pdt.TypeDouble, "Pad CPW trace gap", 153, unit="μm")
    launcher_width = Param(pdt.TypeDouble, "Pad extent", 250, unit="μm")
    taper_length = Param(pdt.TypeDouble, "Tapering length", 200, unit="μm")
    launcher_frame_gap = Param(pdt.TypeDouble, "Gap at chip frame", 100, unit="μm")
    launcher_indent = Param(pdt.TypeDouble, "Chip edge to pad port", 975, unit="μm")
    launcher_y_position = Param(pdt.TypeDouble, "Launcher vertical position", 2750*2, unit="μm")

    cap_distance = Param(pdt.TypeDouble, "Capacitor distance from bottom of resonator ground gap", 50, unit="μm")
    launcher_turn_x = Param(pdt.TypeDouble, "Distance from tip of bias launcher to turn", 300, unit="μm")
    bias_rail_y = Param(pdt.TypeDouble, "Y position of bias rail", 300, unit="μm")

    alignment_pomeroy_local_pos = Param(pdt.TypeDouble, "Distance of alignment mark from center of chip", 3250, unit="μm")
    

    # parameters to pass to junctions
    # small junctions
    #Q_finger_width = Param(pdt.TypeDouble, "Width of the finger.", 0.136, unit="μm")
    #Q_bridge_gap = Param(pdt.TypeDouble, "Gap between finger and hook.", 0.15, unit="μm")
    #Q_hook_thickness = Param(pdt.TypeDouble, "Thickness of hook on catch.", 0.100, unit="μm")

    # SQUID junctions
    #S_finger_width = Param(pdt.TypeDouble, "Width of the finger.", 1.496, unit="μm")
    #S_bridge_gap = Param(pdt.TypeDouble, "Gap between finger and hook.", 0.15, unit="μm")
    #S_taper = Param(pdt.TypeDouble, "Width of fixed finger.", 2.0, unit="μm")

    def produce_four_launchers(self, a_launcher, b_launcher, launcher_width, taper_length, launcher_frame_gap, 
                              launcher_indent, pad_pitch, launcher_assignments=None,  enabled=None, chip_box=None,
                            face_id=0):
        
        launcher_cell = self.add_element(Launcher, s=launcher_width, l=taper_length,
                                             a_launcher=a_launcher, b_launcher=b_launcher,
                                             launcher_frame_gap=launcher_frame_gap, face_ids=[self.face_ids[face_id]])

        pads_per_side = [0,2,0,2]

        dirs = (90, 0, -90, 180)
        trans = (pya.DTrans(3, 0, self.box.p1.x, self.box.p2.y),
                 pya.DTrans(2, 0, self.box.p2.x, self.box.p2.y),
                 pya.DTrans(1, 0, self.box.p2.x, self.box.p1.y),
                 pya.DTrans(0, 0, self.box.p1.x, self.box.p1.y))
        _w = self.box.p2.x - self.box.p1.x
        _h = self.box.p2.y - self.box.p1.y
        sides = [_w, _h, _w, _h]

        return self._insert_launchers(dirs, enabled, launcher_assignments, None, launcher_cell, launcher_indent,
                                      launcher_width, pad_pitch, pads_per_side, sides, trans, face_id=0)

    
    def produce_ground_grid(self):
        # no ground grid on test junction chip
        pass

    def build(self):
        self.launchers = self.produce_four_launchers(self.a_launcher, self.b_launcher, self.launcher_width,
                                   self.taper_length, self.launcher_frame_gap, self.launcher_indent, self.launcher_y_position, launcher_assignments={1: "W1", 2: "W2", 3:"E2", 4:"E1"})
        

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



        self.insert_cell(AlignmentPomeroyLocal, pya.DTrans(0, False,
                                                  3750,
                                                  self.alignment_pomeroy_local_pos + 3750),
                                                  "alignment_local")
        self.insert_cell(AlignmentPomeroyLocal, pya.DTrans(0, False,
                                                  3750,
                                                  -self.alignment_pomeroy_local_pos + 3750),
                                                  "alignment_local")
        self.insert_cell(AlignmentPomeroyLocal, pya.DTrans(0, False,
                                                  self.alignment_pomeroy_local_pos + 3750,
                                                  3750),
                                                  "alignment_local")
        self.insert_cell(AlignmentPomeroyLocal, pya.DTrans(0, False,
                                                  -self.alignment_pomeroy_local_pos + 3750,
                                                  3750),
                                                  "alignment_local")




        DR_coords = []

        center_x = 7500/2
        center_y = 7500/2
        spacing = 1800
        n_res = 2

        res_params = [{"cap_width": 2, "cap_height": 2},
                      {"cap_width": 3, "cap_height": 3}, ]



        i = 0
        while i < n_res:
            if i < n_res/2:
                DR_coord = pya.DTrans(2, False, center_x - (i - (n_res-1)/2)*spacing, center_y)
            else:
                DR_coord = pya.DTrans(0, False, center_x - (i - (n_res-1)/2)*spacing, center_y)
            DR_coords.append(DR_coord)

            self.insert_cell(
                PomeroyDoubleRes, DR_coord, f"DR{i}", 
                feedline_cutout_bool=False,
                **res_params[i], 
            ) 

            offset_x = -300
            if i < n_res/2:
                offset_y = -400
            else:
                offset_y = 400
            produce_label(
                self.cell,
                label="cap_dim " + str(res_params[i]["cap_width"]) + " x " + str(res_params[i]["cap_height"]),
                location=pya.DPoint(center_x - (i - (n_res-1)/2)*spacing + offset_x, center_y + offset_y),
                origin=LabelOrigin.TOPLEFT,
                origin_offset=0,
                margin=10,
                layers=[self.face()["base_metal_gap_wo_grid"]],
                layer_protection=self.face()["ground_grid_avoidance"],
                size=50,
            )

            i += 1

        launcher_feed_middle = ((-self.refpoints["W2_port"].x + self.refpoints["DR0_feedline_a"].x)/2)
        self.refpoints["launcher_feed_middle_l1"] = pya.DPoint(self.refpoints["E1_port"].x - launcher_feed_middle, self.refpoints["E1_port"].y)
        self.refpoints["launcher_feed_middle_l2"] = pya.DPoint(self.refpoints["E1_port"].x - launcher_feed_middle, self.refpoints["DR0_feedline_b"].y)
        self.refpoints["launcher_feed_middle_r1"] = pya.DPoint(self.refpoints["W2_port"].x + launcher_feed_middle, self.refpoints["W2_port"].y)
        self.refpoints["launcher_feed_middle_r2"] = pya.DPoint(self.refpoints["W2_port"].x + launcher_feed_middle, self.refpoints[f"DR{n_res-1}_feedline_b"].y)
        left_ref_names = ["W2_port"]
        right_ref_names = []
        i = 0
        while i < n_res:
            if i < n_res/2:
                left_ref_names.append(f"DR{i}_feedline_b")
                right_ref_names.append(f"DR{i}_feedline_a")
            else:
                left_ref_names.append(f"DR{i}_feedline_a")
                right_ref_names.append(f"DR{i}_feedline_b")
            i += 1
        right_ref_names.append("E1_port")


        for i in range(len(left_ref_names)):
            if i == 0:
                self.insert_cell(
                    WaveguideComposite, 
                    nodes=[
                        Node(self.refpoints[left_ref_names[i]]),
                        Node(self.refpoints['launcher_feed_middle_r1']),
                        Node(self.refpoints['launcher_feed_middle_r2']),
                        Node(self.refpoints[right_ref_names[i]])
                    ],
                )
            elif i == len(left_ref_names) - 1:
                self.insert_cell(
                    WaveguideComposite, 
                    nodes=[
                        Node(self.refpoints[left_ref_names[i]]),
                        Node(self.refpoints['launcher_feed_middle_l2']),
                        Node(self.refpoints['launcher_feed_middle_l1']),
                        Node(self.refpoints[right_ref_names[i]])
                    ],
                )
            else:
                self.insert_cell(
                    WaveguideComposite, 
                    nodes=[
                        Node(self.refpoints[left_ref_names[i]]),
                        Node(self.refpoints[right_ref_names[i]])
                    ],
                )

        cap_to_skip = 5  # Example: skip capacitor for resonator 2
        i = 0
        while i < n_res:
            cap_center_x = self.refpoints[f"DR{i}_bias"].x
            
            if i < n_res/2:
                rot = 2
                cap_center_y = self.refpoints[f"DR{i}_bias"].y + self.cap_distance
            else:
                rot = 0
                cap_center_y = self.refpoints[f"DR{i}_bias"].y - self.cap_distance
            
            if i != cap_to_skip:
                self.insert_cell(
                    FingerCapacitorGroundV3, pya.DTrans(rot, False, cap_center_x, cap_center_y), f"CAP{i}",
                    a=self.a, b=self.b, finger_number=0, 
                )

                self.insert_cell(
                        WaveguideComposite, 
                        nodes=[
                            Node(self.refpoints[f"DR{i}_bias"]),
                            Node(self.refpoints[f"CAP{i}_top_port"])
                        ],
                    )
            
            i += 1


        self.insert_cell( WaveguideComposite, nodes=[
                    Node(self.refpoints[f"W1_port"]),
                    Node((self.refpoints[f"W1_port"].x - self.launcher_turn_x, self.refpoints[f"W1_port"].y)),
                    Node((self.refpoints[f"W1_port"].x - self.launcher_turn_x, 7500 - self.bias_rail_y)),
                    Node((self.refpoints[f"CAP0_bottom_port"].x, 7500 - self.bias_rail_y)),
                    Node(self.refpoints[f"CAP0_bottom_port"])],)
        
        self.insert_cell( WaveguideComposite, nodes=[
                    Node(self.refpoints[f"E2_port"]),
                    Node((self.refpoints[f"E2_port"].x + self.launcher_turn_x, self.refpoints[f"E2_port"].y)),
                    Node((self.refpoints[f"E2_port"].x + self.launcher_turn_x, self.bias_rail_y)),
                    Node((self.refpoints[f"CAP1_bottom_port"].x, self.bias_rail_y)),
                    Node(self.refpoints[f"CAP1_bottom_port"])],)
        


