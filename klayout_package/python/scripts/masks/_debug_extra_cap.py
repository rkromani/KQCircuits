from kqcircuits.chips.met_rfs_chip import MetRfsChip
from kqcircuits.pya_resolver import pya
from kqcircuits.klayout_view import KLayoutView
from kqcircuits.util.library_helper import load_libraries

load_libraries(path="elements")
load_libraries(path="test_structures")

view = KLayoutView()
layout = view.layout

cell = MetRfsChip.create(layout, extra_cap_heights=[0, 93, 186, 279])
inst = cell.pcell_declaration()
print("extra_cap_heights on chip instance:", cell.pcell_parameters_by_name().get("extra_cap_heights"))

# find the RFS subcells and check their extra_cap_height param
for ci in layout.each_cell():
    if "Met Rfs" in ci.name and ci.is_pcell_variant():
        params = ci.pcell_parameters_by_name()
        print("  ->", ci.name, "met_bridge_length=", params.get("met_bridge_length"), "extra_cap_height=", params.get("extra_cap_height"))
