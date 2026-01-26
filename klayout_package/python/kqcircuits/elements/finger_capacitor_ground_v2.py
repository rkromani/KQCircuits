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


from kqcircuits.pya_resolver import pya
from kqcircuits.util.parameters import Param, pdt, add_parameters_from
from kqcircuits.elements.element import Element
from kqcircuits.elements.finger_capacitor_taper import FingerCapacitorTaper
from kqcircuits.util.refpoints import WaveguideToSimPort


def eval_a2(element):
    """Evaluation function for center conductor width on the other end."""
    return element.a if element.a2 < 0 else element.a2


def eval_b2(element):
    """Evaluation function for gap width on the other end."""
    return element.b if element.b2 < 0 else element.b2


@add_parameters_from(FingerCapacitorTaper, "*", "taper_length")
class FingerCapacitorGroundV2(Element):
    """Refactored grounded finger capacitor with clear coordinate system.

    COORDINATE SYSTEM:
    - Origin (0, 0) is at the center of the structure
    - Y-axis: vertical, ports at y = ±finger_array_half_height
    - X-axis: horizontal, fingers extend symmetrically left/right from center

    STRUCTURE:
    - Center conductor: vertical strip at x=0, width=a, connects to ports at top/bottom
    - Interdigitated fingers:
        * Even fingers (i=0,2,4...): extend full length horizontally, centered at x=0
        * Odd fingers (i=1,3,5...): split into two halves on left/right sides of center conductor
    - Ground plane: surrounds finger structure with ground_padding spacing

    The design creates a large capacitance to ground through the interdigitated finger structure.

    .. MARKERS_FOR_PNG 20,-10,ground_padding 0,17,finger_width 0,5,finger_gap
    """

    a2 = Param(
        pdt.TypeDouble,
        "Width of center conductor on the other end",
        -1,
        unit="μm",
        docstring="Non-physical value '-1' means that the default size 'a' is used.",
    )
    b2 = Param(
        pdt.TypeDouble,
        "Width of gap on the other end",
        -1,
        unit="μm",
        docstring="Non-physical value '-1' means that the default size 'b' is used.",
    )
    finger_gap_end = Param(pdt.TypeDouble, "Gap between the finger and center conductor", 3, unit="μm")
    ground_padding = Param(pdt.TypeDouble, "Ground plane padding around finger structure", 10, unit="μm")
    fixed_length = Param(pdt.TypeDouble, "Fixed length of element, 0 for auto-length", 0, unit="μm")
    ground_gap_ratio = Param(pdt.TypeDouble, "Ground connection width per gap ratio", 0, unit="μm")
    cutout_bool = Param(pdt.TypeBoolean, "Whether to cut out the center conductor for capacitance sims", False)

    def can_create_from_shape_impl(self):
        return self.shape.is_path()

    def build(self):
        """Main build method that constructs the finger capacitor geometry."""

        # Create all geometric regions
        region_ground = self._create_ground_plane()
        region_center = self._create_center_conductor()
        region_ground_extensions = self._create_ground_extensions()
        region_fingers = self._create_fingers()

        # Combine conductor regions (everything that should be etched from ground plane)
        region_etch = region_ground_extensions + region_fingers + region_center
        region_etch.round_corners(self.corner_r / self.layout.dbu, self.corner_r / self.layout.dbu, self.n)

        # Round ground plane corners
        region_ground.round_corners(self.corner_r / self.layout.dbu, self.corner_r / self.layout.dbu, self.n)

        # Final geometry: ground plane with conductor etched out
        region = region_ground - region_etch

        self.cell.shapes(self.get_layer("base_metal_gap_wo_grid")).insert(region)

        # Add ports at top and bottom
        finger_array_half_height = self.finger_array_height() / 2
        self.add_port("a", pya.DPoint(0, -finger_array_half_height), pya.DVector(0, -1))
        self.add_port("b", pya.DPoint(0, finger_array_half_height), pya.DVector(0, 1))
        self.refpoints['top_port'] = pya.DPoint(0, finger_array_half_height)
        self.refpoints['bottom_port'] = pya.DPoint(0, -finger_array_half_height)

        # Reference point for internal port placement in capacitance simulations
        # This point is at the center of the structure, inside the center conductor
        self.refpoints['signal_location'] = pya.DPoint(0, 0)

    def _create_ground_plane(self):
        """Creates the main ground plane rectangle.

        Returns:
            pya.Region: Ground plane that will surround the entire finger capacitor structure
        """
        # Calculate extent of finger array
        finger_array_half_height = self.finger_array_height() / 2

        # Ground plane extends from finger array edges by ground_padding
        ground_half_height = finger_array_half_height + self.ground_padding

        # Ground plane extends horizontally to cover fingers plus padding
        # Even fingers extend to ±finger_length/2
        # Odd fingers extend to ±(a/2 + finger_gap_end + finger_length/2)
        # Ground plane must cover the odd fingers (which extend further) plus ground_padding
        center_conductor_half_width = self.a / 2
        odd_finger_extent = center_conductor_half_width - self.finger_gap_end + self.finger_length/2
        ground_half_width = odd_finger_extent + self.finger_gap_end

        region_ground = pya.Region(
            pya.DPolygon(
                [
                    pya.DPoint(-ground_half_width, -ground_half_height),
                    pya.DPoint(-ground_half_width, ground_half_height),
                    pya.DPoint(ground_half_width, ground_half_height),
                    pya.DPoint(ground_half_width, -ground_half_height),
                ]
            ).to_itype(self.layout.dbu)
        )

        return region_ground

    def _create_center_conductor(self):
        """Creates the center conductor strip that connects the top and bottom ports.

        The center conductor runs vertically through the middle of the structure (at x=0).
        Its width determines the gap between odd finger halves.

        Returns:
            pya.Region: Center conductor region
        """
        center_conductor_half_width = self.a / 2
        finger_array_half_height = self.finger_array_height() / 2

        # Height of center conductor depends on cutout_bool parameter
        if self.cutout_bool:
            # Smaller conductor for capacitance simulations
            conductor_half_height = finger_array_half_height + self.ground_padding * 0.5
        else:
            # Extended conductor for regular simulations
            conductor_half_height = finger_array_half_height + self.ground_padding * 2

        region_center = pya.Region(
            pya.DPolygon(
                [
                    pya.DPoint(-center_conductor_half_width, -conductor_half_height),
                    pya.DPoint(-center_conductor_half_width, conductor_half_height),
                    pya.DPoint(center_conductor_half_width, conductor_half_height),
                    pya.DPoint(center_conductor_half_width, -conductor_half_height),
                ]
            ).to_itype(self.layout.dbu)
        )

        return region_center

    def _create_ground_extensions(self):
        """Creates L-shaped ground extensions on left and right sides.

        These extensions connect the ground plane to the center conductor area,
        wrapping around the ends of the finger structure.

        Returns:
            pya.Region: Combined left and right ground extension regions
        """
        finger_array_half_height = self.finger_array_height() / 2
        center_conductor_half_width_left = self.a / 2
        center_conductor_half_width_right = eval_a2(self) / 2

        # X-coordinates for ground extensions
        # Extensions must clear the odd fingers, which extend to ±(a/2 + finger_gap_end + finger_length/2)
        even_finger_edge = self.finger_length / 2
        odd_finger_extent = center_conductor_half_width_right + self.finger_gap_end + self.finger_length / 2
        extension_inner_x_left = odd_finger_extent + self.finger_gap_end
        extension_inner_x_right = odd_finger_extent + self.finger_gap_end

        # Add ground padding if center conductor is wider than finger array
        if center_conductor_half_width_left > finger_array_half_height:
            extension_inner_x_left += self.ground_padding
        if center_conductor_half_width_right > finger_array_half_height:
            extension_inner_x_right += self.ground_padding

        extension_outer_x = extension_inner_x_right + self.ground_padding

        # Right side L-shaped extension
        region_ground_right = pya.Region(
            pya.DPolygon(
                [
                    pya.DPoint(even_finger_edge, finger_array_half_height),
                    pya.DPoint(extension_inner_x_right, finger_array_half_height),
                    pya.DPoint(extension_inner_x_right, finger_array_half_height + self.ground_padding),
                    pya.DPoint(extension_outer_x, finger_array_half_height + self.ground_padding),
                    pya.DPoint(extension_outer_x, -finger_array_half_height - self.ground_padding),
                    pya.DPoint(extension_inner_x_right, -finger_array_half_height - self.ground_padding),
                    pya.DPoint(extension_inner_x_right, -finger_array_half_height),
                    pya.DPoint(even_finger_edge, -finger_array_half_height),
                ]
            ).to_itype(self.layout.dbu)
        )

        # Left side L-shaped extension (mirror of right side)
        region_ground_left = pya.Region(
            pya.DPolygon(
                [
                    pya.DPoint(-even_finger_edge, finger_array_half_height),
                    pya.DPoint(-extension_inner_x_left, finger_array_half_height),
                    pya.DPoint(-extension_inner_x_left, finger_array_half_height + self.ground_padding),
                    pya.DPoint(-extension_outer_x, finger_array_half_height + self.ground_padding),
                    pya.DPoint(-extension_outer_x, -finger_array_half_height - self.ground_padding),
                    pya.DPoint(-extension_inner_x_left, -finger_array_half_height - self.ground_padding),
                    pya.DPoint(-extension_inner_x_left, -finger_array_half_height),
                    pya.DPoint(-even_finger_edge, -finger_array_half_height),
                ]
            ).to_itype(self.layout.dbu)
        )

        return region_ground_left + region_ground_right

    def _create_fingers(self):
        """Creates the interdigitated finger structure.

        The finger pattern alternates:
        - Even fingers (i=0,2,4...): horizontal bars spanning full finger_length, centered at x=0
        - Odd fingers (i=1,3,5...): split into two halves, one on each side of center conductor

        This creates interdigitation with the center conductor running between the odd finger halves.

        Returns:
            pya.Region: All finger polygons combined
        """
        finger_array_half_height = self.finger_array_height() / 2
        center_conductor_half_width = self.a / 2

        polys_fingers = []

        for i in range(self.finger_number):
            # Y-position: fingers stack vertically, starting from bottom
            y_bottom = i * (self.finger_width + self.finger_gap) - finger_array_half_height
            y_top = y_bottom + self.finger_width

            if (i % 2) == 0:
                # Even finger: full horizontal bar centered at x=0
                finger_half_length = self.finger_length / 2
                polys_fingers.append(
                    pya.DPolygon(
                        [
                            pya.DPoint(-finger_half_length, y_bottom),
                            pya.DPoint(-finger_half_length, y_top),
                            pya.DPoint(finger_half_length, y_top),
                            pya.DPoint(finger_half_length, y_bottom),
                        ]
                    )
                )
            else:
                # Odd finger: split into left and right halves
                # Right half
                right_finger_inner_x = center_conductor_half_width + self.finger_gap_end
                right_finger_outer_x = right_finger_inner_x + self.finger_length / 2
                polys_fingers.append(
                    pya.DPolygon(
                        [
                            pya.DPoint(right_finger_inner_x, y_bottom),
                            pya.DPoint(right_finger_inner_x, y_top),
                            pya.DPoint(right_finger_outer_x, y_top),
                            pya.DPoint(right_finger_outer_x, y_bottom),
                        ]
                    )
                )

                # Left half (mirror of right)
                left_finger_inner_x = -center_conductor_half_width - self.finger_gap_end
                left_finger_outer_x = left_finger_inner_x - self.finger_length / 2
                polys_fingers.append(
                    pya.DPolygon(
                        [
                            pya.DPoint(left_finger_inner_x, y_bottom),
                            pya.DPoint(left_finger_inner_x, y_top),
                            pya.DPoint(left_finger_outer_x, y_top),
                            pya.DPoint(left_finger_outer_x, y_bottom),
                        ]
                    )
                )

        region_fingers = pya.Region([poly.to_itype(self.layout.dbu) for poly in polys_fingers])
        return region_fingers

    def finger_array_height(self):
        """Calculate total height of finger array.

        Returns:
            float: Height occupied by all fingers including gaps between them
        """
        return self.finger_number * self.finger_width + (self.finger_number - 1) * self.finger_gap

    def finger_array_length(self):
        """Calculate total length of finger array.

        Returns:
            float: Length includes finger length plus gap to center conductor
        """
        return self.finger_length + self.finger_gap_end

    def get_total_height(self):
        """Calculate total height of the structure including ground padding.

        This is the full Y-extent of the ground plane.

        Returns:
            float: Total height from bottom to top of ground plane
        """
        return self.finger_array_height() + 2 * self.ground_padding

    def get_half_height(self):
        """Calculate half-height of the structure including ground padding.

        Useful for positioning: if you place the capacitor at y_center,
        the bottom edge is at y_center - get_half_height()
        and the top edge is at y_center + get_half_height()

        Returns:
            float: Distance from center to top/bottom edge of ground plane
        """
        return self.finger_array_height() / 2 + self.ground_padding

    @staticmethod
    def calculate_half_height(finger_number, finger_width, finger_gap, ground_padding=10):
        """Calculate half-height from parameters without creating an instance.

        Useful for positioning before inserting the cell.

        Args:
            finger_number: Number of fingers
            finger_width: Width of each finger
            finger_gap: Gap between fingers
            ground_padding: Padding around finger array (default: 10)

        Returns:
            float: Distance from center to top/bottom edge of ground plane
        """
        finger_array_height = finger_number * finger_width + (finger_number - 1) * finger_gap
        return finger_array_height / 2 + ground_padding

    @classmethod
    def get_sim_ports(cls, simulation):
        """Returns simulation ports for the two ends of the capacitor.

        The a and b values of right waveguide can be adjusted separately using a2 and b2 parameters.
        """
        return [
            WaveguideToSimPort("port_a", side="left", a=simulation.a, b=simulation.b),
            WaveguideToSimPort("port_b", side="right", a=eval_a2(simulation), b=eval_b2(simulation)),
        ]
