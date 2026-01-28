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
from kqcircuits.util.refpoints import WaveguideToSimPort, RefpointToInternalPort


class FingerCapacitorGroundV3(Element):
    """Refactored by Roger grounded finger capacitor with clear coordinate system.

    COORDINATE SYSTEM:
    - Origin (0, 0) is at the center of the structure
    - Y-axis: vertical, ports at y = ±finger_array_half_height
    - X-axis: horizontal, fingers extend symmetrically left/right from center

    """

    
    finger_gap = Param(pdt.TypeDouble, "Gap between the fingers", 3, unit="μm")
    finger_width = Param(pdt.TypeDouble, "Width of each finger", 3, unit="μm")
    finger_length = Param(pdt.TypeDouble, "Finger length", 20, unit="μm")
    finger_number = Param(pdt.TypeInt, "Number of fingers", 4)
    corner_r = Param(pdt.TypeDouble, "Corner rounding radius", 1, unit="μm")
    ground_cutout_bool = Param(pdt.TypeBoolean, "Whether to cut off center conductor from ground for sims", False)

    # Lumped model parameters
    use_lumped_model = Param(pdt.TypeBoolean, "Use lumped capacitance instead of full geometry", False)
    lumped_capacitance = Param(pdt.TypeDouble, "Capacitance for lumped model (fF)", 100.0, unit="fF")
    
    
    def can_create_from_shape_impl(self):
        return self.shape.is_path()

    def build(self):
        """Main build method that constructs the finger capacitor geometry."""

        ground_width = self.a + 2 * (self.finger_length + self.finger_gap)
        ground_length = self.finger_number * 2 * (self.finger_width + self.finger_gap)

        if self.use_lumped_model:
            # LUMPED MODEL MODE: Create geometry on lumped_rlc layer for boundary attachment
            # This layer exports to ANSYS as a non-model surface that lumped RLC boundaries attach to

            self.refpoints['top_port'] = pya.DPoint(0, 0)
            self.refpoints['bottom_port'] = pya.DPoint(0, -ground_length)

            # Create attachment rectangle on lumped_rlc layer
            # This geometry will be exported to ANSYS for boundary attachment
            # Width and length define the region where the lumped capacitor exists
            cap_width = self.a  # Width matches waveguide
            cap_length = ground_length  # Full capacitor region length

            # Rectangle geometry for ANSYS boundary attachment
            # This will be exported as a non-model surface (material=None in simulation.py)
            attachment_region = pya.Region(
                pya.DPolygon(
                    [
                        pya.DPoint(-cap_width/2, 0),           # Top-left
                        pya.DPoint(cap_width/2, 0),            # Top-right
                        pya.DPoint(cap_width/2, -cap_length),  # Bottom-right
                        pya.DPoint(-cap_width/2, -cap_length), # Bottom-left
                    ]
                ).to_itype(self.layout.dbu)
            )

            # Insert on lumped_rlc layer - will be extracted by simulation.py and exported to ANSYS
            self.cell.shapes(self.get_layer("lumped_rlc")).insert(attachment_region)

            # Signal and ground locations define the lumped RLC current line direction
            # ANSYS will use these coordinates to attach the lumped RLC boundary
            signal_y = -cap_length * 0.2  # Near resonator connection (20% down)
            ground_y = -cap_length * 0.8  # Near ground connection (80% down)
            ground_region = pya.Region(
                pya.DPolygon(
                    [
                        pya.DPoint(-cap_width, 0),           # Top-left
                        pya.DPoint(-cap_width/2, 0),
                        pya.DPoint(-cap_width/2, signal_y),
                        pya.DPoint(cap_width/2, signal_y),
                        pya.DPoint(cap_width/2, 0),
                        pya.DPoint(cap_width, 0),            # Top-right
                        pya.DPoint(cap_width, ground_y),  # Bottom-right
                        pya.DPoint(-cap_width, ground_y), # Bottom-left
                    ]
                ).to_itype(self.layout.dbu)
            )
            self.cell.shapes(self.get_layer("base_metal_gap_wo_grid")).insert(ground_region)

            # Diagonal placement avoids numerical issues in polygon creation
            self.refpoints['signal_location'] = pya.DPoint(-cap_width/4, signal_y)
            self.refpoints['ground_location'] = pya.DPoint(cap_width/4, ground_y)

            return  # Skip full capacitor geometry creation

        region_ground = pya.Region(
            pya.DPolygon(
                [
                    pya.DPoint(-ground_width / 2, -ground_length / 2),
                    pya.DPoint(-ground_width / 2, ground_length / 2),
                    pya.DPoint(ground_width / 2, ground_length / 2),
                    pya.DPoint(ground_width / 2, -ground_length / 2),
                ]
            ).to_itype(self.layout.dbu)
        )

        # Create all geometric regions
        region_fingers = pya.Region()
        finger_step = -2 * (self.finger_width + self.finger_gap)
        i = 0
        while i < self.finger_number:
            if (i == 0):
                gap = self.b
            else:
                gap = self.finger_gap

            finger_l_pts = pya.DPolygon(
                [pya.DPoint(-self.a/2, i * finger_step),
                 pya.DPoint(-self.a/2, i * finger_step - self.finger_width - self.finger_gap),
                 pya.DPoint(-self.a/2 - self.finger_length, i * finger_step - self.finger_width - self.finger_gap),
                 pya.DPoint(-self.a/2 - self.finger_length, i * finger_step - 2 * self.finger_width - self.finger_gap),
                 pya.DPoint(-self.a/2, i * finger_step - 2 * self.finger_width - self.finger_gap),
                 pya.DPoint(-self.a/2, i * finger_step - 2 * self.finger_width - 2 * self.finger_gap),
                 pya.DPoint(-self.a/2 - self.finger_gap - self.finger_length, i * finger_step - 2 * self.finger_width - 2 * self.finger_gap),
                 pya.DPoint(-self.a/2 - self.finger_gap - self.finger_length, i * finger_step - self.finger_width),
                 pya.DPoint(-self.a/2 - gap, i * finger_step - self.finger_width),
                 pya.DPoint(-self.a/2 - gap, i * finger_step),
                ]
            )

            
            finger_r_pts = pya.DPolygon(
                [pya.DPoint(self.a/2, i * finger_step),
                 pya.DPoint(self.a/2, i * finger_step - self.finger_width - self.finger_gap),
                 pya.DPoint(self.a/2 + self.finger_length, i * finger_step - self.finger_width - self.finger_gap),
                 pya.DPoint(self.a/2 + self.finger_length, i * finger_step - 2 * self.finger_width - self.finger_gap),
                 pya.DPoint(self.a/2, i * finger_step - 2 * self.finger_width - self.finger_gap),
                 pya.DPoint(self.a/2, i * finger_step - 2 * self.finger_width - 2 * self.finger_gap),
                 pya.DPoint(self.a/2 + self.finger_gap + self.finger_length, i * finger_step - 2 * self.finger_width - 2 * self.finger_gap),
                 pya.DPoint(self.a/2 + self.finger_gap + self.finger_length, i * finger_step - self.finger_width),
                 pya.DPoint(self.a/2 + gap, i * finger_step - self.finger_width),
                 pya.DPoint(self.a/2 + gap, i * finger_step),
                ]
            )

            finger_l_region = pya.Region(finger_l_pts.to_itype(self.layout.dbu))
            finger_r_region = pya.Region(finger_r_pts.to_itype(self.layout.dbu))
            region_fingers += finger_l_region
            region_fingers += finger_r_region
            i += 1
        
        region_lead_in_bl = pya.Region(pya.DPolygon(
            [
                pya.DPoint(-self.a/2, -ground_length),
                pya.DPoint(-self.a/2 - self.b, -ground_length),
                pya.DPoint(-self.a/2 - self.b, -ground_length - self.finger_width),
                pya.DPoint(-self.a/2, -ground_length - self.finger_width),
            ]
        ).to_itype(self.layout.dbu))
        region_lead_in_br = pya.Region(pya.DPolygon(
            [
                pya.DPoint(self.a/2, -ground_length),
                pya.DPoint(self.a/2 + self.b, -ground_length),
                pya.DPoint(self.a/2 + self.b, -ground_length - self.finger_width),
                pya.DPoint(self.a/2, -ground_length - self.finger_width),
            ]
        ).to_itype(self.layout.dbu))
        region_fingers += (region_lead_in_bl + region_lead_in_br)

        region_fingers.round_corners(self.corner_r / self.layout.dbu, self.corner_r / self.layout.dbu, self.n)
        
        region_lead_in_tl = pya.Region(pya.DPolygon(
            [
                pya.DPoint(-self.a/2, 0),
                pya.DPoint(-self.a/2 - self.b, 0),
                pya.DPoint(-self.a/2 - self.b, -self.corner_r),
                pya.DPoint(-self.a/2, -self.corner_r),
            ]
        ).to_itype(self.layout.dbu))
        region_lead_in_tr = pya.Region(pya.DPolygon(
            [
                pya.DPoint(self.a/2, 0),
                pya.DPoint(self.a/2 + self.b, 0),
                pya.DPoint(self.a/2 + self.b, -self.corner_r),
                pya.DPoint(self.a/2, -self.corner_r),
            ]
        ).to_itype(self.layout.dbu))
        region_lead_in_bl = pya.Region(pya.DPolygon(
            [
                pya.DPoint(-self.a/2, -ground_length - self.finger_width),
                pya.DPoint(-self.a/2 - self.b, -ground_length - self.finger_width),
                pya.DPoint(-self.a/2 - self.b, -ground_length - self.finger_width + self.corner_r),
                pya.DPoint(-self.a/2, -ground_length - self.finger_width + self.corner_r),
            ]
        ).to_itype(self.layout.dbu))
        region_lead_in_br = pya.Region(pya.DPolygon(
            [
                pya.DPoint(self.a/2, -ground_length - self.finger_width),
                pya.DPoint(self.a/2 + self.b, -ground_length - self.finger_width),
                pya.DPoint(self.a/2 + self.b, -ground_length - self.finger_width + self.corner_r),
                pya.DPoint(self.a/2, -ground_length - self.finger_width + self.corner_r),
            ]
        ).to_itype(self.layout.dbu))
        region_fingers += (region_lead_in_tl + region_lead_in_tr + region_lead_in_bl + region_lead_in_br)

        if self.ground_cutout_bool:
            region_cutout_top = pya.Region(pya.DPolygon(
                [
                    pya.DPoint(-self.a/2 - self.b, 0),
                    pya.DPoint(self.a/2 + self.b, 0),
                    pya.DPoint(self.a/2 + self.b, 3*self.finger_gap),
                    pya.DPoint(-self.a/2 - self.b, 3*self.finger_gap),
                ]
            ).to_itype(self.layout.dbu))
            region_cutout_bottom = pya.Region(pya.DPolygon(
                [
                    pya.DPoint(-self.a/2 - self.b, -ground_length - self.finger_width),
                    pya.DPoint(self.a/2 + self.b, -ground_length - self.finger_width),
                    pya.DPoint(self.a/2 + self.b, -ground_length - self.finger_width - 3*self.finger_gap),
                    pya.DPoint(-self.a/2 - self.b, -ground_length - self.finger_width - 3*self.finger_gap),
                ]
            ).to_itype(self.layout.dbu))
            region_fingers += (region_cutout_top + region_cutout_bottom)


        self.cell.shapes(self.get_layer("base_metal_gap_wo_grid")).insert(region_fingers)
        self.cell.shapes(self.get_layer("mesh_4")).insert(region_fingers)

        # Add ports at top and bottom
        #self.add_port("a", pya.DPoint(0, -finger_array_half_height), pya.DVector(0, -1))
        #self.add_port("b", pya.DPoint(0, finger_array_half_height), pya.DVector(0, 1))
        self.refpoints['top_port'] = pya.DPoint(0, 0)
        self.refpoints['bottom_port'] = pya.DPoint(0, -ground_length)

        # Reference point for internal port placement in capacitance simulations
        # This point is at the center of the structure, inside the center conductor
        self.refpoints['signal_location'] = pya.DPoint(0, -ground_length/2)

    @classmethod
    def get_sim_ports(cls, simulation):
        """Return simulation ports.

        If use_lumped_model=True, returns lumped RLC port.
        If use_lumped_model=False, returns no ports (just geometry).
        """
        # Check for both singular and plural parameter names for compatibility
        use_lumped = getattr(simulation, 'use_lumped_model', False) or getattr(simulation, 'use_lumped_models', False)

        if use_lumped:
            # Return lumped capacitor port
            # Get capacitance from either singular or plural parameter name
            cap_value = getattr(simulation, 'lumped_capacitance', getattr(simulation, 'cap_lumped_value', 100.0))

            return [
                RefpointToInternalPort(
                    refpoint="signal_location",
                    ground_refpoint="ground_location",
                    capacitance=cap_value * 1e-15,  # fF to F
                    inductance=0,
                    resistance=0,
                    lumped_element=True,
                    rlc_type="parallel",
                )
            ]
        else:
            # Full geometry - no ports needed
            return []

