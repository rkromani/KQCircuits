from pathlib import Path
from kqcircuits.chips.met_rfs_chip import MetRfsChip
from kqcircuits.chips.met_circle_chip import MetCircleChip
from kqcircuits.chips.blank_chip import BlankChip
from kqcircuits.masks.mask_set import MaskSet
from kqcircuits.defaults import TMP_PATH
from kqcircuits.util.library_helper import load_libraries
from kqcircuits.pya_resolver import pya

load_libraries(path="elements")
load_libraries(path="test_structures")

if __name__ == "__main__":
    mdemo = MaskSet(
        name="DebugCap",
        version=1,
        with_grid=False,
        mask_export_layers=["base_metal_gap_wo_grid"],
        export_path=TMP_PATH,
        name_date="debug",
    )

    layers_to_mask = {"base_metal_gap_wo_grid": "1"}

    mdemo.add_mask_layout(
        [
            ["--", "--",   "--", "--", "--"],
            ["--", "BK",   "MC", "RFSA", "--"],
            ["--", "RFSC", "--", "--", "--"],
            ["--", "--",   "--", "--", "--"],
        ],
        "1t1",
        layers_to_mask=layers_to_mask,
        mask_markers_dict={},
        mask_name_label=False,
        center_on_wafer=True,
        wafer_outline_in_dicing=True,
        wafer_bottom_flat_length=22000,
        edge_clearance=100,
    )

    mdemo.add_chip(
        [
            (BlankChip, "BK"),
            (MetCircleChip, "MC"),
            (MetRfsChip, "RFSA", {"bridge_lengths": [1.0, 2.5, 4.0, 6.0]}),
            (MetRfsChip, "RFSC", {"extra_cap_heights": [0, 93, 186, 279]}),
        ]
    )

    mdemo.build()

    # Inspect the produced RFSC chip cell for the 4 "Met Rfs" instances' bounding box heights
    layout = mdemo.layout
    for cell in layout.each_cell():
        if cell.name.startswith("RFSC"):
            print("Found chip cell:", cell.name)

    # find cells named like Met Rfs / Met Rfs$N as loaded from the exported oas (likely flattened, no pcell)
    for cell in layout.each_cell():
        if "Rfs" in cell.name and cell.name != "Met Rfs Chip":
            bbox = cell.dbbox()
            print(cell.name, "bbox height=", bbox.height(), "is_pcell=", cell.is_pcell_variant())
