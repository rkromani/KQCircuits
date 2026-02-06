"""
Automatic Sweep Plotting

Generates plots for parameter sweeps showing results vs design parameters.
"""

import json
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path
from datetime import datetime


def plot_sweep_results(sweep_folder):
    """
    Automatically generate plots for a parameter sweep.

    Args:
        sweep_folder: Path to the sweep folder containing sweep_metadata.json
    """
    sweep_path = Path(sweep_folder)

    # Load sweep metadata
    metadata_file = sweep_path / 'sweep_metadata.json'
    if not metadata_file.exists():
        print(f"Warning: No sweep_metadata.json found in {sweep_folder}")
        return

    with open(metadata_file, 'r') as f:
        sweep_metadata = json.load(f)

    # Get sweep information
    design = sweep_metadata.get('design', 'unknown')
    timestamp = sweep_metadata.get('timestamp', '')
    tool = sweep_metadata.get('ansys_tool', 'unknown')
    varied_params = sweep_metadata.get('varied_parameters', {})
    simulations = sweep_metadata.get('simulations', [])

    if not varied_params:
        print("No varied parameters detected, skipping plots.")
        return

    # Filter out metadata parameters
    excluded_params = {'name', 'extra_json_data', 'box', 'face_stack'}
    meaningful_params = {k: v for k, v in varied_params.items() if k not in excluded_params}

    if not meaningful_params:
        print("No meaningful varied parameters detected (only metadata varied), skipping plots.")
        return

    # Collect data from all simulations with ALL parameter values
    sim_data = []
    for sim_info in simulations:
        sim_name = sim_info['name']
        sim_folder = sweep_path / sim_name

        # Read simulation metadata
        sim_metadata_file = sim_folder / 'metadata.json'
        if not sim_metadata_file.exists():
            continue

        with open(sim_metadata_file, 'r') as f:
            sim_metadata = json.load(f)

        # Get ALL parameter values
        params = {k: sim_metadata.get('parameters', {}).get(k, None)
                  for k in meaningful_params.keys()}

        # Get results summary
        results_summary = sim_metadata.get('results_summary', {})

        if results_summary and all(v is not None for v in params.values()):
            sim_data.append({
                'params': params,
                'results': results_summary,
                'name': sim_name
            })

    if not sim_data:
        print("No simulation results found for plotting.")
        return

    # Determine what to plot based on available results
    sample_results = sim_data[0]['results']

    # Get simulation tolerance for error bars
    percent_error = sweep_metadata.get('export_parameters', {}).get('percent_error', None)

    # Check if this is a multi-parameter sweep
    num_params = len(meaningful_params)

    if num_params == 1:
        # Single-parameter sweep (backward compatibility)
        primary_param = list(meaningful_params.keys())[0]

        # Sort by parameter value
        sim_data.sort(key=lambda x: x['params'][primary_param])

        # Extract x-axis values
        x_values = [d['params'][primary_param] for d in sim_data]

        # Create plots based on tool type
        if tool == 'q3d':
            plot_q3d_results(sweep_path, x_values, sim_data, primary_param,
                            design, timestamp, sample_results, percent_error)
        elif tool == 'eigenmode':
            plot_eigenmode_results(sweep_path, x_values, sim_data, primary_param,
                                  design, timestamp, sample_results)
        elif tool == 'hfss':
            plot_hfss_results(sweep_path, x_values, sim_data, primary_param,
                             design, timestamp, sample_results)

    elif num_params == 2:
        # Two-parameter sweep: create dual plots
        param_names = list(meaningful_params.keys())

        # Create plots based on tool type
        if tool == 'q3d':
            plot_q3d_multi_param(sweep_path, sim_data, param_names,
                                design, timestamp, sample_results, percent_error)
        elif tool == 'eigenmode':
            plot_eigenmode_multi_param(sweep_path, sim_data, param_names,
                                      design, timestamp, sample_results)
        elif tool == 'hfss':
            plot_hfss_multi_param(sweep_path, sim_data, param_names,
                                 design, timestamp, sample_results)

    else:
        # More than 2 parameters: fall back to pairwise plotting
        print(f"Detected {num_params} varied parameters. Creating pairwise plots...")
        param_names = list(meaningful_params.keys())

        for i, param1 in enumerate(param_names):
            for param2 in param_names[i+1:]:
                pair_params = [param1, param2]

                if tool == 'q3d':
                    plot_q3d_multi_param(sweep_path, sim_data, pair_params,
                                        design, timestamp, sample_results, percent_error,
                                        suffix=f"_{param1}_vs_{param2}")
                elif tool == 'eigenmode':
                    plot_eigenmode_multi_param(sweep_path, sim_data, pair_params,
                                              design, timestamp, sample_results,
                                              suffix=f"_{param1}_vs_{param2}")
                elif tool == 'hfss':
                    plot_hfss_multi_param(sweep_path, sim_data, pair_params,
                                         design, timestamp, sample_results,
                                         suffix=f"_{param1}_vs_{param2}")

    print(f"[OK] Generated plots in {sweep_path / 'plots'}")


def plot_q3d_results(sweep_path, x_values, sim_data, param_name, design, timestamp, sample_results, percent_error=None):
    """Generate plots for Q3D simulations (capacitance/inductance).

    Args:
        sweep_path: Path to sweep folder
        x_values: X-axis parameter values
        sim_data: List of simulation data dicts
        param_name: Name of swept parameter
        design: Design name
        timestamp: Sweep timestamp
        sample_results: Sample results dict for key detection
        percent_error: Simulation convergence tolerance (e.g., 0.3 for 0.3%)
    """
    plots_folder = sweep_path / 'plots'
    plots_folder.mkdir(exist_ok=True)

    # Get all available matrix elements (support both old and new naming)
    # Old style: capacitance_11, inductance_12
    # New style: C_feedline, L_feedline_main_inductor
    capacitance_keys = [k for k in sample_results.keys() if k.startswith('capacitance_') or k.startswith('C_')]
    inductance_keys = [k for k in sample_results.keys() if k.startswith('inductance_') or k.startswith('L_')]

    # Format timestamp for plot
    try:
        dt = datetime.fromisoformat(timestamp)
        timestamp_str = dt.strftime('%Y-%m-%d %H:%M:%S')
    except:
        timestamp_str = timestamp

    # Helper function to separate matrix elements
    def separate_matrix_elements(keys):
        """Separate matrix elements into diagonal and unique off-diagonal pairs.

        Handles both old-style (inductance_11) and new-style (L_feedline) keys.
        """
        diagonal = []
        offdiag_unique = []
        seen_pairs = set()

        for k in keys:
            parts = k.split('_')

            # Check if this is new-style naming (descriptive names like L_feedline or L_feedline_inductor)
            if len(parts) >= 2 and (k.startswith('C_') or k.startswith('L_') or k.startswith('R_')):
                # New style: count underscores to determine if self or mutual
                # Self: C_feedline (1 underscore after prefix)
                # Mutual: C_feedline_inductor (2+ underscores after prefix)
                if len(parts) == 2:
                    diagonal.append(k)  # Self-inductance/capacitance
                else:
                    # Mutual - check if we've seen the reverse
                    net_names = parts[1:]
                    pair = tuple(sorted(net_names))
                    if pair not in seen_pairs:
                        seen_pairs.add(pair)
                        offdiag_unique.append(k)
            else:
                # Old style: extract numeric indices
                if len(parts) >= 2:
                    indices = parts[1]  # e.g., "11", "12", "21"
                    if len(indices) >= 2:
                        i, j = indices[0], indices[1]
                        if i == j:
                            diagonal.append(k)
                        else:
                            # Only keep unique pairs (e.g., keep "12" but skip "21")
                            pair = tuple(sorted([i, j]))
                            if pair not in seen_pairs:
                                seen_pairs.add(pair)
                                offdiag_unique.append(k)

        return diagonal, offdiag_unique

    # Helper function to create individual element plot
    def plot_single_element(key, matrix_type, unit, y_label):
        """Create a plot for a single matrix element with error bars.

        Handles both old-style (inductance_11) and new-style (L_feedline) keys.
        """
        fig, ax = plt.subplots(figsize=(10, 6))

        # Get y-values
        y_values = np.array([d['results'].get(key, 0) for d in sim_data])

        # Calculate error bars if percent_error is provided
        if percent_error is not None:
            y_errors = np.abs(y_values) * (percent_error / 100.0)
        else:
            y_errors = None

        # Determine if this is new-style or old-style naming
        is_new_style = key.startswith('C_') or key.startswith('L_') or key.startswith('R_')

        if is_new_style:
            # New style: use descriptive names as-is
            parts = key.split('_', 1)  # Split only on first underscore to get prefix and net info
            if len(parts) >= 2:
                matrix_prefix = parts[0]  # 'L', 'C', or 'R'
                net_info = parts[1]  # e.g., "feedline" or "feedline_main_inductor"

                # Determine if self or mutual based on underscore count
                # Self: one component (feedline, main_inductor)
                # Mutual: multiple components (feedline_main_inductor)
                underscore_count = key.count('_')

                if underscore_count == 1:
                    # Self term (only one underscore: the one after the matrix prefix)
                    element_type = 'Self'
                else:
                    # Mutual term (more than one underscore)
                    element_type = 'Mutual'

                # Use the descriptive name directly in labels
                label = f'{matrix_prefix}_{{{net_info}}}'
                title_element = f'{matrix_prefix}_{{{net_info}}}'
                filename_base = net_info
            else:
                # Fallback
                element_type = 'Unknown'
                label = key
                title_element = key
                filename_base = key.replace(f'{matrix_type}_', '')
        else:
            # Old style: extract numeric indices
            indices = key.replace(f'{matrix_type}_', '')
            i, j = indices[0], indices[1] if len(indices) > 1 else indices[0]

            if i == j:
                element_type = 'Self'
            else:
                element_type = 'Mutual'

            label = f'{matrix_type[0].upper()}_{{{i}{j}}}'
            title_element = f'{matrix_type[0].upper()}_{{{i}{j}}}'
            filename_base = indices

        # Plot with error bars
        if y_errors is not None:
            ax.errorbar(x_values, y_values, yerr=y_errors, fmt='o-',
                       linewidth=2, markersize=8, capsize=5, capthick=2,
                       label=label)
        else:
            ax.plot(x_values, y_values, 'o-', linewidth=2, markersize=8,
                   label=label)

        # Format plot
        ax.set_xlabel(param_name.replace('_', ' ').title(), fontsize=12)
        ax.set_ylabel(f'{y_label} ({unit})', fontsize=12)

        # Create title
        ax.set_title(f'{element_type} {y_label} {title_element} vs {param_name.replace("_", " ").title()}\n{design}',
                    fontsize=14)

        ax.legend()
        ax.grid(True, alpha=0.3)

        # Add timestamp and tolerance annotation
        annotation_text = f'Sweep: {timestamp_str}'
        if percent_error is not None:
            annotation_text += f'\nTolerance: ±{percent_error}%'
        ax.text(0.02, 0.98, annotation_text,
               transform=ax.transAxes, fontsize=8, verticalalignment='top',
               bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.3))

        plt.tight_layout()

        # Save with descriptive filename
        filename = f'{matrix_type}_{filename_base}.png'
        plt.savefig(plots_folder / filename, dpi=150)
        plt.close()

    # Plot capacitance matrix elements
    if capacitance_keys:
        diagonal_keys, offdiag_keys = separate_matrix_elements(capacitance_keys)

        # Create individual plot for each diagonal element
        for key in diagonal_keys:
            plot_single_element(key, 'capacitance', 'fF', 'Capacitance')

        # Create individual plot for each unique off-diagonal element
        for key in offdiag_keys:
            plot_single_element(key, 'capacitance', 'fF', 'Capacitance')

    # Plot inductance matrix elements
    if inductance_keys:
        diagonal_keys, offdiag_keys = separate_matrix_elements(inductance_keys)

        # Create individual plot for each diagonal element
        for key in diagonal_keys:
            plot_single_element(key, 'inductance', 'nH', 'Inductance')

        # Create individual plot for each unique off-diagonal element
        for key in offdiag_keys:
            plot_single_element(key, 'inductance', 'nH', 'Inductance')


def plot_q3d_multi_param(sweep_path, sim_data, param_names, design, timestamp, sample_results, percent_error=None, suffix=''):
    """Generate plots for Q3D simulations with multiple parameters.

    Creates two plots for each matrix element:
    1. Lines for different values of param1, plotted vs param2
    2. Lines for different values of param2, plotted vs param1

    Args:
        sweep_path: Path to sweep folder
        sim_data: List of simulation data dicts with 'params' and 'results' keys
        param_names: List of two parameter names [param1, param2]
        design: Design name
        timestamp: Sweep timestamp
        sample_results: Sample results dict for key detection
        percent_error: Simulation convergence tolerance (e.g., 0.3 for 0.3%)
        suffix: Optional filename suffix for multi-parameter sweeps
    """
    plots_folder = sweep_path / 'plots'
    plots_folder.mkdir(exist_ok=True)

    param1, param2 = param_names

    # Get all available matrix elements
    capacitance_keys = [k for k in sample_results.keys() if k.startswith('capacitance_') or k.startswith('C_')]
    inductance_keys = [k for k in sample_results.keys() if k.startswith('inductance_') or k.startswith('L_')]

    # Format timestamp for plot
    try:
        dt = datetime.fromisoformat(timestamp)
        timestamp_str = dt.strftime('%Y-%m-%d %H:%M:%S')
    except:
        timestamp_str = timestamp

    # Get unique values for each parameter
    param1_values = sorted(set(d['params'][param1] for d in sim_data))
    param2_values = sorted(set(d['params'][param2] for d in sim_data))

    # Helper function to create dual plots for a single matrix element
    def plot_dual_matrix_element(key, matrix_type, unit, y_label):
        """Create two plots for a single matrix element: param1 vs param2 and param2 vs param1."""

        # Determine element type and labels (same logic as single-param version)
        is_new_style = key.startswith('C_') or key.startswith('L_') or key.startswith('R_')

        if is_new_style:
            parts = key.split('_', 1)
            if len(parts) >= 2:
                matrix_prefix = parts[0]
                net_info = parts[1]
                underscore_count = key.count('_')
                element_type = 'Self' if underscore_count == 1 else 'Mutual'
                title_element = f'{matrix_prefix}_{{{net_info}}}'
                filename_base = net_info
            else:
                element_type = 'Unknown'
                title_element = key
                filename_base = key.replace(f'{matrix_type}_', '')
        else:
            indices = key.replace(f'{matrix_type}_', '')
            i, j = indices[0], indices[1] if len(indices) > 1 else indices[0]
            element_type = 'Self' if i == j else 'Mutual'
            title_element = f'{matrix_type[0].upper()}_{{{i}{j}}}'
            filename_base = indices

        # PLOT 1: Lines for each value of param1, x-axis is param2
        fig, ax = plt.subplots(figsize=(10, 6))

        for p1_val in param1_values:
            # Get data points for this param1 value
            x_vals = []
            y_vals = []

            for p2_val in param2_values:
                # Find simulation with these parameter values
                matching = [d for d in sim_data
                           if d['params'][param1] == p1_val and d['params'][param2] == p2_val]

                if matching:
                    x_vals.append(p2_val)
                    y_vals.append(matching[0]['results'].get(key, 0))

            if x_vals:
                y_array = np.array(y_vals)

                # Calculate error bars
                if percent_error is not None:
                    y_errors = np.abs(y_array) * (percent_error / 100.0)
                    ax.errorbar(x_vals, y_vals, yerr=y_errors, fmt='o-',
                               linewidth=2, markersize=8, capsize=5, capthick=2,
                               label=f'{param1}={p1_val}')
                else:
                    ax.plot(x_vals, y_vals, 'o-', linewidth=2, markersize=8,
                           label=f'{param1}={p1_val}')

        ax.set_xlabel(param2.replace('_', ' ').title(), fontsize=12)
        ax.set_ylabel(f'{y_label} ({unit})', fontsize=12)
        ax.set_title(f'{element_type} {y_label} {title_element}\nvs {param2.replace("_", " ").title()} (lines: {param1.replace("_", " ").title()})\n{design}',
                    fontsize=14)
        ax.legend()
        ax.grid(True, alpha=0.3)

        # Add timestamp and tolerance annotation
        annotation_text = f'Sweep: {timestamp_str}'
        if percent_error is not None:
            annotation_text += f'\nTolerance: ±{percent_error}%'
        ax.text(0.02, 0.98, annotation_text,
               transform=ax.transAxes, fontsize=8, verticalalignment='top',
               bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.3))

        plt.tight_layout()

        filename = f'{matrix_type}_{filename_base}_vs_{param2}{suffix}.png'
        plt.savefig(plots_folder / filename, dpi=150)
        plt.close()

        # PLOT 2: Lines for each value of param2, x-axis is param1
        fig, ax = plt.subplots(figsize=(10, 6))

        for p2_val in param2_values:
            # Get data points for this param2 value
            x_vals = []
            y_vals = []

            for p1_val in param1_values:
                # Find simulation with these parameter values
                matching = [d for d in sim_data
                           if d['params'][param1] == p1_val and d['params'][param2] == p2_val]

                if matching:
                    x_vals.append(p1_val)
                    y_vals.append(matching[0]['results'].get(key, 0))

            if x_vals:
                y_array = np.array(y_vals)

                # Calculate error bars
                if percent_error is not None:
                    y_errors = np.abs(y_array) * (percent_error / 100.0)
                    ax.errorbar(x_vals, y_vals, yerr=y_errors, fmt='o-',
                               linewidth=2, markersize=8, capsize=5, capthick=2,
                               label=f'{param2}={p2_val}')
                else:
                    ax.plot(x_vals, y_vals, 'o-', linewidth=2, markersize=8,
                           label=f'{param2}={p2_val}')

        ax.set_xlabel(param1.replace('_', ' ').title(), fontsize=12)
        ax.set_ylabel(f'{y_label} ({unit})', fontsize=12)
        ax.set_title(f'{element_type} {y_label} {title_element}\nvs {param1.replace("_", " ").title()} (lines: {param2.replace("_", " ").title()})\n{design}',
                    fontsize=14)
        ax.legend()
        ax.grid(True, alpha=0.3)

        # Add timestamp and tolerance annotation
        ax.text(0.02, 0.98, annotation_text,
               transform=ax.transAxes, fontsize=8, verticalalignment='top',
               bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.3))

        plt.tight_layout()

        filename = f'{matrix_type}_{filename_base}_vs_{param1}{suffix}.png'
        plt.savefig(plots_folder / filename, dpi=150)
        plt.close()

    # Helper function to separate matrix elements (same as single-param version)
    def separate_matrix_elements(keys):
        diagonal = []
        offdiag_unique = []
        seen_pairs = set()

        for k in keys:
            parts = k.split('_')

            if len(parts) >= 2 and (k.startswith('C_') or k.startswith('L_') or k.startswith('R_')):
                if len(parts) == 2:
                    diagonal.append(k)
                else:
                    net_names = parts[1:]
                    pair = tuple(sorted(net_names))
                    if pair not in seen_pairs:
                        seen_pairs.add(pair)
                        offdiag_unique.append(k)
            else:
                if len(parts) >= 2:
                    indices = parts[1]
                    if len(indices) >= 2:
                        i, j = indices[0], indices[1]
                        if i == j:
                            diagonal.append(k)
                        else:
                            pair = tuple(sorted([i, j]))
                            if pair not in seen_pairs:
                                seen_pairs.add(pair)
                                offdiag_unique.append(k)

        return diagonal, offdiag_unique

    # Plot capacitance matrix elements
    if capacitance_keys:
        diagonal_keys, offdiag_keys = separate_matrix_elements(capacitance_keys)

        for key in diagonal_keys:
            plot_dual_matrix_element(key, 'capacitance', 'fF', 'Capacitance')

        for key in offdiag_keys:
            plot_dual_matrix_element(key, 'capacitance', 'fF', 'Capacitance')

    # Plot inductance matrix elements
    if inductance_keys:
        diagonal_keys, offdiag_keys = separate_matrix_elements(inductance_keys)

        for key in diagonal_keys:
            plot_dual_matrix_element(key, 'inductance', 'nH', 'Inductance')

        for key in offdiag_keys:
            plot_dual_matrix_element(key, 'inductance', 'nH', 'Inductance')


def plot_eigenmode_results(sweep_path, x_values, sim_data, param_name, design, timestamp, sample_results):
    """Generate plots for eigenmode simulations (resonant frequency and Q factor).

    Creates separate plots for each mode's frequency and Q factor.
    """
    plots_folder = sweep_path / 'plots'
    plots_folder.mkdir(exist_ok=True)

    # Format timestamp
    try:
        dt = datetime.fromisoformat(timestamp)
        timestamp_str = dt.strftime('%Y-%m-%d %H:%M:%S')
    except:
        timestamp_str = timestamp

    # Find all frequency and Q factor keys
    freq_keys = [k for k in sample_results.keys() if k.startswith('frequency_mode_')]
    q_keys = [k for k in sample_results.keys() if k.startswith('Q_mode_')]

    # Helper function to plot individual mode data
    def plot_single_mode(key, y_label, unit, filename_prefix):
        """Create a plot for a single eigenmode parameter."""
        fig, ax = plt.subplots(figsize=(10, 6))

        # Get y-values
        y_values = np.array([d['results'].get(key, 0) for d in sim_data])

        # Extract mode number from key (e.g., "frequency_mode_1" -> "1")
        mode_num = key.split('_')[-1]

        # Create label
        label = f'{y_label} (Mode {mode_num})'

        # Plot
        ax.plot(x_values, y_values, 'o-', linewidth=2, markersize=8, label=label)

        # Format plot
        ax.set_xlabel(param_name.replace('_', ' ').title(), fontsize=12)
        ax.set_ylabel(f'{y_label} ({unit})' if unit else y_label, fontsize=12)
        ax.set_title(f'{y_label} (Mode {mode_num}) vs {param_name.replace("_", " ").title()}\n{design}',
                    fontsize=14)
        ax.legend()
        ax.grid(True, alpha=0.3)

        # Add timestamp annotation
        ax.text(0.02, 0.98, f'Sweep: {timestamp_str}',
               transform=ax.transAxes, fontsize=8, verticalalignment='top',
               bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.3))

        plt.tight_layout()

        # Save with descriptive filename
        filename = f'{filename_prefix}_mode_{mode_num}.png'
        plt.savefig(plots_folder / filename, dpi=150)
        plt.close()

    # Plot each mode's frequency
    for freq_key in freq_keys:
        plot_single_mode(freq_key, 'Frequency', 'GHz', 'frequency')

    # Plot each mode's Q factor
    for q_key in q_keys:
        # Only plot if Q > 0 (Q=0 means lossless simulation)
        y_values = np.array([d['results'].get(q_key, 0) for d in sim_data])
        if np.any(y_values > 0):
            plot_single_mode(q_key, 'Q Factor', '', 'Q_factor')

    # Create combined frequency plot if multiple modes exist
    if len(freq_keys) > 1:
        fig, ax = plt.subplots(figsize=(10, 6))

        for key in freq_keys:
            y_values = [d['results'].get(key, 0) for d in sim_data]
            mode_num = key.split('_')[-1]
            label = f'Mode {mode_num}'
            ax.plot(x_values, y_values, 'o-', linewidth=2, markersize=8, label=label)

        ax.set_xlabel(param_name.replace('_', ' ').title(), fontsize=12)
        ax.set_ylabel('Frequency (GHz)', fontsize=12)
        ax.set_title(f'Resonant Frequencies vs {param_name.replace("_", " ").title()}\n{design}', fontsize=14)
        ax.legend()
        ax.grid(True, alpha=0.3)

        # Add timestamp annotation
        ax.text(0.02, 0.98, f'Sweep: {timestamp_str}',
               transform=ax.transAxes, fontsize=8, verticalalignment='top',
               bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.3))

        plt.tight_layout()
        plt.savefig(plots_folder / 'frequency_all_modes.png', dpi=150)
        plt.close()

    # Create combined Q factor plot if multiple modes exist and Q > 0
    if len(q_keys) > 1:
        # Check if any Q values are non-zero
        has_nonzero_q = False
        for q_key in q_keys:
            y_values = np.array([d['results'].get(q_key, 0) for d in sim_data])
            if np.any(y_values > 0):
                has_nonzero_q = True
                break

        if has_nonzero_q:
            fig, ax = plt.subplots(figsize=(10, 6))

            for key in q_keys:
                y_values = np.array([d['results'].get(key, 0) for d in sim_data])
                if np.any(y_values > 0):  # Only plot if Q > 0
                    mode_num = key.split('_')[-1]
                    label = f'Mode {mode_num}'
                    ax.plot(x_values, y_values, 'o-', linewidth=2, markersize=8, label=label)

            ax.set_xlabel(param_name.replace('_', ' ').title(), fontsize=12)
            ax.set_ylabel('Q Factor', fontsize=12)
            ax.set_title(f'Quality Factors vs {param_name.replace("_", " ").title()}\n{design}', fontsize=14)
            ax.legend()
            ax.grid(True, alpha=0.3)

            # Add timestamp annotation
            ax.text(0.02, 0.98, f'Sweep: {timestamp_str}',
                   transform=ax.transAxes, fontsize=8, verticalalignment='top',
                   bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.3))

            plt.tight_layout()
            plt.savefig(plots_folder / 'Q_factor_all_modes.png', dpi=150)
            plt.close()


def plot_eigenmode_multi_param(sweep_path, sim_data, param_names, design, timestamp, sample_results, suffix=''):
    """Generate plots for eigenmode simulations with multiple parameters.

    Creates two plots for each mode:
    1. Lines for different values of param1, plotted vs param2
    2. Lines for different values of param2, plotted vs param1
    """
    plots_folder = sweep_path / 'plots'
    plots_folder.mkdir(exist_ok=True)

    param1, param2 = param_names

    # Format timestamp
    try:
        dt = datetime.fromisoformat(timestamp)
        timestamp_str = dt.strftime('%Y-%m-%d %H:%M:%S')
    except:
        timestamp_str = timestamp

    # Get unique values for each parameter
    param1_values = sorted(set(d['params'][param1] for d in sim_data))
    param2_values = sorted(set(d['params'][param2] for d in sim_data))

    # Find all frequency and Q factor keys
    freq_keys = [k for k in sample_results.keys() if k.startswith('frequency_mode_')]
    q_keys = [k for k in sample_results.keys() if k.startswith('Q_mode_')]

    # Helper function to create dual plots for a mode parameter
    def plot_dual_mode_param(key, y_label, unit, filename_prefix):
        """Create two plots for a single mode parameter."""

        mode_num = key.split('_')[-1]

        # PLOT 1: Lines for each value of param1, x-axis is param2
        fig, ax = plt.subplots(figsize=(10, 6))

        for p1_val in param1_values:
            x_vals = []
            y_vals = []

            for p2_val in param2_values:
                matching = [d for d in sim_data
                           if d['params'][param1] == p1_val and d['params'][param2] == p2_val]

                if matching:
                    x_vals.append(p2_val)
                    y_vals.append(matching[0]['results'].get(key, 0))

            if x_vals:
                ax.plot(x_vals, y_vals, 'o-', linewidth=2, markersize=8,
                       label=f'{param1}={p1_val}')

        ax.set_xlabel(param2.replace('_', ' ').title(), fontsize=12)
        ax.set_ylabel(f'{y_label} ({unit})' if unit else y_label, fontsize=12)
        ax.set_title(f'{y_label} (Mode {mode_num})\nvs {param2.replace("_", " ").title()} (lines: {param1.replace("_", " ").title()})\n{design}',
                    fontsize=14)
        ax.legend()
        ax.grid(True, alpha=0.3)

        ax.text(0.02, 0.98, f'Sweep: {timestamp_str}',
               transform=ax.transAxes, fontsize=8, verticalalignment='top',
               bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.3))

        plt.tight_layout()

        filename = f'{filename_prefix}_mode_{mode_num}_vs_{param2}{suffix}.png'
        plt.savefig(plots_folder / filename, dpi=150)
        plt.close()

        # PLOT 2: Lines for each value of param2, x-axis is param1
        fig, ax = plt.subplots(figsize=(10, 6))

        for p2_val in param2_values:
            x_vals = []
            y_vals = []

            for p1_val in param1_values:
                matching = [d for d in sim_data
                           if d['params'][param1] == p1_val and d['params'][param2] == p2_val]

                if matching:
                    x_vals.append(p1_val)
                    y_vals.append(matching[0]['results'].get(key, 0))

            if x_vals:
                ax.plot(x_vals, y_vals, 'o-', linewidth=2, markersize=8,
                       label=f'{param2}={p2_val}')

        ax.set_xlabel(param1.replace('_', ' ').title(), fontsize=12)
        ax.set_ylabel(f'{y_label} ({unit})' if unit else y_label, fontsize=12)
        ax.set_title(f'{y_label} (Mode {mode_num})\nvs {param1.replace("_", " ").title()} (lines: {param2.replace("_", " ").title()})\n{design}',
                    fontsize=14)
        ax.legend()
        ax.grid(True, alpha=0.3)

        ax.text(0.02, 0.98, f'Sweep: {timestamp_str}',
               transform=ax.transAxes, fontsize=8, verticalalignment='top',
               bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.3))

        plt.tight_layout()

        filename = f'{filename_prefix}_mode_{mode_num}_vs_{param1}{suffix}.png'
        plt.savefig(plots_folder / filename, dpi=150)
        plt.close()

    # Plot each mode's frequency
    for freq_key in freq_keys:
        plot_dual_mode_param(freq_key, 'Frequency', 'GHz', 'frequency')

    # Plot each mode's Q factor
    for q_key in q_keys:
        y_values = np.array([d['results'].get(q_key, 0) for d in sim_data])
        if np.any(y_values > 0):
            plot_dual_mode_param(q_key, 'Q Factor', '', 'Q_factor')


def plot_hfss_multi_param(sweep_path, sim_data, param_names, design, timestamp, sample_results, suffix=''):
    """Generate plots for HFSS simulations with multiple parameters.

    Creates two plots for each S-parameter or Q-factor:
    1. Lines for different values of param1, plotted vs param2
    2. Lines for different values of param2, plotted vs param1
    """
    plots_folder = sweep_path / 'plots'
    plots_folder.mkdir(exist_ok=True)

    param1, param2 = param_names

    # Format timestamp
    try:
        dt = datetime.fromisoformat(timestamp)
        timestamp_str = dt.strftime('%Y-%m-%d %H:%M:%S')
    except:
        timestamp_str = timestamp

    # Get unique values for each parameter
    param1_values = sorted(set(d['params'][param1] for d in sim_data))
    param2_values = sorted(set(d['params'][param2] for d in sim_data))

    # Look for Q-factor, S-parameters, etc.
    q_keys = [k for k in sample_results.keys() if 'q_factor' in k.lower() or 'quality' in k.lower()]
    s_keys = [k for k in sample_results.keys() if k.lower().startswith('s')]

    # Helper function to create dual plots
    def plot_dual_hfss_param(key, y_label):
        """Create two plots for an HFSS parameter."""

        # PLOT 1: Lines for each value of param1, x-axis is param2
        fig, ax = plt.subplots(figsize=(10, 6))

        for p1_val in param1_values:
            x_vals = []
            y_vals = []

            for p2_val in param2_values:
                matching = [d for d in sim_data
                           if d['params'][param1] == p1_val and d['params'][param2] == p2_val]

                if matching:
                    x_vals.append(p2_val)
                    y_vals.append(matching[0]['results'].get(key, 0))

            if x_vals:
                ax.plot(x_vals, y_vals, 'o-', linewidth=2, markersize=8,
                       label=f'{param1}={p1_val}')

        ax.set_xlabel(param2.replace('_', ' ').title(), fontsize=12)
        ax.set_ylabel(y_label, fontsize=12)
        ax.set_title(f'{y_label}\nvs {param2.replace("_", " ").title()} (lines: {param1.replace("_", " ").title()})\n{design}',
                    fontsize=14)
        ax.legend()
        ax.grid(True, alpha=0.3)

        ax.text(0.02, 0.98, f'Sweep: {timestamp_str}',
               transform=ax.transAxes, fontsize=8, verticalalignment='top',
               bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.3))

        plt.tight_layout()

        filename = f'{key}_vs_{param2}{suffix}.png'
        plt.savefig(plots_folder / filename, dpi=150)
        plt.close()

        # PLOT 2: Lines for each value of param2, x-axis is param1
        fig, ax = plt.subplots(figsize=(10, 6))

        for p2_val in param2_values:
            x_vals = []
            y_vals = []

            for p1_val in param1_values:
                matching = [d for d in sim_data
                           if d['params'][param1] == p1_val and d['params'][param2] == p2_val]

                if matching:
                    x_vals.append(p1_val)
                    y_vals.append(matching[0]['results'].get(key, 0))

            if x_vals:
                ax.plot(x_vals, y_vals, 'o-', linewidth=2, markersize=8,
                       label=f'{param2}={p2_val}')

        ax.set_xlabel(param1.replace('_', ' ').title(), fontsize=12)
        ax.set_ylabel(y_label, fontsize=12)
        ax.set_title(f'{y_label}\nvs {param1.replace("_", " ").title()} (lines: {param2.replace("_", " ").title()})\n{design}',
                    fontsize=14)
        ax.legend()
        ax.grid(True, alpha=0.3)

        ax.text(0.02, 0.98, f'Sweep: {timestamp_str}',
               transform=ax.transAxes, fontsize=8, verticalalignment='top',
               bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.3))

        plt.tight_layout()

        filename = f'{key}_vs_{param1}{suffix}.png'
        plt.savefig(plots_folder / filename, dpi=150)
        plt.close()

    # Plot Q-factors
    if q_keys:
        for key in q_keys:
            label = key.replace('_', ' ').title()
            plot_dual_hfss_param(key, label)

    # Plot S-parameters
    if s_keys:
        for key in s_keys:
            label = key.replace('_', ' ').upper()
            plot_dual_hfss_param(key, label)


def plot_hfss_results(sweep_path, x_values, sim_data, param_name, design, timestamp, sample_results):
    """Generate plots for HFSS simulations (S-parameters, Q-factor)."""
    plots_folder = sweep_path / 'plots'
    plots_folder.mkdir(exist_ok=True)

    # Format timestamp
    try:
        dt = datetime.fromisoformat(timestamp)
        timestamp_str = dt.strftime('%Y-%m-%d %H:%M:%S')
    except:
        timestamp_str = timestamp

    # Look for Q-factor, S-parameters, etc.
    q_keys = [k for k in sample_results.keys() if 'q_factor' in k.lower() or 'quality' in k.lower()]
    s_keys = [k for k in sample_results.keys() if k.lower().startswith('s')]

    if q_keys:
        fig, ax = plt.subplots(figsize=(10, 6))

        for key in q_keys:
            y_values = [d['results'].get(key, 0) for d in sim_data]
            label = key.replace('_', ' ').title()
            ax.plot(x_values, y_values, 'o-', linewidth=2, markersize=8, label=label)

        ax.set_xlabel(param_name.replace('_', ' ').title(), fontsize=12)
        ax.set_ylabel('Q Factor', fontsize=12)
        ax.set_title(f'Quality Factor vs {param_name.replace("_", " ").title()}\n{design}', fontsize=14)
        ax.legend()
        ax.grid(True, alpha=0.3)

        # Add timestamp annotation
        ax.text(0.02, 0.98, f'Sweep: {timestamp_str}',
               transform=ax.transAxes, fontsize=8, verticalalignment='top',
               bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.3))

        plt.tight_layout()
        plt.savefig(plots_folder / 'q_factor.png', dpi=150)
        plt.close()


if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1:
        plot_sweep_results(sys.argv[1])
    else:
        print("Usage: python plot_sweep.py <sweep_folder>")
