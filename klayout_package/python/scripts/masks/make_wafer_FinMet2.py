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

from kqcircuits.chips.chip import Chip
from kqcircuits.chips.fin_met_chip import FinMetChip
from kqcircuits.chips.fin_ler_wide_chip import FinLerWideChip
from kqcircuits.chips.blank_chip import BlankChip
from kqcircuits.masks.mask_set import MaskSet
from kqcircuits.masks.mask_export import get_mask_layout_full_name
from kqcircuits.elements.alignment_markers import AlignmentMarkers
from kqcircuits.defaults import TMP_PATH, default_faces
from kqcircuits.util.library_helper import load_libraries
from kqcircuits.util.load_save_layout import save_layout, load_layout
from kqcircuits.pya_resolver import pya

# Load libraries at module level so worker processes also have them
load_libraries(path="elements")
load_libraries(path="test_structures")

if __name__ == "__main__":
    mdemo = MaskSet(
        name="FinMET2",
        version=1,
        with_grid=False,
        mask_export_layers=["base_metal_gap_wo_grid", "SIS_shadow", "SIS_junction_2", "chip_dicing"],
        export_path=TMP_PATH,
        name_date="260601",  # <-- date/version label on every chip; update each run
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
    mdemo.add_mask_layout(
        [
            ["---", "---",   "FLER",  "FLER",  "FLER",  "FLER",  "FLER",   "---",  "---"],
            ["---", "FLER",  "FLER",  "FLER",  "FLER",  "FLER",  "FLER",  "FLER",  "---"],
            ["---", "FLER",  "FLER",  "FLER",  "FLER",  "FLER",  "FLER",  "FLER",  "---"],
            ["---", "FLER",  "FLER",  "FLER",  "FLER",  "FLER",  "FLER",  "FLER",  "---"],
            ["---", "FLER",  "FLER",  "FLER",  "FLER",  "FLER",  "FLER",  "FLER",  "---"],
            ["---", "FLER",  "FLER",  "FLER",  "FLER",  "FLER",  "FLER",  "FLER",  "---"],
            ["---", "FLER",  "FLER",  "FLER",  "FLER",  "FLER",  "FLER",  "FLER",  "---"],
            ["---", "---",   "FLER",  "FLER",  "FLER",  "FLER",  "FLER",   "---",  "---"],
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
    )

    # chip definitions
    mdemo.add_chip(
        [
            (FinMetChip, "FMET", {"enable_resistance_probe": False}),
            (FinMetChip, "FMETR", {"enable_resistance_probe": True}),  # variant without resistance probe structures
            (FinLerWideChip, "FLER"),
            #(QualityFactor, "BR1", {"n_ab": [1, 2, 3, 4, 5, 6]}),
        ]
    )

    for mask_layout in mdemo.mask_layouts:
        if mask_layout.face_id == "1t1":
            am_cell = AlignmentMarkers.create(mask_layout.layout, face_ids=["1t1"])
            mask_layout.top_cell.insert(pya.DCellInstArray(am_cell.cell_index(), pya.DTrans()))


    mdemo.build()
    mdemo.export()

    # Overlay an external GDS onto the fab_layers output.
    # Layer EXTERNAL_MERGE_LAYER from the external file is merged (boolean OR) into base_metal_gap_wo_grid.
    # All other layers in the external file are appended as-is.
    #EXTERNAL_GDS = Path(r"C:\Users\rkr1\Downloads\260321_FinMET_LERes_Transmon_V3_Teun_rotated.gds")  # <-- set this path
    EXTERNAL_GDS = Path(r"C:\Users\rkr1\Downloads\260514_LERes_Angle_V1_Teun_rotated.gds")  # <-- set this path
    EXTERNAL_MERGE_LAYER = pya.LayerInfo(26, 0)       # layer/datatype to merge into base_metal_gap_wo_grid

    ext_layout = pya.Layout()
    ext_layout.read(str(EXTERNAL_GDS))
    ext_top = ext_layout.top_cells()[0]

    for mask_layout in mdemo.mask_layouts:
        if mask_layout.face_id != "1t1":
            continue
        full_name = get_mask_layout_full_name(mdemo, mask_layout)
        fab_path = mdemo._mask_set_dir / full_name / f"{full_name}-fab_layers.oas"

        fab_layout = pya.Layout()
        load_layout(fab_path, fab_layout)
        fab_top = fab_layout.top_cells()[0]

        # Merge external layer 26 into base_metal_gap_wo_grid
        bmg_layer = fab_layout.layer(default_faces["1t1"]["base_metal_gap_wo_grid"])
        ext_merge_idx = ext_layout.find_layer(EXTERNAL_MERGE_LAYER)
        if ext_merge_idx >= 0:
            fab_top.shapes(bmg_layer).insert(pya.Region(ext_top.begin_shapes_rec(ext_merge_idx)))

        # Append all other external layers as separate layers
        for li in ext_layout.layer_infos():
            if li.layer == EXTERNAL_MERGE_LAYER.layer and li.datatype == EXTERNAL_MERGE_LAYER.datatype:
                continue
            ext_idx = ext_layout.layer(li)
            region = pya.Region(ext_top.begin_shapes_rec(ext_idx))
            if not region.is_empty():
                fab_top.shapes(fab_layout.layer(li)).insert(region)

        save_layout(fab_path, fab_layout, cells=[fab_top])
