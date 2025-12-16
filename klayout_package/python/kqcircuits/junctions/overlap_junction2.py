# This code is part of KQCircuits
# Copyright (C) 2025 Zachary Parrott
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


from math import sqrt
from kqcircuits.pya_resolver import pya
from kqcircuits.util.parameters import Param, pdt
from kqcircuits.junctions.junction import Junction
from kqcircuits.util.symmetric_polygons import polygon_with_vsym, polygon_with_hsym


class Overlap2(Junction):
    """The PCell declaration for a test single junction.
    """
    noSQUID = Param(pdt.TypeBoolean, "Qubit JJ or coupler SQUID JJ.", False)
    hook_thickness = Param(pdt.TypeDouble, "Thickness of hook on catch.", 0.1, unit="μm")
    hook_lead_thickness = Param(pdt.TypeDouble, "Thickness of hook lead in.", 0.1, unit="μm")
    hook_undercut = Param(pdt.TypeDouble, "Length of hook undercut.", 0.300, unit="μm")
    finger_width = Param(pdt.TypeDouble, "Width of the finger.", 0.12, unit="μm")
    hook_width = Param(pdt.TypeDouble, "Width of the hook perpendicular to finger.", 1.0, unit="μm")
    bridge_gap = Param(pdt.TypeDouble, "Gap between finger and hook.", 0.15, unit="μm")
    pad_to_pad_separation = Param(pdt.TypeDouble, "Pad separation.", 12.0, unit="μm")
    pad_height = Param(pdt.TypeDouble, "Height of the junction pad.", 4.0, unit="μm")
    pad_width = Param(pdt.TypeDouble, "Width of the junction pad.", 8.0, unit="μm")
    taper_width = Param(pdt.TypeDouble, "Width of the triangle taper base,", 2.0, unit="μm")
    pad_offset = Param(pdt.TypeDouble, "Setback of pad from base metal edge.", 1.0, unit="μm")
    pad_rounding_radius = Param(pdt.TypeDouble, "Rounding radius of the junction pad.", 1.0, unit="μm")
    junction_height = Param(pdt.TypeDouble, "Override junction height.", 10, unit="μm")
    include_base_metal_gap = Param(pdt.TypeBoolean, "Include base metal gap layer.", True)
    include_base_metal_addition = Param(pdt.TypeBoolean, "Include base metal addition layer.", True)
    shadow_margin = Param(pdt.TypeDouble, "Shadow layer margin near the the pads.", 0.5, unit="μm")
    separate_junctions = Param(pdt.TypeBoolean, "Junctions to separate layer.", False)

    # height = Param(pdt.TypeDouble, "Height of the junction element.", 22.0, unit="μm")
    # width = Param(pdt.TypeDouble, "Width of the junction element.", 22.0, unit="μm")
    
    
    
    x_offset = Param(pdt.TypeDouble, "Horizontal junction offset.", 0, unit="μm")
    

    def build(self, **kwargs):
        # self.metal_height = self.pad_to_pad_separation + 2 * (self.pad_height + self.shadow_margin*4)
        self.metal_height = max(self.pad_to_pad_separation + 2 * (self.pad_height + self.shadow_margin*4), self.junction_height)
        self.width = 10

        self.produce_junction()

    def produce_junction(self):

        # corner rounding parameters
        rounding_params = {
            "rinner": self.pad_rounding_radius,  # inner corner rounding radius
            "router": self.pad_rounding_radius,  # outer corner rounding radius
            "n": 64,  # number of point per rounded corner
        }

        junction_shapes_top = []
        junction_shapes_bottom = []
        shadow_shapes = []
        patch_shapes = []

        # create rounded bottom part
        y0 = (self.pad_to_pad_separation / 2) + self.pad_offset
        bp_pts_left = [
            pya.DPoint(-self.pad_width / 2, y0),
            pya.DPoint(-self.pad_width / 2, y0 + self.pad_height)
        ]
        bp_shape = pya.DTrans(0, False, 0, - self.pad_to_pad_separation - self.pad_height - 2*self.pad_offset) * polygon_with_vsym(bp_pts_left)
        self._round_corners_and_append(bp_shape, junction_shapes_bottom, rounding_params)

        bp_shadow_pts_left = [
            bp_pts_left[0] + pya.DPoint(-self.shadow_margin, -self.shadow_margin),
            bp_pts_left[1] + pya.DPoint(-self.shadow_margin, self.shadow_margin)
        ]
        bp_shadow_shape = pya.DTrans(0, False, 0,
                                     - self.pad_to_pad_separation - self.pad_height - 2*self.pad_offset) * polygon_with_vsym(bp_shadow_pts_left)
        self._round_corners_and_append(bp_shadow_shape, shadow_shapes, rounding_params)

        # bottom patch
        bp_patch_pts_left = [
            bp_pts_left[0] + pya.DPoint(0, -3), #-self.shadow_margin),
            bp_pts_left[1] + pya.DPoint(0, 0)
        ]
        bp_patch_shape = pya.DTrans(0, False, 0, 
                                    - self.pad_to_pad_separation - self.pad_height - 2*self.pad_offset) * polygon_with_vsym(bp_patch_pts_left)
        self._round_corners_and_append(bp_patch_shape, patch_shapes, rounding_params)
        
        # create rounded top part
        tp_shape = pya.DTrans(0, False, 0,
                              self.pad_height/2 + self.pad_to_pad_separation/2) * polygon_with_vsym(bp_pts_left)
                
        tp_shape = pya.DTrans(0, False, 0, 0) * polygon_with_vsym(bp_pts_left)
        self._round_corners_and_append(tp_shape, junction_shapes_top, rounding_params)

        tp_shadow_shape = pya.DTrans(0, False, 0, 0) * polygon_with_vsym(bp_shadow_pts_left)
        self._round_corners_and_append(tp_shadow_shape, shadow_shapes, rounding_params)

        tp_patch_shape = pya.DTrans(2, False, 0, 0) * bp_patch_shape
        self._round_corners_and_append(tp_patch_shape, patch_shapes, rounding_params)

        # create rectangular junction-support structures and junctions
        if self.noSQUID:
            self._make_qubit_junction()
        else:
            self._make_squid_junction()

        # self._make_junction(pya.DPoint(0, self.metal_height / 2 + 2.8), self.metal_height / 2 - 5, 0)
        self._add_shapes(junction_shapes_bottom, "SIS_junction")
        self._add_shapes(junction_shapes_top, "SIS_junction")
        self._add_shapes(shadow_shapes, "SIS_shadow")
        self._add_shapes(patch_shapes, "SIS_junction_2")
        self._produce_ground_metal_shapes()
        self._produce_ground_grid_avoidance()
        self._add_refpoints()

    def _make_qubit_junction(self): #, top_corner, b_corner_y, finger_margin=0):
        """Create junction fingers and add them to some SIS layer.
        Choose 'SIS_junction' layer by default but 'SIS_junction_2' if ``separate_junctions`` is True.
        """
        hook_under_pts =[
            pya.DPoint(self.hook_width / 2 - self.hook_lead_thickness, self.bridge_gap / 2 + self.hook_thickness),
            pya.DPoint(- self.hook_width / 2, self.bridge_gap / 2 + self.hook_thickness),
            pya.DPoint(- self.hook_width / 2, self.bridge_gap / 2 + self.hook_thickness + self.hook_undercut),
            pya.DPoint(self.hook_width / 2 - self.hook_lead_thickness, self.bridge_gap / 2 + self.hook_thickness + self.hook_undercut),
        ]
        hook_under_pts1 = [
            pya.DPoint( self.taper_width/2, (self.pad_to_pad_separation / 2)),
            pya.DPoint( self.hook_width/2, (self.pad_to_pad_separation / 2 - 1)),
            pya.DPoint( self.hook_width/2, (self.pad_to_pad_separation / 2 - 1)- 0.3),
            pya.DPoint( self.hook_width/2 + 0.3, (self.pad_to_pad_separation / 2 - 1) - 0.3),
            pya.DPoint( self.hook_width/2 + 0.3, (self.pad_to_pad_separation / 2 - 1)),
            pya.DPoint( self.taper_width/2 + 0.3, (self.pad_to_pad_separation / 2) ),
        ]
        hook_under_pts2 = [
            pya.DPoint( -self.taper_width/2, (self.pad_to_pad_separation / 2)),
            pya.DPoint( -self.hook_thickness/2, (self.pad_to_pad_separation / 2 - 1)),
            pya.DPoint( -self.hook_thickness/2 - 0.3, (self.pad_to_pad_separation / 2 - 1)),
            pya.DPoint(self.hook_width / 2 - 0.2, (self.pad_to_pad_separation / 2 - 1 )),
            pya.DPoint(self.hook_width / 2 - 0.2, (self.pad_to_pad_separation / 2 - 1.3 )),
            pya.DPoint( -self.hook_thickness/2, (self.pad_to_pad_separation / 2 - 1.3)),
            pya.DPoint( -self.taper_width/2 - 0.3, (self.pad_to_pad_separation / 2) ),
        ]

        finger_under_pts1 = [
            pya.DPoint( - self.taper_width/2, - (self.pad_to_pad_separation / 2)),
            pya.DPoint( - 0.1, - (self.pad_to_pad_separation / 2 - 1)),
            pya.DPoint( - 0.1, - (self.pad_to_pad_separation / 2 - 1) + 0.3),
            pya.DPoint( - self.taper_width/2, - (self.pad_to_pad_separation / 2) + 0.3),
        ]
        finger_under_pts2 = [
            pya.DPoint( self.taper_width/2, - (self.pad_to_pad_separation / 2)),
            pya.DPoint( 0.1, - (self.pad_to_pad_separation / 2 - 1)),
            pya.DPoint( 0.1, - (self.pad_to_pad_separation / 2 - 1) + 0.3),
            pya.DPoint( self.taper_width/2, - (self.pad_to_pad_separation / 2) + 0.3),
        ]

        finger_under_pts3 = [
            pya.DPoint( - self.finger_width / 2, - self.bridge_gap / 2 - 0.1),
            pya.DPoint( - self.finger_width / 2, - self.bridge_gap / 2),
            pya.DPoint( self.finger_width / 2, - self.bridge_gap / 2),
            pya.DPoint( self.finger_width / 2, - self.bridge_gap / 2 - 0.1),
            pya.DPoint(self.hook_width / 2, - self.bridge_gap / 2 - 0.1),
            pya.DPoint(self.hook_width / 2, self.bridge_gap / 2),
            pya.DPoint(- self.hook_width / 2, self.bridge_gap / 2),
            pya.DPoint(- self.hook_width / 2, - self.bridge_gap / 2 - 0.1),

        ]

        hook_pts = [
            pya.DPoint(self.hook_width / 2 - self.hook_lead_thickness, self.bridge_gap / 2 + self.hook_thickness),
            pya.DPoint(- self.hook_width / 2, self.bridge_gap / 2 + self.hook_thickness),
            pya.DPoint(- self.hook_width / 2, self.bridge_gap / 2),
            pya.DPoint(self.hook_width / 2, self.bridge_gap / 2),
            pya.DPoint(self.hook_width / 2, (self.pad_to_pad_separation / 2 - 1)),

            pya.DPoint(self.taper_width / 2, self.pad_to_pad_separation / 2),
            pya.DPoint(self.taper_width / 2, self.pad_to_pad_separation / 2 + self.pad_offset + 1),
            pya.DPoint(- self.taper_width / 2, self.pad_to_pad_separation / 2 + self.pad_offset + 1),
            pya.DPoint(- self.taper_width / 2, self.pad_to_pad_separation / 2),
            pya.DPoint(- self.hook_thickness / 2, (self.pad_to_pad_separation / 2 - 1)),
            
            pya.DPoint(self.hook_width / 2 - 0.2, (self.pad_to_pad_separation / 2 - 1 )),
            pya.DPoint(self.hook_width / 2 - 0.2, self.bridge_gap / 2 + self.hook_thickness  + 1 ),
            pya.DPoint(self.hook_width / 2 - self.hook_lead_thickness, self.bridge_gap / 2 + self.hook_thickness  + 1 ),
        ]

        finger_pts = [
            pya.DPoint( - self.finger_width / 2, - self.bridge_gap / 2),
            pya.DPoint( self.finger_width / 2, - self.bridge_gap / 2),
            pya.DPoint( self.finger_width / 2, - self.bridge_gap / 2 - 1),

            pya.DPoint( 0.1, - self.bridge_gap / 2 - 1),
            pya.DPoint( 0.1, - (self.pad_to_pad_separation / 2 - 1)),

            pya.DPoint( self.taper_width / 2, - self.pad_to_pad_separation / 2),
            pya.DPoint(self.taper_width / 2, - self.pad_to_pad_separation / 2 - self.pad_offset - 1),
            pya.DPoint(- self.taper_width / 2, - self.pad_to_pad_separation / 2 - self.pad_offset - 1),
            pya.DPoint( - self.taper_width / 2, - self.pad_to_pad_separation / 2),
            
            pya.DPoint( - 0.1, - (self.pad_to_pad_separation / 2 - 1)),
            pya.DPoint( - 0.1, - self.bridge_gap / 2 - 1),
            pya.DPoint( - self.finger_width / 2, - self.bridge_gap / 2 - 1),
            
        ]

        junction_shapes = [ pya.DPolygon(hook_pts).to_itype(self.layout.dbu), pya.DPolygon(finger_pts).to_itype(self.layout.dbu)]
        self._add_shapes(junction_shapes, "SIS_junction")
        
        under_pts = [hook_under_pts, finger_under_pts1, finger_under_pts2, finger_under_pts3,
                     hook_under_pts1, hook_under_pts2]

        undercut_shapes = [pya.DPolygon(pts).to_itype(self.layout.dbu) for pts in under_pts]
        self._add_shapes(undercut_shapes, "SIS_shadow")
        
    def _make_squid_junction(self): #, top_corner, b_corner_y, finger_margin=0):
        """Modified to reduce SQUID linear inductance. 
        Create junction fingers and add them to some SIS layer.
        Choose 'SIS_junction' layer by default but 'SIS_junction_2' if ``separate_junctions`` is True.
        """
        shift_hook = self.hook_width / 2

        hook_under_pts =[
            pya.DPoint(shift_hook + - self.taper_width / 2, self.bridge_gap / 2 + self.hook_thickness),
            pya.DPoint(shift_hook + - self.taper_width / 2 - self.hook_width, self.bridge_gap / 2 + self.hook_thickness),
            pya.DPoint(shift_hook + - self.taper_width / 2 - self.hook_width, self.bridge_gap / 2 + self.hook_thickness + self.hook_undercut),
            pya.DPoint(shift_hook + - self.taper_width / 2, self.bridge_gap / 2 + self.hook_thickness + self.hook_undercut),
        ]
        hook_under_pts1 = [
            pya.DPoint( self.taper_width/2, (self.pad_to_pad_separation / 2)),
            pya.DPoint( self.hook_width/2, (self.pad_to_pad_separation / 2 - 1)),
            pya.DPoint( self.hook_width/2, (self.pad_to_pad_separation / 2 - 1)- 0.3),
            pya.DPoint( self.hook_width/2 + 0.3, (self.pad_to_pad_separation / 2 - 1) - 0.3),
            pya.DPoint( self.hook_width/2 + 0.3, (self.pad_to_pad_separation / 2 - 1)),
            pya.DPoint( self.taper_width/2 + 0.3, (self.pad_to_pad_separation / 2) ),
        ]
        hook_under_pts2 = [
            pya.DPoint( -self.taper_width/2, (self.pad_to_pad_separation / 2)),
            pya.DPoint( -self.hook_thickness/2, (self.pad_to_pad_separation / 2 - 1)),
            pya.DPoint( -self.hook_thickness/2 - 0.3, (self.pad_to_pad_separation / 2 - 1)),
            pya.DPoint(self.hook_width / 2 - 0.2, (self.pad_to_pad_separation / 2 - 1 )),
            pya.DPoint(self.hook_width / 2 - 0.2, (self.pad_to_pad_separation / 2 - 1.3 )),
            pya.DPoint( -self.hook_thickness/2, (self.pad_to_pad_separation / 2 - 1.3)),
            pya.DPoint( -self.taper_width/2 - 0.3, (self.pad_to_pad_separation / 2) ),
        ]

        finger_under_pts1 = [
            pya.DPoint( - self.taper_width/2, - (self.pad_to_pad_separation / 2)),
            pya.DPoint( - 0.1, - (self.pad_to_pad_separation / 2 - 1)),
            pya.DPoint( - 0.1, - (self.pad_to_pad_separation / 2 - 1) + 0.3),
            pya.DPoint( - self.taper_width/2, - (self.pad_to_pad_separation / 2) + 0.3),
        ]
        finger_under_pts2 = [
            pya.DPoint( self.taper_width/2, - (self.pad_to_pad_separation / 2)),
            pya.DPoint( 0.1, - (self.pad_to_pad_separation / 2 - 1)),
            pya.DPoint( 0.1, - (self.pad_to_pad_separation / 2 - 1) + 0.3),
            pya.DPoint( self.taper_width/2, - (self.pad_to_pad_separation / 2) + 0.3),
        ]

        
        shift_finger = - self.taper_width / 2
        finger_under_pts3 = [
            pya.DPoint(shift_finger - self.finger_width / 2, - self.bridge_gap / 2 - 0.1),
            pya.DPoint(shift_finger - self.finger_width / 2, - self.bridge_gap / 2),
            pya.DPoint(shift_finger + self.finger_width / 2, - self.bridge_gap / 2),
            pya.DPoint(shift_finger + self.finger_width / 2, - self.bridge_gap / 2 - 0.1),
            pya.DPoint(shift_finger + self.hook_width / 2, - self.bridge_gap / 2 - 0.1),
            pya.DPoint(shift_finger + self.hook_width / 2, self.bridge_gap / 2),
            pya.DPoint(shift_finger - self.hook_width / 2, self.bridge_gap / 2),
            pya.DPoint(shift_finger - self.hook_width / 2, - self.bridge_gap / 2 - 0.1),
        ]
        hook_pts = [
            pya.DPoint(shift_hook + - self.taper_width / 2 , self.bridge_gap / 2 + self.hook_thickness),
            pya.DPoint(shift_hook + - self.taper_width / 2 - self.hook_width, self.bridge_gap / 2 + self.hook_thickness),
            pya.DPoint(shift_hook + - self.taper_width / 2 - self.hook_width, self.bridge_gap / 2),
            pya.DPoint(shift_hook + self.taper_width / 2, self.bridge_gap / 2),
            pya.DPoint(shift_hook + self.taper_width / 2, self.pad_to_pad_separation / 2),
            pya.DPoint(shift_hook + self.taper_width / 2, self.pad_to_pad_separation / 2 + self.pad_offset + 1),
            pya.DPoint(shift_hook + - self.taper_width / 2, self.pad_to_pad_separation / 2 + self.pad_offset + 1),
            pya.DPoint(shift_hook + - self.taper_width / 2, self.pad_to_pad_separation / 2),
        ]

        finger_pts = [
            pya.DPoint(shift_finger - self.finger_width / 2, - self.bridge_gap / 2),
            pya.DPoint(shift_finger + self.finger_width / 2, - self.bridge_gap / 2),
            pya.DPoint(shift_finger + self.finger_width / 2, - self.pad_to_pad_separation / 2 - self.pad_offset - 1),
            pya.DPoint(shift_finger - self.finger_width / 2, - self.pad_to_pad_separation / 2 - self.pad_offset - 1),           
        ]

        junction_shapes = [ pya.DPolygon(hook_pts).to_itype(self.layout.dbu), pya.DPolygon(finger_pts).to_itype(self.layout.dbu)]
        self._add_shapes(junction_shapes, "SIS_junction")
        
        under_pts = [hook_under_pts, finger_under_pts3] #, finger_under_pts1, finger_under_pts2, hook_under_pts1, hook_under_pts2]

        undercut_shapes = [pya.DPolygon(pts).to_itype(self.layout.dbu) for pts in under_pts]
        self._add_shapes(undercut_shapes, "SIS_shadow")

    def _add_shapes(self, shapes, layer):
        """Merge shapes into a region and add it to layer."""
        region = pya.Region(shapes).merged()
        self.cell.shapes(self.get_layer(layer)).insert(region)

    def _add_refpoints(self):
        """Adds the "origin_squid" refpoint and port "common"."""
        self.refpoints["origin_squid"] = pya.DPoint(0, 0)
        self.add_port("common", pya.DPoint(0, 0))

    def _produce_ground_metal_shapes(self):
        """Produces hardcoded shapes in metal gap and metal addition layers."""
        # metal additions bottom

        if self.noSQUID:
            x0 = self.taper_width / 2
            y0 = - self.pad_to_pad_separation / 2
            shift_finger = 0
        else:
            x0 = self.finger_width / 2
            y0 = - self.pad_to_pad_separation / 2
            shift_finger = - self.taper_width / 2
            
        bottom_pts = [
            pya.DPoint(5, - self.metal_height/2),
            pya.DPoint(5, y0),
            pya.DPoint(shift_finger + x0, y0),
            pya.DPoint(shift_finger + x0, y0 - 2),
            pya.DPoint(3, y0 - 2),
            pya.DPoint(3, y0 - 4),
            pya.DPoint(-3, y0 - 4),
            pya.DPoint(-3, y0 - 2),          
            pya.DPoint(shift_finger - x0, y0 - 2),
            pya.DPoint(shift_finger - x0, y0),
            pya.DPoint(-5, y0),
            pya.DPoint(-5, - self.metal_height/2),    
        ]

        if self.include_base_metal_addition:
            bot_shapes = [pya.DPolygon(bottom_pts).to_itype(self.layout.dbu)]
            self._add_shapes(bot_shapes, "base_metal_addition")
            # metal additions top
            if self.noSQUID:
                x0 = self.taper_width / 2
                y0 = self.pad_to_pad_separation / 2
                shift_hook = 0
            else:
                x0 = self.taper_width / 2
                y0 = self.pad_to_pad_separation / 2
                shift_hook = self.hook_width / 2

            top_pts = [
                pya.DPoint(5, self.metal_height / 2),
                pya.DPoint(5, y0),
                pya.DPoint(shift_hook + x0, y0),
                pya.DPoint(shift_hook + x0, y0 + 2),
                pya.DPoint(3, y0 + 2),
                pya.DPoint(3, y0 + 4),
                pya.DPoint(-3, y0 + 4),
                pya.DPoint(-3, y0 + 2),
                pya.DPoint(shift_hook - x0, y0 + 2),
                pya.DPoint(shift_hook - x0, y0),
                pya.DPoint(-5, y0),
                pya.DPoint(-5, self.metal_height / 2),
            ]   

            top_shapes = [pya.DPolygon(top_pts).to_itype(self.layout.dbu)]
            self._add_shapes(top_shapes, "base_metal_addition")

        # metal gap
        if self.include_base_metal_gap:
            if self.include_base_metal_addition:
                pts = bottom_pts + top_pts[::-1]
                shapes = [pya.DPolygon(pts).to_itype(self.layout.dbu)]
                self._add_shapes(shapes, "base_metal_gap_wo_grid")                      
            else:
                pts = [pya.DPoint(-self.width / 2, -self.metal_height/2), pya.DPoint(-self.width / 2, self.metal_height/2)]
                shape = polygon_with_vsym(pts)
                self.cell.shapes(self.get_layer("base_metal_gap_wo_grid")).insert(shape)

    def _produce_ground_grid_avoidance(self):
        """Add ground grid avoidance."""
        w = self.cell.dbbox().width()
        h = self.cell.dbbox().height()
        protection = pya.DBox(-w / 2 - self.margin, -h/2 - self.margin, w / 2 + self.margin, h/2 + self.margin)
        self.cell.shapes(self.get_layer("ground_grid_avoidance")).insert(protection)

    def _round_corners_and_append(self, polygon, polygon_list, rounding_params):
        """Rounds the corners of the polygon, converts it to integer coordinates, and adds it to the polygon list."""
        polygon = polygon.round_corners(rounding_params["rinner"], rounding_params["router"], rounding_params["n"])
        polygon_list.append(polygon.to_itype(self.layout.dbu))
