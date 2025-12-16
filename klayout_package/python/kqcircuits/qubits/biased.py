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


@add_parameters_from(Squid, junction_type="Overlap2")
@add_parameters_from(Manhattan)
@add_parameters_from(ManhattanSingleJunction)
class BiasedGrounded(Qubit):
    """
    A grounded transmon, where most of the capacitance to ground is through an electrode close to the main transmon that
    can be biased, but can be connected to ground with a large capacitance added at the chip level.
    """

    ground_gap = Param(pdt.TypeList, "Width, height of the ground gap (µm, µm)", [700, 900])
    ground_gap_r = Param(pdt.TypeDouble, "Ground gap rounding radius", 50, unit="μm")
    coupler_extent = Param(pdt.TypeList, "Width, height of the coupler (µm, µm)", [20, 150])
    coupler_r = Param(pdt.TypeDouble, "Coupler rounding radius", 10, unit="μm")
    coupler_a = Param(pdt.TypeDouble, "Width of the coupler waveguide center conductor", Element.a, unit="μm")
    coupler_offset = Param(pdt.TypeDouble, "Distance from first qubit island to coupler", 20, unit="μm")
    island_offset = Param(pdt.TypeDouble, "Distance between islands", 40, unit="μm")
    #squid_offset = Param(pdt.TypeDouble, "Offset between SQUID center and qubit center", 0, unit="μm")
    island1_extent = Param(pdt.TypeList, "Width, height of the first qubit island (µm, µm)", [100, 500])
    island1_r = Param(pdt.TypeDouble, "First qubit island rounding radius", 30, unit="μm")
    island2_extent = Param(pdt.TypeList, "Width, height of the second qubit island (µm, µm)", [100, 500])
    island2_r = Param(pdt.TypeDouble, "Second qubit island rounding radius", 30, unit="μm")
    drive_position = Param(pdt.TypeList, "Coordinate for the drive port (µm, µm)", [-450, 0])
    island1_taper_width = Param(pdt.TypeDouble, "Junction tapering width on the island/ground side", 30, unit="µm")
    island1_taper_junction_width = Param(
        pdt.TypeDouble, "Junction tapering width on the junction side", 15, unit="µm"
    )
    #island2_taper_width = Param(pdt.TypeDouble, "Second qubit island tapering width on the island side", 10, unit="µm")
    #island2_taper_junction_width = Param(
    #    pdt.TypeDouble, "Second qubit island tapering width on the junction side", 10, unit="µm" 
    #)

    island_island_gap = Param(pdt.TypeDouble, "Island to island gap distance", 70, unit="µm")
    with_junction = Param(pdt.TypeBoolean, "Boolean whether to include the junction", True)
    junction_width = Param(pdt.TypeDouble, "Junction total width", 28, unit="µm")
    junction_height = Param(pdt.TypeDouble, "Junction total height", 85, unit="µm")
    junction_pad_sep = Param(pdt.TypeDouble, "Junction pad separation", 15, unit="µm")

    bias_width = Param(pdt.TypeDouble, "Bias width connection to island 2", 20, unit="µm")

    def build(self):
        # Qubit base
        ground_gap_points = [
            pya.DPoint(float(self.ground_gap[0]) / 2, float(self.ground_gap[1]) / 2),
            pya.DPoint(float(self.ground_gap[0]) / 2, -float(self.ground_gap[1]) / 2),
            pya.DPoint(-float(self.ground_gap[0]) / 2, -float(self.ground_gap[1]) / 2),
            pya.DPoint(-float(self.ground_gap[0]) / 2, float(self.ground_gap[1]) / 2),
        ]
        ground_gap_polygon = pya.DPolygon(ground_gap_points)
        ground_gap_region = pya.Region(ground_gap_polygon.to_itype(self.layout.dbu))
        ground_gap_region.round_corners(
            self.ground_gap_r / self.layout.dbu, self.ground_gap_r / self.layout.dbu, self.n
        )

        # SQUID
        # Create temporary SQUID cell to calculate SQUID height
        #temp_squid_cell = self.add_element(Squid, junction_type=self.junction_type)
        #temp_squid_ref = self.get_refpoints(temp_squid_cell)
        #squid_height = temp_squid_ref["port_common"].distance(pya.DPoint(0, 0))
        # Now actually add SQUID
        #squid_transf = pya.DCplxTrans(1, 0, False, pya.DVector(0, self.squid_offset - squid_height / 2))

        #if self.with_squid:
        #    self.produce_squid(squid_transf)
        
        temp_junction_cell = self.add_element(Squid, junction_type=self.junction_type)
        #temp_junction_ref = self.get_refpoints(temp_junction_cell)
        #junction_height = 100# temp_junction_ref["port_common"].distance(pya.DPoint(0, 0))

        junction_centerx = self.island1_extent[0]/2 + self.island_offset/2 #- self.pad_width/2
        junction_centery = float(self.island1_extent[1])/2 + (float(self.ground_gap[1]) - self.island1_extent[1])/4
        # Now actually add SQUID
        junction_transf = pya.DCplxTrans(1, 0, False, pya.DVector(junction_centerx, junction_centery))#, pad_width=self.junction_width)
        #if self.with_junction:
        #    self.produce_squid(junction_transf, pad_to_pad_separation=self.junction_pad_sep, pad_height=(self.junction_height - self.junction_pad_sep)/2)

        #taper_height = (self.island_island_gap - squid_height) / 2

        # First island
        island1_region = self._build_island1()

        # Second island
        island2_region = self._build_island2()

        # Coupler gap
        coupler_region = self._build_coupler(
            (self.island_offset/2 + float(self.island1_extent[0]))
        )

        self.cell.shapes(self.get_layer("base_metal_gap_wo_grid")).insert(
            ground_gap_region - coupler_region - island1_region - island2_region
        )

        # Protection
        protection_polygon = pya.DPolygon(
            [
                p + pya.DVector(math.copysign(self.margin, p.x), math.copysign(self.margin, p.y))
                for p in ground_gap_points
            ]
        )
        protection_region = pya.Region(protection_polygon.to_itype(self.layout.dbu))
        protection_region.round_corners(
            (self.ground_gap_r + self.margin) / self.layout.dbu,
            (self.ground_gap_r + self.margin) / self.layout.dbu,
            self.n,
        )
        self.add_protection(protection_region)

        # Coupler port
        self.add_port(
            "cplr",
            pya.DPoint(float(self.ground_gap[0]) / 2, 0),
            direction=pya.DVector(pya.DPoint(float(self.ground_gap[0]), 0)),
        )

        # Drive port
        #self.add_port(
        #    "drive",
        #    pya.DPoint(float(self.drive_position[0]), float(self.drive_position[1])),
        #    direction=pya.DVector(float(self.drive_position[0]), float(self.drive_position[1])),
        #)

        # Bias port
        self.add_port(
            "bias",
            pya.DPoint(-float(self.ground_gap[0])/ 2, 0),
            direction=pya.DVector(-pya.DPoint(1, 0)),
        )

        # Probepoints
        #self.refpoints["probe_island_1"] = pya.DPoint(
        #    0, self.squid_offset + squid_height / 2 + taper_height + float(self.island1_extent[1]) / 2
        #)
        #self.refpoints["probe_island_2"] = pya.DPoint(
        #    0, self.squid_offset - squid_height / 2 - taper_height - float(self.island2_extent[1]) / 2
        #)

        # Now actually add SQUID
        #self.refpoints["junction1"] = pya.DPoint(0, squid_height / 2.0)
        #self.refpoints["junction2"] = pya.DPoint(0, -squid_height / 2.0)
        self.refpoints["junction1"] = pya.DPoint(junction_centerx + self.junction_height/2, junction_centery)
        self.refpoints["junction2"] = pya.DPoint(junction_centerx - self.junction_height/2, junction_centery)

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
