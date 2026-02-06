# Debug script to analyze ACRL refpoints from simulation JSON
import json
from pathlib import Path

# Read the JSON file
json_file = Path("C:/Roger/KQCircuits/tmp/double_res_acrl_sim_output/double_res_acrl_12000.json")
with open(json_file) as f:
    data = json.load(f)

params = data['parameters']

# Extract relevant parameters
a = params['a']
b = params['b']
feedline_coupling_ground_spacing = params['feedline_coupling_ground_spacing']
ground_cutout_height = params['ground_cutout_height']
l_ground_sep = params['l_ground_sep']
l_width = params['l_width']
cap_wide_height = params['cap_wide_height']
cap_inner_width = params['cap_inner_width']
cap_outer_width = params['cap_outer_width']
cap_wide_gap = params['cap_wide_gap']

# Calculate key geometry positions
ground_gap_top = -(a/2 + b + feedline_coupling_ground_spacing)
ground_gap_bottom = ground_gap_top - ground_cutout_height
cap_region_total_width = cap_inner_width + 2 * cap_outer_width + 2 * cap_wide_gap

print("\n=== Geometry Calculations ===")
print(f"ground_gap_top: {ground_gap_top:.2f}")
print(f"ground_gap_bottom: {ground_gap_bottom:.2f}")
print(f"cap_region_total_width: {cap_region_total_width:.2f}")

# Calculate capacitor positions
cap_bottom = ground_gap_bottom + l_ground_sep - l_width/2
cap_top = cap_bottom + cap_wide_height

print(f"\nCapacitor:")
print(f"  bottom: {cap_bottom:.2f}")
print(f"  top: {cap_top:.2f}")
print(f"  left edge: {-cap_region_total_width/2:.2f}")
print(f"  right edge: {cap_region_total_width/2:.2f}")

# Calculate plate positions
left_plate_right_edge = -cap_region_total_width/2 + cap_outer_width
center_plate_left_edge = -cap_inner_width/2
center_plate_right_edge = cap_inner_width/2
right_plate_left_edge = cap_region_total_width/2 - cap_outer_width

print(f"\nCapacitor plates:")
print(f"  Left plate: x = [{-cap_region_total_width/2:.2f}, {left_plate_right_edge:.2f}]")
print(f"  Center plate: x = [{center_plate_left_edge:.2f}, {center_plate_right_edge:.2f}]")
print(f"  Right plate: x = [{right_plate_left_edge:.2f}, {cap_region_total_width/2:.2f}]")
print(f"  Bias lead (center to ground): x = 0, y = [{cap_bottom:.2f}, {ground_gap_bottom:.2f}]")

# Get ACRL refpoints from JSON
acrl_locs = params['extra_json_data']['acrl_port_locations']
net_names = params['extra_json_data']['net_names']

print("\n=== ACRL Port Locations from JSON ===")
for net_num, locations in acrl_locs.items():
    net_name = net_names[net_num]
    source = locations['source']
    sink = locations['sink']
    print(f"\nNet {net_num} ({net_name}):")
    print(f"  Source: ({source[0]:.2f}, {source[1]:.2f}, {source[2]:.2f})")
    print(f"  Sink:   ({sink[0]:.2f}, {sink[1]:.2f}, {sink[2]:.2f})")

# Analyze where these points land
print("\n=== ACRL Refpoint Analysis ===")
for net_num, locations in acrl_locs.items():
    net_name = net_names[net_num]
    source = locations['source']
    sink = locations['sink']

    print(f"\nNet {net_num} ({net_name}):")
    print(f"  Source at ({source[0]:.2f}, {source[1]:.2f}):")

    # Check which plate the source is on
    if -cap_region_total_width/2 <= source[0] <= left_plate_right_edge:
        print(f"    → On LEFT capacitor plate")
    elif center_plate_left_edge <= source[0] <= center_plate_right_edge:
        print(f"    → On CENTER capacitor plate")
    elif right_plate_left_edge <= source[0] <= cap_region_total_width/2:
        print(f"    → On RIGHT capacitor plate")
    else:
        print(f"    → OUTSIDE capacitor region!")

    print(f"  Sink at ({sink[0]:.2f}, {sink[1]:.2f}):")

    # Check which plate the sink is on
    if -cap_region_total_width/2 <= sink[0] <= left_plate_right_edge:
        print(f"    → On LEFT capacitor plate")
    elif center_plate_left_edge <= sink[0] <= center_plate_right_edge:
        print(f"    → On CENTER capacitor plate (or bias lead)")
    elif right_plate_left_edge <= sink[0] <= cap_region_total_width/2:
        print(f"    → On RIGHT capacitor plate")
    else:
        print(f"    → OUTSIDE capacitor region!")

print("\n=== Electrical Connectivity Analysis ===")
print("The double_res structure topology:")
print("  1. Left inductor connects to LEFT capacitor plate")
print("  2. Right inductor connects to RIGHT capacitor plate")
print("  3. Left and right inductors are CONTINUOUS (connected at top)")
print("  4. Center capacitor plate connects to GROUND via bias lead")
print("  5. Capacitor plates are SEPARATED by gaps (not electrically connected)")
print("\nFor ACRL measurement to work without duplicate net error:")
print("  - Source and sink must be on DIFFERENT electrical nets")
print("  - Since inductors form a continuous loop, both inductor connection")
print("    points are on the SAME net")
print("  - The center plate (via bias lead) connects to ground")
print("\nPROBLEM: Current refpoints place:")
print(f"  - Source on LEFT inductor/left plate (floating net)")
print(f"  - Sink on bias lead/center plate (ground net)")
print("\nThis should work IF:")
print("  - The left and right inductor/plate combinations are isolated")
print("  - The center plate is grounded")
print("But the inductor forms a CONTINUOUS loop, so left and right are SAME net!")
