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

from kqcircuits.chips.chip import Chip
from kqcircuits.chips.blank_chip import BlankChip
from kqcircuits.masks.mask_set import MaskSet
from kqcircuits.defaults import TMP_PATH
from kqcircuits.util.library_helper import load_libraries

# Load libraries at module level so worker processes also have them
load_libraries(path="elements")
load_libraries(path="test_structures")

if __name__ == "__main__":
    mdemo = MaskSet(
        name="blank1",
        version=1,
        with_grid=False,
        mask_export_layers=["base_metal_gap_wo_grid"],
        export_path=TMP_PATH,
    )

    layers_to_mask = {"base_metal_gap_wo_grid": "1"}
    
    # Bottom face (1t1) mask
    mdemo.add_mask_layout(
        [
            ["---", "---", "---", "---", "---", "---", "---", "---", "---", "---"],
            ["---", "---", "BK",  "BK",  "BK",  "BK",  "BK",  "BK",  "---", "---"],
            ["---", "BK",  "BK",  "BK",  "BK",  "BK",  "BK",  "BK",  "BK",  "---"],
            ["---", "BK",  "BK",  "BK",  "BK",  "BK",  "BK",  "BK",  "BK",  "---"],
            ["---", "BK",  "BK",  "BK",  "BK",  "BK",  "BK",  "BK",  "BK",  "---"],
            ["---", "BK",  "BK",  "BK",  "BK",  "BK",  "BK",  "BK",  "BK",  "---"],
            ["---", "BK",  "BK",  "BK",  "BK",  "BK",  "BK",  "BK",  "BK",  "---"],
            ["---", "---", "BK",  "BK",  "BK",  "BK",  "BK",  "BK",  "---", "---"],
            ["---", "---", "---", "---", "---", "---", "---", "---", "---", "---"],
        ],
        "1t1",
        layers_to_mask=layers_to_mask,
        mask_markers_dict={},
        mask_name_label=False,
        center_on_wafer=True, 
        covered_region_excluded_layers=["base_metal_gap_wo_grid"],
        wafer_outline_in_dicing=True,
        wafer_bottom_flat_length=22000,
        edge_clearance=100
    )

    # chip definitions
    mdemo.add_chip(
        [
            (BlankChip, "BK"),
        ]
    )

    mdemo.build()
    mdemo.export()
