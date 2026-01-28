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
"""
Produces capacitance, inductance, and resistance matrix tables from Ansys or Elmer results

This script handles ACRL (AC Resistance and Inductance) simulation results in addition to standard
capacitance matrix results. It produces separate CSV tables for C, L, and R matrices when available.

Produces deembed capacitances if `deembed_cross_sections` is set in the simulations class and corresponding
cross-section simulation results are found.
"""

import os
from post_process_helpers import find_varied_parameters, tabulate_into_csv, load_json


def _get_excitations(json_data):
    return {l["excitation"] for l in json_data["layers"].values() if l.get("excitation", 0) > 0}


def _get_matrix_label(matrix_type, i, j, net_names):
    """Generate matrix element label with descriptive net names.

    Args:
        matrix_type: "C", "L", or "R"
        i, j: Matrix indices (0-based)
        net_names: Dictionary mapping port numbers (1-based) to net names

    Returns:
        String label like "L_feedline" (self) or "L_feedline_inductor" (mutual)
    """
    # Convert to 1-based port numbers
    port_i = i + 1
    port_j = j + 1

    # Use net names if available, otherwise fall back to numbers
    if net_names and port_i in net_names and port_j in net_names:
        name_i = net_names[port_i]
        name_j = net_names[port_j]

        if i == j:
            # Self-inductance/capacitance/resistance
            return f"{matrix_type}_{name_i}"
        else:
            # Mutual inductance/capacitance/resistance
            return f"{matrix_type}_{name_i}_{name_j}"
    else:
        # Fall back to numbered labels
        return f"{matrix_type}{port_i}{port_j}"


# Find data files
path = os.path.curdir
result_files = [f for f in os.listdir(path) if f.endswith("_project_results.json")]
if result_files:
    # Find parameters that are swept
    definition_files = [f.replace("_project_results.json", ".json") for f in result_files]
    parameters, parameter_values = find_varied_parameters(definition_files)

    # Load net name mappings from definition files
    net_names_map = {}
    for key, def_file in zip(parameter_values.keys(), definition_files):
        def_data = load_json(def_file)
        net_names = def_data.get("parameters", {}).get("extra_json_data", {}).get("net_names", {})
        if net_names:
            # Convert string keys to int keys and store
            net_names_map[key] = {int(k): v for k, v in net_names.items()}

    # Load result data
    cmatrix = {}
    lmatrix = {}
    rmatrix = {}
    has_capacitance = False
    has_inductance = False
    has_resistance = False

    for key, result_file in zip(parameter_values.keys(), result_files):
        result = load_json(result_file)

        # Helper function to check if matrix data is valid (not all NaN)
        def is_valid_matrix(matrix_data):
            """Check if matrix contains valid numeric data (not NaN/None)"""
            if matrix_data is None:
                return False
            try:
                # Flatten the matrix and check if any values are valid numbers
                import math
                for row in matrix_data:
                    for val in (row if isinstance(row, list) else [row]):
                        if val is not None and not (isinstance(val, float) and math.isnan(val)):
                            return True
                return False
            except (TypeError, AttributeError):
                return False

        # Get net names for this simulation (if available)
        net_names = net_names_map.get(key, {})

        # Extract capacitance matrix (if present and valid - not available in ACRL mode)
        cdata = result.get("CMatrix") or result.get("Cs")
        if is_valid_matrix(cdata):
            has_capacitance = True
            cmatrix[key] = {
                _get_matrix_label("C", i, j, net_names): c
                for i, l in enumerate(cdata) for j, c in enumerate(l)
            }

        # Extract inductance matrix if ACRL was enabled
        ldata = result.get("LMatrix") or result.get("Ls")
        if is_valid_matrix(ldata):
            has_inductance = True
            lmatrix[key] = {
                _get_matrix_label("L", i, j, net_names): l
                for i, l_row in enumerate(ldata) for j, l in enumerate(l_row)
            }

        # Extract resistance matrix if ACRL was enabled
        rdata = result.get("RMatrix") or result.get("Rs")
        if is_valid_matrix(rdata):
            has_resistance = True
            rmatrix[key] = {
                _get_matrix_label("R", i, j, net_names): r
                for i, r_row in enumerate(rdata) for j, r in enumerate(r_row)
            }

    # Deembedding (currently only for capacitance)
    # Skip deembedding if no capacitance data available (e.g., ACRL mode)
    try:
        if not has_capacitance or not cmatrix:
            raise ValueError("Skipping deembedding - no capacitance data available")

        def_data_cs = {}
        def_data_3d = {}
        for key, def_file in zip(parameter_values.keys(), definition_files):
            data = load_json(def_file)
            (def_data_cs if data.get("tool") == "cross-section" else def_data_3d)[key] = data

        for key, def_data in def_data_3d.items():
            for port in def_data.get("ports", []):
                d_len, d_cross_section = 1e-6 * port.get("deembed_len", 0), port.get("deembed_cross_section")
                if d_len and d_cross_section:
                    cs_key = f"{key}_{d_cross_section}"
                    if cs_key not in def_data_cs:
                        print(f"WARNING: deembed cross section not found {cs_key}")
                        continue
                    exc_set = _get_excitations(def_data_cs[cs_key])
                    if len(exc_set) > 1:
                        print(f"WARNING: Multiple signals in deembedding cross section {cs_key}")
                        continue
                    exc = exc_set.pop()
                    deembed_key = f"C{exc}{exc}_deembed"
                    deembed_c = d_len * cmatrix[cs_key]["C11"]
                    cmatrix[key][deembed_key] = cmatrix[key].get(deembed_key, 0) + deembed_c
                    cmatrix[key][f"C{exc}{exc}"] -= deembed_c

    except Exception as e:  # pylint: disable=broad-except
        print(f"Encountered exception in capacitance deembedding\n {e}")

    # Output results to CSV tables
    output_basename = os.path.basename(os.path.abspath(path))

    # Output capacitance matrix if present (not available in ACRL mode)
    if has_capacitance and cmatrix:
        tabulate_into_csv(f"{output_basename}_cmatrix_results.csv", cmatrix, parameters, parameter_values)
        print(f"Capacitance matrix table created: {output_basename}_cmatrix_results.csv")

    # Output inductance matrix if ACRL was used
    if has_inductance and lmatrix:
        tabulate_into_csv(f"{output_basename}_lmatrix_results.csv", lmatrix, parameters, parameter_values)
        print(f"Inductance matrix table created: {output_basename}_lmatrix_results.csv")

    # Output resistance matrix if ACRL was used
    if has_resistance and rmatrix:
        tabulate_into_csv(f"{output_basename}_rmatrix_results.csv", rmatrix, parameters, parameter_values)
        print(f"Resistance matrix table created: {output_basename}_rmatrix_results.csv")
