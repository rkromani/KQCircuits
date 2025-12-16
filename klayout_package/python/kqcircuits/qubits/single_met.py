# This code is part of KQCircuits
# Copyright (C) 2022 IQM Finland Oy
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


import math

from kqcircuits.elements.element import Element
from kqcircuits.junctions.squid import Squid
from kqcircuits.junctions.manhattan import Manhattan
from kqcircuits.junctions.manhattan_single_junction import ManhattanSingleJunction
from kqcircuits.junctions.overlap_junction2 import Overlap2
from kqcircuits.util.parameters import Param, pdt, add_parameters_from
from kqcircuits.qubits.qubit import Qubit
from kqcircuits.pya_resolver import pya
from kqcircuits.util.refpoints import WaveguideToSimPort, JunctionSimPort


#@add_parameters_from(Squid, junction_type="Overlap2")
#@add_parameters_from(Manhattan)
#@add_parameters_from(ManhattanSingleJunction)
class SingleMET(Qubit):
    """
    Represents a floating MET inside a ground plane coupled to a drive line.
    """

    ground_gap_met = Param(pdt.TypeDouble, "Width, height of the ground gap around the MET(µm, µm)", 0.5)
    ground_gap_coupler = Param(pdt.TypeDouble, "Coupler gap to ground (µm)", 10)

    met_width = Param(pdt.TypeDouble, "MET width (µm)", 1.25)
    met_height = Param(pdt.TypeDouble, "MET height (µm)", 1.25)
    met_coupler_width = Param(pdt.TypeDouble, "MET to coupler width (µm)", 10)
    met_coupler_height = Param(pdt.TypeDouble, "MET to coupler height (µm)", 50)

    coupler_gap = Param(pdt.TypeDouble, "MET to coupler gap (µm)", 1)
    coupler_width = Param(pdt.TypeDouble, "Coupler width (µm)", 10)
    coupler_waveguide_length = Param(pdt.TypeDouble, "Coupler waveguide length (µm)", 20)

    def build(self):
        # Qubit base
        ground_gap_points_met = [
            pya.DPoint(float(self.ground_gap_met +  self.met_width) / 2, float(self.met_height) / 2 - float(self.ground_gap_met)),
            pya.DPoint(float(self.ground_gap_met +  self.met_width) / 2, -float(self.ground_gap_met + self.met_height) / 2),
            pya.DPoint(-float(self.ground_gap_met +  self.met_width) / 2, -float(self.ground_gap_met + self.met_height) / 2),
            pya.DPoint(-float(self.ground_gap_met +  self.met_width) / 2, float(self.met_height) / 2 - float(self.ground_gap_met)),
            pya.DPoint(-float(self.met_coupler_width/2 + self.coupler_gap + self.coupler_width + self.ground_gap_coupler), float(self.met_height) / 2 - float(self.ground_gap_met)),
            pya.DPoint(-float(self.met_coupler_width/2 + self.coupler_gap + self.coupler_width + self.ground_gap_coupler), float(self.met_height) / 2 + float(self.met_coupler_height + self.coupler_gap + self.coupler_width + self.ground_gap_coupler)),
            pya.DPoint(-float(self.a/2 + self.b), float(self.met_height) / 2 + float(self.met_coupler_height + self.coupler_gap + self.coupler_width + self.ground_gap_coupler)),
            pya.DPoint(-float(self.a/2 + self.b), float(self.met_height) / 2 + float(self.met_coupler_height + self.coupler_gap + self.coupler_width + self.ground_gap_coupler + self.coupler_waveguide_length)),
            pya.DPoint(float(self.a/2 + self.b), float(self.met_height) / 2 + float(self.met_coupler_height + self.coupler_gap + self.coupler_width + self.ground_gap_coupler + self.coupler_waveguide_length)),
            pya.DPoint(float(self.a/2 + self.b), float(self.met_height) / 2 + float(self.met_coupler_height + self.coupler_gap + self.coupler_width + self.ground_gap_coupler)),
            pya.DPoint(float(self.met_coupler_width/2 + self.coupler_gap + self.coupler_width + self.ground_gap_coupler), float(self.met_height) / 2 + float(self.met_coupler_height + self.coupler_gap + self.coupler_width + self.ground_gap_coupler)),
            pya.DPoint(float(self.met_coupler_width/2 + self.coupler_gap + self.coupler_width + self.ground_gap_coupler), float(self.met_height) / 2 - float(self.ground_gap_met)),
        ]
        ground_gap_polygon = pya.DPolygon(ground_gap_points_met)
        ground_gap_region = pya.Region(ground_gap_polygon.to_itype(self.layout.dbu))
        #ground_gap_region.round_corners(
        #    self.ground_gap_r / self.layout.dbu, self.ground_gap_r / self.layout.dbu, self.n
        #)

        met_polygon_points = [
            pya.DPoint(float(self.met_width) / 2, float(self.met_height) / 2),
            pya.DPoint(float(self.met_width) / 2, -float(self.met_height) / 2),
            pya.DPoint(-float(self.met_width) / 2, -float(self.met_height) / 2),
            pya.DPoint(-float(self.met_width) / 2, float(self.met_height) / 2),
        ]
        met_polygon = pya.DPolygon(met_polygon_points)
        met_region = pya.Region(met_polygon.to_itype(self.layout.dbu))
        met_coupler_polygon_points = [
            pya.DPoint(float(self.met_coupler_width) / 2, float(self.met_height) / 2),
            pya.DPoint(float(self.met_coupler_width) / 2, float(self.met_height) / 2 + float(self.met_coupler_height)),
            pya.DPoint(-float(self.met_coupler_width) / 2, float(self.met_height) / 2 + float(self.met_coupler_height)),
            pya.DPoint(-float(self.met_coupler_width) / 2, float(self.met_height) / 2),
        ]
        met_coupler_polygon = pya.DPolygon(met_coupler_polygon_points)
        met_coupler_region = pya.Region(met_coupler_polygon.to_itype(self.layout.dbu))

        coupler_polygon_points = [
            pya.DPoint(float(self.met_coupler_width) / 2 + float(self.coupler_gap), float(self.met_height) / 2 + float(self.met_coupler_height + self.coupler_gap)),
            pya.DPoint(float(self.met_coupler_width) / 2 + float(self.coupler_gap), float(self.met_height) / 2),
            pya.DPoint(float(self.met_coupler_width) / 2 + float(self.coupler_gap + self.coupler_width), float(self.met_height) / 2),
            pya.DPoint(float(self.met_coupler_width) / 2 + float(self.coupler_gap + self.coupler_width), float(self.met_height) / 2 + float(self.met_coupler_height + self.coupler_gap + self.coupler_width)),
            pya.DPoint(-float(self.met_coupler_width) / 2 - float(self.coupler_gap + self.coupler_width), float(self.met_height) / 2 + float(self.met_coupler_height + self.coupler_gap + self.coupler_width)),
            pya.DPoint(-float(self.met_coupler_width) / 2 - float(self.coupler_gap + self.coupler_width), float(self.met_height) / 2),
            pya.DPoint(-float(self.met_coupler_width) / 2 - float(self.coupler_gap), float(self.met_height) / 2),
            pya.DPoint(-float(self.met_coupler_width) / 2 - float(self.coupler_gap), float(self.met_height) / 2 + float(self.met_coupler_height + self.coupler_gap)),
        ]
        coupler_polygon = pya.DPolygon(coupler_polygon_points)
        coupler_region = pya.Region(coupler_polygon.to_itype(self.layout.dbu))

        coupler_waveguide_polygon_points = [
            pya.DPoint(float(self.a) / 2, float(self.met_height) / 2 + float(self.met_coupler_height + self.coupler_gap + self.coupler_width)),
            pya.DPoint(float(self.a) / 2, float(self.met_height) / 2 + float(self.met_coupler_height + self.coupler_gap + self.coupler_width + self.coupler_waveguide_length)),
            pya.DPoint(-float(self.a) / 2, float(self.met_height) / 2 + float(self.met_coupler_height + self.coupler_gap + self.coupler_width + self.coupler_waveguide_length)),
            pya.DPoint(-float(self.a) / 2, float(self.met_height) / 2 + float(self.met_coupler_height + self.coupler_gap + self.coupler_width)),
        ]
        coupler_waveguide_polygon = pya.DPolygon(coupler_waveguide_polygon_points)
        coupler_waveguide_region = pya.Region(coupler_waveguide_polygon.to_itype(self.layout.dbu))

        self.cell.shapes(self.get_layer("base_metal_gap_wo_grid")).insert(
            ground_gap_region - met_region - met_coupler_region - coupler_region - coupler_waveguide_region
        )

        self.cell.shapes(self.get_layer("SIS_shadow")).insert(
            met_region
        )

        self.cell.shapes(self.get_layer("SIS_junction_2")).insert(
            met_region
        )



        # Coupler port
        self.add_port(
            "cplr",
            pya.DPoint(0, float(self.met_height) / 2 + float(self.met_coupler_height) + float(self.coupler_gap) + float(self.coupler_width) + float(self.coupler_waveguide_length)),
            direction=pya.DVector(pya.DPoint(0, 1)),
        )
        
    def _build_coupler(self, first_island_right_edge):
        coupler_right_edge = first_island_right_edge + self.coupler_offset + float(self.coupler_extent[0])
        coupler_polygon = pya.DPolygon(
            [
                pya.DPoint(coupler_right_edge, -float(self.coupler_extent[1]) / 2),
                pya.DPoint(first_island_right_edge + self.coupler_offset, -float(self.coupler_extent[1]) / 2),
                pya.DPoint(first_island_right_edge + self.coupler_offset, float(self.coupler_extent[1]) / 2),
                pya.DPoint(coupler_right_edge, float(self.coupler_extent[1]) / 2),
            ]
        )
        coupler_region = pya.Region(coupler_polygon.to_itype(self.layout.dbu))
        coupler_region.round_corners(self.coupler_r / self.layout.dbu, self.coupler_r / self.layout.dbu, self.n)
        coupler_path_polygon = pya.DPolygon(
            [
                pya.DPoint((float(self.ground_gap[0]) / 2), -self.coupler_a / 2),
                pya.DPoint((float(self.ground_gap[0]) / 2), self.coupler_a / 2),
                pya.DPoint(coupler_right_edge, self.coupler_a / 2),
                pya.DPoint(coupler_right_edge, -self.coupler_a / 2),
            ]
        )
        coupler_path = pya.Region(coupler_path_polygon.to_itype(self.layout.dbu))
        return coupler_region #coupler_path

    def _build_island1(self):
        island1_left = self.island_offset / 2
        island1_top = self.island1_extent[1] / 2
        ground_bottom = float(self.ground_gap[1]) / 2
        island1_centerx = self.island_offset/2 + self.island1_extent[0] / 2
        taper_height = (float(self.ground_gap[1]) - self.island1_extent[1])/4 - self.pad_to_pad_separation/2
        island1_polygon = pya.DPolygon(
            [
                pya.DPoint(
                    island1_left + float(self.island1_extent[0]), -float(self.island1_extent[1]) / 2
                ),
                pya.DPoint(
                    island1_left + float(self.island1_extent[0]), float(self.island1_extent[1]) / 2
                ),
                pya.DPoint(island1_left, float(self.island1_extent[1]) / 2),
                pya.DPoint(island1_left, -float(self.island1_extent[1]) / 2),
            ]
        )
        island1_taper1 = pya.Region(
            pya.DPolygon(
                [
                    pya.DPoint(self.island1_taper_width / 2 + island1_centerx, island1_top),
                    pya.DPoint(self.island1_taper_junction_width / 2 + island1_centerx, island1_top + taper_height),
                    pya.DPoint(-self.island1_taper_junction_width / 2 + island1_centerx, island1_top + taper_height),
                    pya.DPoint(-self.island1_taper_width / 2 + island1_centerx, island1_top),
                ]
            ).to_itype(self.layout.dbu)
        )
        island1_region = pya.Region(island1_polygon.to_itype(self.layout.dbu))
        island1_region += island1_taper1
        island1_region.round_corners(self.island1_r / self.layout.dbu, self.island1_r / self.layout.dbu, self.n)
        island1_taper2 = pya.Region(
            pya.DPolygon(
                [
                    pya.DPoint(self.island1_taper_width / 2 + island1_centerx, ground_bottom),
                    pya.DPoint(self.island1_taper_junction_width / 2 + island1_centerx, ground_bottom - taper_height),
                    pya.DPoint(-self.island1_taper_junction_width / 2 + island1_centerx, ground_bottom - taper_height),
                    pya.DPoint(-self.island1_taper_width / 2 + island1_centerx, ground_bottom),
                    pya.DPoint(-self.island1_taper_width * 4 + island1_centerx, ground_bottom),
                    pya.DPoint(-self.island1_taper_width * 4 + island1_centerx, ground_bottom + taper_height),
                    pya.DPoint(self.island1_taper_width * 4 + island1_centerx, ground_bottom + taper_height),
                    pya.DPoint(self.island1_taper_width * 4 + island1_centerx, ground_bottom),
                ]
            ).to_itype(self.layout.dbu)
        )
        island1_taper2.round_corners(self.island1_r / self.layout.dbu, self.island1_r / self.layout.dbu, self.n)



        return island1_region + island1_taper1 + island1_taper2

    def _build_island2(self):
        island2_right = -self.island_offset / 2
        island2_polygon = pya.DPolygon(
            [
                pya.DPoint(
                    island2_right - float(self.island2_extent[0]), -float(self.island2_extent[1]) / 2
                ),
                pya.DPoint(
                    island2_right - float(self.island2_extent[0]), -float(self.bias_width) / 2
                ),
                pya.DPoint(
                    island2_right - float(self.island2_extent[0]) - self.island2_r*2, -float(self.bias_width) / 2
                ),
                pya.DPoint(
                    island2_right - float(self.island2_extent[0]) - self.island2_r*2, float(self.bias_width) / 2
                ),
                pya.DPoint(
                    island2_right - float(self.island2_extent[0]), float(self.bias_width) / 2
                ),
                pya.DPoint(
                    island2_right - float(self.island2_extent[0]), float(self.island2_extent[1]) / 2
                ),
                pya.DPoint(island2_right, float(self.island2_extent[1]) / 2),
                pya.DPoint(island2_right, -float(self.island2_extent[1]) / 2),
            ]
        )
        island2_region = pya.Region(island2_polygon.to_itype(self.layout.dbu))
        island2_region.round_corners(self.island2_r / self.layout.dbu, self.island2_r / self.layout.dbu, self.n)
        #island2_taper = pya.Region(
        #    pya.DPolygon(
        #        [
        #            pya.DPoint(self.island2_taper_width / 2, island2_top - taper_height),
        #            pya.DPoint(self.island2_taper_junction_width / 2, island2_top),
        #            pya.DPoint(-self.island2_taper_junction_width / 2, island2_top),
        #            pya.DPoint(-self.island2_taper_width / 2, island2_top - taper_height),
        #        ]
        #    ).to_itype(self.layout.dbu)
        #)

        island2_bias = pya.Region(
            pya.DPolygon(
                [
                    pya.DPoint(island2_right - float(self.island2_extent[0]) - self.island2_r, self.bias_width/2),
                    pya.DPoint(island2_right - float(self.island2_extent[0]) - self.island2_r, -self.bias_width/2),
                    pya.DPoint(-float(self.ground_gap[0])/2, -float(self.bias_width/2)),
                    pya.DPoint(-float(self.ground_gap[0])/2, float(self.bias_width/2)),
                ]
            ).to_itype(self.layout.dbu)
        )
        return island2_region #+ island2_bias

    @classmethod
    def get_sim_ports(cls, simulation):  # pylint: disable=unused-argument
        return [JunctionSimPort(), WaveguideToSimPort("port_cplr", side="top")]
