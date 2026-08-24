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

"""Demo mask."""

from pathlib import Path
import os

from kqcircuits.chips.chip import Chip
from kqcircuits.chips.junction_hook_test_chip import JunctionHookTestChip
from kqcircuits.chips.junction_bridge_test_chip import JunctionBridgeTestChip
from kqcircuits.chips.blank_chip import BlankChip
from kqcircuits.masks.mask_set import MaskSet
from kqcircuits.masks.mask_export import get_mask_layout_full_name
from kqcircuits.elements.alignment_markers import AlignmentMarkers
from kqcircuits.elements.alignment_pomeroy_global import AlignmentPomeroyGlobal
from kqcircuits.defaults import TMP_PATH, default_faces
from kqcircuits.util.library_helper import load_libraries
from kqcircuits.util.load_save_layout import save_layout, load_layout
from kqcircuits.pya_resolver import pya

# Load libraries at module level so worker processes also have them
load_libraries(path="elements")
load_libraries(path="test_structures")

if __name__ == "__main__":
    mdemo = MaskSet(
        name="JunctionTest1",
        version=6,
        with_grid=False,
        mask_export_layers=["base_metal_gap_wo_grid", "SIS_junction",  "SIS_shadow", "chip_dicing"],
        export_path=TMP_PATH,
        name_date="260805",  # <-- date/version label on every chip; update each run
        #chip_copy_label_layers=["base_metal_gap", "base_metal_gap_wo_grid", "base_metal_gap_for_EBL", "SIS_junction"],
    )

    layers_to_mask = {"base_metal_gap_wo_grid": "1"}

    """# Bottom face (1t1) mask
    mdemo.add_mask_layout(
        [
            ["---", "---", "---", "---", "---", "---", "---", "---", "---", "---", "---", "---"],
            ["---", "---", "---", "BR2", "LR2", "BR2", "DR",  "BR2", "LR2",  "---", "---", "---"],
            ["---", "---", "BR2", "LR2", "BR2", "DR",  "BR2", "LR2", "BR2", "DR",  "BR2", "LR2", "BR2", "---", "---"],
            ["---", "---", "BR2", "LR2", "BR2", "DR",  "BR2", "LR2", "BR2", "DR",  "BR2", "LR2", "BR2", "---", "---"],
            ["---", "BR2", "LR2", "BR2", "DR",  "BR2", "LR2", "BR2", "DR",  "BR2", "LR2", "BR2", "DR",  "BR2", "---"],
            ["---", "BR2", "LR2", "BR2", "DR",  "BR2", "LR2", "BR2", "DR",  "BR2", "LR2", "BR2", "DR",  "BR2", "---"],
            ["---", "BR2", "LR2", "BR2", "DR",  "BR2", "LR2", "BR2", "DR",  "BR2", "LR2", "BR2", "DR",  "BR2", "---"],
            ["---", "BR2", "LR2", "BR2", "DR",  "BR2", "LR2", "BR2", "DR",  "BR2", "LR2", "BR2", "DR",  "BR2", "---"],
            ["---", "BR2", "LR2", "BR2", "DR",  "BR2", "LR2", "BR2", "DR",  "BR2", "LR2", "BR2", "DR",  "BR2", "---"],
            ["---", "---", "---", "---", "---", "---", "---", "---", "---", "---", "---", "---", "---", "---", "---"],
        ],
        "1t1",
        layers_to_mask=layers_to_mask,
        mask_markers_dict={},
    )"""
    
    """# Bottom face (1t1) mask
    mdemo.add_mask_layout(
        [
            ["---", "---",   "FLER",  "FMET",  "FLER",  "FMETR", "FLER",   "---",  "---"],
            ["---", "FMETR", "FLER",  "FMET",  "FLER",  "FMETR",  "FLER",  "FMET",  "---"],
            ["---", "FLER",  "FMETR", "FLER",  "FMET",  "FLER",  "FMETR",  "FLER",  "---"],
            ["---", "FMETR", "FLER",  "FMET",  "FLER",  "FMETR", "FLER",  "FMET",  "---"],
            ["---", "FLER",  "FMETR", "FLER",  "FMET",  "FLER",  "FMETR",  "FLER",  "---"],
            ["---", "FMETR", "FLER",  "FMET",  "FLER",  "FMETR", "FLER",  "FMET",  "---"],
            ["---", "FLER",  "FMETR", "FLER",  "FMET",  "FLER",  "FMETR",  "FLER",  "---"],
            ["---", "---",   "FLER", "FMETR",  "FMET",  "FLER",  "FMETR",   "---",  "---"],
        ],
        "1t1",
        layers_to_mask=layers_to_mask,
        mask_markers_dict={},
        mask_name_label=False,
        center_on_wafer=True,
        covered_region_excluded_layers=["base_metal_gap_wo_grid"],
        wafer_outline_in_dicing=True,
        wafer_bottom_flat_length=22000,
        edge_clearance=100,
        chip_trans=pya.DTrans().R90,
    )"""

    # Bottom face (1t1) mask
    """[
            ["---", "--",   "BK",   "BK",   "BK",   "BK",   "BK",   "--",  "---"],
            ["---", "BK",   "JB",   "BK",   "BK",   "BK",   "JB",   "BK",  "---"],
            ["---", "BK",   "BK",   "BK",   "BK",   "BK",   "BK",   "BK",  "---"],
            ["---", "BK",   "JB",   "BK",   "BK",   "BK",   "JB",   "BK",  "---"],
            ["---", "BK",   "BK",   "BK",   "BK",   "BK",   "BK",   "BK",  "---"],
            #["---", "BK",   "BK",   "BK",   "BK",   "BK",   "BK",   "BK",  "---"],
            ["---", "BK",   "JB",   "BK",   "BK",   "BK",   "JB",   "BK",  "---"],
            ["---", "--",   "BK",   "BK",   "BK",   "BK",   "BK",   "--",  "---"],
        ],"""
    mdemo.add_mask_layout(
            [
            ["---", "--",   "JH",   "JB",   "BK",   "JH",   "JB",   "--",  "---"],
            ["---", "BK",   "JB",   "JR",   "BK",   "JB",   "JR",   "BK",  "---"],
            ["---", "BK",   "BK",   "BK",   "BK",   "BK",   "BK",   "BK",  "---"],
            ["---", "BK",   "JH",   "JB",   "BK",   "JH",   "JB",   "BK",  "---"],
            ["---", "BK",   "JB",   "JR",   "BK",   "JB",   "JR",   "BK",  "---"],
            ["---", "BK",   "BK",   "BK",   "BK",   "BK",   "BK",   "BK",  "---"],
            ["---", "BK",   "JH",   "JB",   "BK",   "JH",   "JB",   "BK",  "---"],
            ["---", "--",   "JB",   "JR",   "BK",   "JB",   "JR",   "--",  "---"],
        ],
        "1t1",
        layers_to_mask=layers_to_mask,
        mask_markers_dict={},
        mask_name_label=False,
        center_on_wafer=True,
        covered_region_excluded_layers=["base_metal_gap_wo_grid"],
        wafer_outline_in_dicing=True,
        wafer_bottom_flat_length=22000,
        edge_clearance=100,
        chip_trans=pya.DTrans().R90,
        square_in_dicing=True,
    )

    # chip definitions
    mdemo.add_chip(
        [
            (BlankChip, "BK"),
            (JunctionHookTestChip, "JH", {"label_sis_junction": True, "label_text": "260805"}),
            (JunctionBridgeTestChip, "JB", {"label_sis_junction": True, "label_text": "260805"}),
            (JunctionBridgeTestChip, "JR", {"label_sis_junction": True, "label_text": "260805", "rotate_junctions_180": True}),
        ]
    )

    for mask_layout in mdemo.mask_layouts:
        if mask_layout.face_id == "1t1":
            am_cell = AlignmentMarkers.create(mask_layout.layout, face_ids=["1t1"])
            mask_layout.top_cell.insert(pya.DCellInstArray(am_cell.cell_index(), pya.DTrans()))


    mdemo.build()
    mdemo.export()

