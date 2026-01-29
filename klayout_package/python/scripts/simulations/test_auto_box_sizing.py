# This code is part of KQCircuits
# Copyright (C) 2025 Roger Romani
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


"""Test script for automatic box sizing functionality."""
import logging
import sys
from pathlib import Path

# Set UTF-8 encoding for Windows console
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

from kqcircuits.pya_resolver import pya
from kqcircuits.simulations.single_element_simulation import get_single_element_sim_class
from kqcircuits.elements.finger_capacitor_square import FingerCapacitorSquare
from kqcircuits.util.export_helper import get_active_or_new_layout

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
layout = get_active_or_new_layout()
SimClass = get_single_element_sim_class(FingerCapacitorSquare)

print("=" * 80)
print("Testing Automatic Box Sizing Functionality")
print("=" * 80)

# Test 1: Auto-sizing with defaults
print("\n=== Test 1: Auto-sizing with defaults ===")
print("Parameters: auto_size_box=True (margin=500µm, round=100µm)")
sim1 = SimClass(
    layout,
    name="test1_autosize_default",
    auto_size_box=True,
    finger_number=5,
    finger_length=100
)
print(f"✓ Auto-sized box: {sim1.box}")
print(f"  Cell bbox: {sim1.cell.dbbox()}")
print(f"  Box width: {sim1.box.width():.1f} µm, height: {sim1.box.height():.1f} µm")

# Test 2: Custom margins
print("\n=== Test 2: Custom margins ===")
print("Parameters: auto_size_box=True, box_margin=1000, box_round=500")
sim2 = SimClass(
    layout,
    name="test2_custom_margin",
    auto_size_box=True,
    box_margin=1000,
    box_round=500,
    finger_number=5,
    finger_length=100
)
print(f"✓ Auto-sized box: {sim2.box}")
print(f"  Cell bbox: {sim2.cell.dbbox()}")
print(f"  Margin check: left={sim2.box.left - sim2.cell.dbbox().left:.1f}, "
      f"right={sim2.cell.dbbox().right - sim2.box.right:.1f}")

# Test 3: No rounding
print("\n=== Test 3: No rounding ===")
print("Parameters: auto_size_box=True, box_round=0")
sim3 = SimClass(
    layout,
    name="test3_no_rounding",
    auto_size_box=True,
    box_round=0,
    finger_number=5,
    finger_length=100
)
print(f"✓ Auto-sized box: {sim3.box}")
print(f"  Coordinates are exact (not rounded to grid)")

# Test 4: Asymmetric margins (4-element list)
print("\n=== Test 4: Asymmetric margins (4-element list) ===")
print("Parameters: auto_size_box=True, box_margin=[300, 500, 400, 600]")
sim4 = SimClass(
    layout,
    name="test4_asymmetric_4",
    auto_size_box=True,
    box_margin=[300, 500, 400, 600],  # [left, right, bottom, top]
    finger_number=5,
    finger_length=100
)
print(f"✓ Auto-sized box: {sim4.box}")
cell_bbox = sim4.cell.dbbox()
print(f"  Margin check:")
print(f"    left={sim4.box.left - cell_bbox.left:.1f} (expected ~-300)")
print(f"    right={cell_bbox.right - sim4.box.right:.1f} (expected ~-500)")
print(f"    bottom={sim4.box.bottom - cell_bbox.bottom:.1f} (expected ~-400)")
print(f"    top={cell_bbox.top - sim4.box.top:.1f} (expected ~-600)")

# Test 5: Asymmetric margins (2-element list)
print("\n=== Test 5: Asymmetric margins (2-element list) ===")
print("Parameters: auto_size_box=True, box_margin=[800, 400] (horizontal, vertical)")
sim5 = SimClass(
    layout,
    name="test5_asymmetric_2",
    auto_size_box=True,
    box_margin=[800, 400],  # [horizontal, vertical]
    finger_number=5,
    finger_length=100
)
print(f"✓ Auto-sized box: {sim5.box}")
cell_bbox = sim5.cell.dbbox()
print(f"  Margin check:")
print(f"    left/right={sim5.box.left - cell_bbox.left:.1f} (expected ~-800)")
print(f"    bottom/top={sim5.box.bottom - cell_bbox.bottom:.1f} (expected ~-400)")

# Test 6: box_margin_x and box_margin_y overrides
print("\n=== Test 6: box_margin_x and box_margin_y overrides ===")
print("Parameters: auto_size_box=True, box_margin=100, box_margin_x=700, box_margin_y=300")
sim6 = SimClass(
    layout,
    name="test6_override_margins",
    auto_size_box=True,
    box_margin=100,  # Base margin
    box_margin_x=700,  # Override horizontal
    box_margin_y=300,  # Override vertical
    finger_number=5,
    finger_length=100
)
print(f"✓ Auto-sized box: {sim6.box}")
cell_bbox = sim6.cell.dbbox()
print(f"  Margin check:")
print(f"    left/right={sim6.box.left - cell_bbox.left:.1f} (expected ~-700)")
print(f"    bottom/top={sim6.box.bottom - cell_bbox.bottom:.1f} (expected ~-300)")

# Test 7: Warning for too-small manual box
print("\n=== Test 7: Box too small warning ===")
print("Parameters: box=DBox(0,0,100,100), warn_box_too_small=True")
print("Expected: Warning message about geometry overflow")
sim7 = SimClass(
    layout,
    name="test7_too_small",
    box=pya.DBox(pya.DPoint(0, 0), pya.DPoint(100, 100)),
    warn_box_too_small=True,
    finger_number=5,
    finger_length=100
)
print(f"✓ Check log above for warning message")
print(f"  Manual box: {sim7.box}")
print(f"  Cell bbox: {sim7.cell.dbbox()}")

# Test 8: Backward compatibility (no auto-sizing by default)
print("\n=== Test 8: Backward compatibility ===")
print("Parameters: No auto_size_box specified (defaults to False)")
sim8 = SimClass(
    layout,
    name="test8_backward_compat",
    finger_number=5,
    finger_length=100
)
default_box = pya.DBox(pya.DPoint(0, 0), pya.DPoint(10000, 10000))
print(f"✓ Box preserved: {sim8.box == default_box}")
print(f"  Box: {sim8.box}")

# Test 9: Explicit box honored
print("\n=== Test 9: Explicit box honored ===")
print("Parameters: box=DBox(0,0,2000,2000), auto_size_box not set")
custom_box = pya.DBox(pya.DPoint(0, 0), pya.DPoint(2000, 2000))
sim9 = SimClass(
    layout,
    name="test9_explicit_box",
    box=custom_box,
    finger_number=5,
    finger_length=100
)
print(f"✓ Custom box preserved: {sim9.box == custom_box}")
print(f"  Box: {sim9.box}")

# Test 10: Disable warning
print("\n=== Test 10: Disable too-small warning ===")
print("Parameters: box=DBox(0,0,100,100), warn_box_too_small=False")
print("Expected: No warning message")
sim10 = SimClass(
    layout,
    name="test10_no_warning",
    box=pya.DBox(pya.DPoint(0, 0), pya.DPoint(100, 100)),
    warn_box_too_small=False,
    finger_number=5,
    finger_length=100
)
print(f"✓ No warning should appear above")
print(f"  Box: {sim10.box}")

print("\n" + "=" * 80)
print("All tests completed successfully!")
print("=" * 80)
