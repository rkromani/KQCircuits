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
from kqcircuits.elements.double_res_2 import DoubleRes2
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
    name_chip="DR1",
    frames_marker_dist=[250, 250],
    name_mask="tt",
    name_copy="",
    marker_types=[""] * 8,
)

# @add_parameters_from(Junction, "junction_type")
# @add_parameters_from(Junction, "junction_type")


class DoubleRes2Chip(Chip):
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



        feedline_offset = 500
        self.refpoints["feedline_middle_left"] = pya.DPoint(self.refpoints["E1_port"].x + feedline_offset, (self.refpoints["E1_port"].y + self.refpoints["E2_port"].y)/2)
        self.refpoints["feedline_middle_right"] = pya.DPoint(self.refpoints["W1_port"].x - feedline_offset, (self.refpoints["E1_port"].y + self.refpoints["E2_port"].y)/2)
        self.refpoints["feedline_bottom_left"] = pya.DPoint(self.refpoints["E2_port"].x + feedline_offset, self.refpoints["E2_port"].y)
        self.refpoints["feedline_top_right"] = pya.DPoint(self.refpoints["W1_port"].x - feedline_offset, self.refpoints["E1_port"].y)
        self.insert_cell(
                    WaveguideComposite, 
                    nodes=[
                        Node(self.refpoints["E1_port"]),
                        Node(self.refpoints["feedline_top_right"]),
                        Node(self.refpoints["feedline_middle_right"]),
                        Node(self.refpoints["feedline_middle_left"]),
                        Node(self.refpoints["feedline_bottom_left"]),
                        Node(self.refpoints["W2_port"])
                    ],
                )
        
        center_offset_x = 1500
        center_x = (self.refpoints["E1_port"].x + self.refpoints["W1_port"].x)/2
        res_locs = [pya.DPoint(center_x - center_offset_x*1.5, self.refpoints["E1_port"].y),
                    pya.DPoint(center_x - center_offset_x*0.5, self.refpoints["E1_port"].y),
                    pya.DPoint(center_x + center_offset_x*0.5, self.refpoints["E1_port"].y),
                    pya.DPoint(center_x + center_offset_x*1, self.refpoints["feedline_middle_right"].y),
                    pya.DPoint(center_x - center_offset_x*0, self.refpoints["feedline_middle_right"].y),
                    pya.DPoint(center_x - center_offset_x*1, self.refpoints["feedline_middle_right"].y),
                    pya.DPoint(center_x + center_offset_x*0.5, self.refpoints["feedline_middle_right"].y),
                    pya.DPoint(center_x - center_offset_x*0.5, self.refpoints["feedline_middle_right"].y),
                    pya.DPoint(center_x + center_offset_x*1, self.refpoints["E2_port"].y),
                    pya.DPoint(center_x - center_offset_x*0, self.refpoints["E2_port"].y),
                    pya.DPoint(center_x - center_offset_x*1, self.refpoints["E2_port"].y),
                    ]
        flip_bools = [False, False, False,  True, True, True, False, False, True, True, True]
        bias_ports = ['E2', 'E2', 'E2', 'E2', 'E2', 'E2', 'W1', 'W1', 'W1', 'W1', 'W1',]
        i = 0
        while i < len(res_locs):
            self.insert_cell(DoubleRes2, pya.DTrans(0, flip_bools[i], res_locs[i].x, res_locs[i].y), f"DR_{i}")
            
            if flip_bools[i]:
                rot = 0
                y_space = self.a/2
            else:
                rot = 2
                y_space = -self.a/2

            self.insert_cell(
                WaveguideCoplanarSplitter,
                pya.DTrans(rot, False, self.refpoints[f"DR_{i}_bias_port"].x, self.refpoints[f"DR_{i}_bias_port"].y + y_space),
                f"T{i}",

                **t_cross_parameters(
                    a=self.a,
                    b=self.b,
                    a2=self.a,
                    b2=self.b,
                    length_extra=5,
                    length_extra_side=5
                )
            )
            i += 1

        top_res_center_y = (self.refpoints["E1_port"].y + self.refpoints["feedline_middle_right"].y)/2
        bottom_res_center_y = (self.refpoints["E2_port"].y + self.refpoints["feedline_middle_right"].y)/2

        self.insert_cell(
                    WaveguideComposite, 
                    nodes=[Node(self.refpoints[f"T3_port_right"]),
                           Node(pya.DPoint(self.refpoints[f"T3_port_right"].x + self.b, self.refpoints[f"T3_port_right"].y))],
                    a = 0,
                    b = self.a/2 + self.b
                )

        
        bias_line_offset_x = 200
        top_dr_order = [3, 2, 4, 1, 5, 0]

        i = 0
        while i < len(top_dr_order) - 1:

            if flip_bools[top_dr_order[i]]:
                left = "left"
            else:
                left = "right"
            if flip_bools[top_dr_order[i + 1]]:
                right = "right"
            else:
                right = "left"

            self.insert_cell(
                    WaveguideComposite, 
                    nodes=[Node(self.refpoints[f"T{top_dr_order[i]}_port_{left}"]), 
                           Node(pya.DPoint(self.refpoints[f"T{top_dr_order[i]}_port_{left}"].x - bias_line_offset_x, self.refpoints[f"T{top_dr_order[i]}_port_{left}"].y)), 
                           Node(pya.DPoint(self.refpoints[f"T{top_dr_order[i]}_port_{left}"].x - bias_line_offset_x, top_res_center_y)), 
                           Node(pya.DPoint(self.refpoints[f"T{top_dr_order[i + 1]}_port_{right}"].x + bias_line_offset_x, top_res_center_y)), 
                           Node(pya.DPoint(self.refpoints[f"T{top_dr_order[i + 1]}_port_{right}"].x + bias_line_offset_x, self.refpoints[f"T{top_dr_order[i + 1]}_port_{right}"].y)), 
                           Node(self.refpoints[f"T{top_dr_order[i + 1]}_port_{right}"]), 
                    ], 
                    r=20
                )
            i += 1

        bias_top_middle_x = (self.refpoints[f"T{top_dr_order[-1]}_port_left"].x + self.refpoints[f"E2_port"].x)/2
        self.insert_cell(
                    WaveguideComposite, 
                    nodes=[Node(self.refpoints[f"T{top_dr_order[-1]}_port_right"]),
                           Node(pya.DPoint(bias_top_middle_x, self.refpoints[f"T{top_dr_order[-1]}_port_right"].y)),
                           Node(pya.DPoint(bias_top_middle_x, self.refpoints[f"E2_port"].y)),
                           Node(self.refpoints[f"E2_port"]),
                            ],
                    r=20
                )

        
        

        