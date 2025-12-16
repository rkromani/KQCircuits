# This code is part of KQCircuits
# Copyright (C) 2025 Roger Romani
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
 
from math import pi
from kqcircuits.pya_resolver import pya
from kqcircuits.elements.element import Element
from kqcircuits.chips.chip import Chip
from kqcircuits.elements.chip_frame import ChipFrame
from kqcircuits.util.parameters import Param, pdt, add_parameters_from, add_parameter
from kqcircuits.elements.launcher import Launcher
from kqcircuits.elements.waveguide_coplanar import WaveguideCoplanar
from kqcircuits.elements.waveguide_composite import WaveguideComposite, Node
from kqcircuits.elements.hanger_resonator import HangerResonator

from kqcircuits.qubits.double_pads import DoublePads
from kqcircuits.qubits.biased import BiasedGrounded
from kqcircuits.qubits.hanger_res_qubit import HangerResQubit
#from kqcircuits.qubits.double_pads_round import DoublePadsRound
#from kqcircuits.qubits.finger_pads_jj import FingerPadsJJ

@add_parameters_from(Element, b = 4.6, a = 10, margin=100)
@add_parameters_from(ChipFrame, box = pya.DBox(pya.DPoint(0, 0), pya.DPoint(7500, 7500)))
# no flip chip alignment markers
@add_parameters_from(ChipFrame, marker_types=['','','',''])
@add_parameters_from(Chip,
                     face_boxes=[None, pya.DBox(pya.DPoint(0, 0), pya.DPoint(7500, 7500))],
                     frames_dice_width=['50'], name_brand='NIST', name_chip='BIAS', name_copy='v3F')

class NISTRKRBias(Chip):
    # parameters accessible in PCell
    a_launcher = Param(pdt.TypeDouble, "Pad CPW trace center", 200, unit="μm")
    b_launcher = Param(pdt.TypeDouble, "Pad CPW trace gap", 153, unit="μm")
    launcher_width = Param(pdt.TypeDouble, "Pad extent", 250, unit="μm")
    taper_length = Param(pdt.TypeDouble, "Tapering length", 200, unit="μm")
    launcher_frame_gap = Param(pdt.TypeDouble, "Gap at chip frame", 100, unit="μm") 
    launcher_indent = Param(pdt.TypeDouble, "Chip edge to pad port", 700, unit="μm") 

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

    def _produce_readout_hangers(self, coupling_lengths):
        # alternate flipping up and down. Position on center not port a
        for i,clength in enumerate(coupling_lengths):
            name_prefix = "HR_U"
            x_len_total = self.refpoints[f"E2_port"].x - self.refpoints[f"W2_port"].x
            x_spacing = (x_len_total)/5
            trans = pya.DTrans(0, True, self.refpoints[f"E2_port"].x - x_spacing*(i + 1) - (clength + self.r)/2, self.refpoints[f"W2_port"].y)

            name = name_prefix + f"{int((i))}"
            rlength = clength + pi*self.r/2 + 100

            self.insert_cell(HangerResonator, trans, name, coupling_length=clength, ground_width=6,
                             head_length=0, res_b=self.b, res_a=self.a, resonator_length=rlength)



    def _produce_u_res(self, i, length, adjust):
        self.insert_cell(
                WaveguideComposite,
                nodes = [
                    Node(self.refpoints[f"HR_U{i}_port_resonator_b"]), 
                    Node((self.refpoints[f"HR_U{i}_port_resonator_b"].x, self.refpoints[f"Q_U{i}_port_cplr_corner"].y - 1100), 
                         length_before=(length - adjust)),
                    Node((self.refpoints[f"HR_U{i}_port_resonator_b"].x, self.refpoints[f"Q_U{i}_port_cplr_corner"].y - 950)),
                    Node((self.refpoints[f"Q_U{i}_port_cplr_corner"].x + 200, self.refpoints[f"Q_U{i}_port_cplr_corner"].y - 950)),
                    Node((self.refpoints[f"Q_U{i}_port_cplr_corner"].x, self.refpoints[f"Q_U{i}_port_cplr_corner"].y - 950)),
                    #Node(self.refpoints[f"Q_U{i}_port_cplr"].x, self.refpoints[f"Q_U{i}_port_cplr_corner"].y), 
                    Node(self.refpoints[f"Q_U{i}_port_cplr"])
                ], 
            )

    def build(self):
        self.launchers = self.produce_four_launchers(self.launcher_width, self.b_launcher, self.launcher_width, 
                                   self.taper_length, self.launcher_frame_gap, self.launcher_indent, 5588, launcher_assignments={1: "W1", 2: "W2", 3:"E2", 4:"E1"})

        res_lengths2 = [4120.4, 4190.2, 4042.4, 4107.9]
        
        coupling_lengths = [260, 257, 254, 251]
        
        hanger_coupling_lengths = []
        for i in range(2):
                hanger_coupling_lengths.append(coupling_lengths[i])

        self.hangers = self._produce_readout_hangers(hanger_coupling_lengths)

        # top row positioning
        rot_arr = [3,3,0,0]
        U_coords = [pya.DTrans(rot_arr[i], False, 1700 + i * 1300, 3750) for i in range(4)]
        # bottom row positioning
        D_coords = [pya.DTrans(1, False, 1800 + i * 1300, 1800) for i in range(4)]


        
        # Qubit U0: 3um IDC: done
        self.insert_cell(
            BiasedGrounded, U_coords[0], f"Q_U0", 
            bias_width=self.a,
            #ground_gap=['800', '510'], 
            #ground_gap_r=20.0, coupler_extent=['300', '18'], coupler_r=20.0, coupler_offset=14.0, 
            #finger_width=3, finger_gap=3, finger_gap_end=3, finger_length=55, finger_number=34,
            #corner_r=5, with_junction=True, #with_tapers=True, 
            #island1_taper_width=20, island1_taper_junction_width=20, 
            #island2_taper_width=20, island2_taper_junction_width=20, 
        )

        # Qubit U1: 150 rounded. done
        self.insert_cell(
            BiasedGrounded, U_coords[1], f"Q_U1", ground_gap=['1500', '900'], 
            bias_width=self.a,
            #ground_gap_r=74.9, coupler_extent=['154', '20'], coupler_r=0.0, coupler_offset=50.0, 
            #island1_extent=['1120', '150'], island1_r=74.9, island2_extent=['1120', '150'], 
            #island2_r=74.9, drive_position=['-450', '0'], island_island_gap=150.0,
            #junction_total_length=20.0, junction_type='Sim', with_squid=False,
            #junction_width=0.02, junction_parameters='{"junction_type": "Sim", "junction_width": 0.02, "junction_total_length": 20.0}', 
            #island1_taper_width=100, island1_taper_junction_width=100, 
            #island2_taper_width=100, island2_taper_junction_width=100, 
        )

        self.insert_cell(
            HangerResQubit, U_coords[2], f"Q_U2",
            r_inductor_coupling_ground_width=10, 
            ground_gap=[800, 5588 - 20 - 19.3],
            r_inductor_coupling_length=500,
            r_inductor_length=13000

        )

        self.insert_cell(
            HangerResQubit, U_coords[3], f"Q_U3",
            r_inductor_coupling_ground_width=10, 
            ground_gap=[800, 5588 - 20 - 19.3],
            r_inductor_coupling_length=300,
            r_inductor_length=15000
        )

        
        res_final = [res_lengths2[i] for i in range(2)]

        rad_adj = 4 * self.r * (2 - pi / 2)

        # 20 um 735, rounded 845, idc 515

        res_params= {
            'U0': {'len': res_final[0], 'adj': 2305 - 150 + coupling_lengths[0] - rad_adj},
            'U1': {'len': res_final[1], 'adj': 2500 - 150 + coupling_lengths[1] - rad_adj},
            #'U2': {'len': res_final[2], 'adj': 2305 - 150 + coupling_lengths[2] - rad_adj},
            #'U3': {'len': res_final[3], 'adj': 2405 - 150 + coupling_lengths[3] - rad_adj},
        }

        #for key in res_params:
        #    if key[0] == 'U':
        #            self._produce_u_res(key[1], res_params[key]['len'], res_params[key]['adj'])
        #    elif key[0] == 'D':
        #        self._produce_d_res(key[1], res_params[key]['len'], res_params[key]['adj'])
        #    else:
        #        pass

        self._produce_u_res(0, res_params['U0']['len'], res_params['U0']['adj'])
        self._produce_u_res(1, res_params['U1']['len'], res_params['U1']['adj'])



        left_ref_names = ["W2_port", 'Q_U3_port_feed_a', 'Q_U2_port_feed_a', "HR_U1_port_a", "HR_U0_port_a"]
        right_ref_names = [ "Q_U3_port_feed_b", "Q_U2_port_feed_b", "HR_U1_port_b", "HR_U0_port_b", "E2_port"]
        #for i in range(2):
        #    left_ref_names.append(f"HR_U{i}_port_b")
        #    right_ref_names.append(f"HR_U{i}_port_a")
        #right_ref_names.append("E2_port")

        for i in range(len(left_ref_names)):
            self.insert_cell(
                WaveguideCoplanar, 
                path=pya.DPath([
                    self.refpoints[left_ref_names[i]],
                    self.refpoints[right_ref_names[i]]
                ], 0),
            )

        loop_width = 300
        loop_offset = 2000
        #flux bias line 
        self.insert_cell(
                WaveguideComposite,
                nodes = [
                    Node(self.refpoints["W1_port"]), 
                    Node((self.refpoints[f"W1_port"].x - 200, self.refpoints[f"W1_port"].y)),
                    Node((self.refpoints[f"W1_port"].x - 200, self.refpoints[f"W1_port"].y + 200)),
                    Node((self.refpoints[f"W1_port"].x - loop_offset, self.refpoints[f"W1_port"].y + 200)),
                    Node((self.refpoints[f"W1_port"].x - loop_offset, self.refpoints[f"W1_port"].y - 5000)),
                    Node((self.refpoints[f"W1_port"].x - loop_offset + loop_width, self.refpoints[f"W1_port"].y - 5000)),
                    Node((self.refpoints[f"W1_port"].x - loop_offset + loop_width, self.refpoints[f"W1_port"].y - 1000)),
                ], 
            )

        #qubit bias line 
        self.insert_cell(
                WaveguideComposite,
                nodes = [
                    Node(self.refpoints["E1_port"]), 
                    Node((self.refpoints[f"Q_U0_port_bias"].x, self.refpoints[f"E1_port"].y)),
                    Node((self.refpoints[f"Q_U0_port_bias"])),
                    
                ], 
            )

        #qubit bias line 
        self.insert_cell(
                WaveguideComposite,
                nodes = [
                    Node(self.refpoints["E1_port"]), 
                    Node((self.refpoints[f"Q_U1_port_bias"].x, self.refpoints[f"E1_port"].y)),
                    Node((self.refpoints[f"Q_U1_port_bias"])),
                    
                ], 
            )
