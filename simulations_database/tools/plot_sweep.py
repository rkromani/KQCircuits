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

    # Determine the primary varied parameter (first meaningful one)
    primary_param = list(meaningful_params.keys())[0]

    # Collect data from all simulations
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

        # Get parameter value
        param_value = sim_metadata.get('parameters', {}).get(primary_param, None)

        # Get results summary
        results_summary = sim_metadata.get('results_summary', {})

        if param_value is not None and results_summary:
            sim_data.append({
                'param_value': param_value,
                'results': results_summary,
                'name': sim_name
            })

    if not sim_data:
        print("No simulation results found for plotting.")
        return

    # Sort by parameter value
    sim_data.sort(key=lambda x: x['param_value'])

    # Extract x-axis values
    x_values = [d['param_value'] for d in sim_data]

    # Determine what to plot based on available results
    sample_results = sim_data[0]['results']

    # Get simulation tolerance for error bars
    percent_error = sweep_metadata.get('export_parameters', {}).get('percent_error', None)

    # Create plots based on tool type
    if tool == 'q3d':
        # Q3D capacitance/inductance plots
        plot_q3d_results(sweep_path, x_values, sim_data, primary_param,
                        design, timestamp, sample_results, percent_error)
    elif tool == 'eigenmode':
        # Eigenmode frequency plots
        plot_eigenmode_results(sweep_path, x_values, sim_data, primary_param,
                              design, timestamp, sample_results)
    elif tool == 'hfss':
        # HFSS S-parameter plots
        plot_hfss_results(sweep_path, x_values, sim_data, primary_param,
                         design, timestamp, sample_results)

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

    # Get all available matrix elements
    capacitance_keys = [k for k in sample_results.keys() if k.startswith('capacitance_')]
    inductance_keys = [k for k in sample_results.keys() if k.startswith('inductance_')]

    # Format timestamp for plot
    try:
        dt = datetime.fromisoformat(timestamp)
        timestamp_str = dt.strftime('%Y-%m-%d %H:%M:%S')
    except:
        timestamp_str = timestamp

    # Helper function to separate matrix elements
    def separate_matrix_elements(keys):
        """Separate matrix elements into diagonal and unique off-diagonal pairs."""
        diagonal = []
        offdiag_unique = []
        seen_pairs = set()

        for k in keys:
            parts = k.split('_')
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
        """Create a plot for a single matrix element with error bars."""
        fig, ax = plt.subplots(figsize=(10, 6))

        # Get y-values
        y_values = np.array([d['results'].get(key, 0) for d in sim_data])

        # Calculate error bars if percent_error is provided
        if percent_error is not None:
            y_errors = np.abs(y_values) * (percent_error / 100.0)
        else:
            y_errors = None

        # Extract indices for label
        indices = key.replace(f'{matrix_type}_', '')
        i, j = indices[0], indices[1] if len(indices) > 1 else indices[0]

        # Plot with error bars
        if y_errors is not None:
            ax.errorbar(x_values, y_values, yerr=y_errors, fmt='o-',
                       linewidth=2, markersize=8, capsize=5, capthick=2,
                       label=f'{matrix_type[0].upper()}_{{{i}{j}}}')
        else:
            ax.plot(x_values, y_values, 'o-', linewidth=2, markersize=8,
                   label=f'{matrix_type[0].upper()}_{{{i}{j}}}')

        # Format plot
        ax.set_xlabel(param_name.replace('_', ' ').title(), fontsize=12)
        ax.set_ylabel(f'{y_label} ({unit})', fontsize=12)

        # Create title
        if i == j:
            element_type = 'Self'
        else:
            element_type = 'Mutual'
        ax.set_title(f'{element_type} {y_label} {matrix_type[0].upper()}_{{{i}{j}}} vs {param_name.replace("_", " ").title()}\n{design}',
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
        filename = f'{matrix_type}_{indices}.png'
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


def plot_eigenmode_results(sweep_path, x_values, sim_data, param_name, design, timestamp, sample_results):
    """Generate plots for eigenmode simulations (resonant frequency)."""
    plots_folder = sweep_path / 'plots'
    plots_folder.mkdir(exist_ok=True)

    # Format timestamp
    try:
        dt = datetime.fromisoformat(timestamp)
        timestamp_str = dt.strftime('%Y-%m-%d %H:%M:%S')
    except:
        timestamp_str = timestamp

    # Look for frequency results
    freq_keys = [k for k in sample_results.keys() if 'frequency' in k.lower() or 'freq' in k.lower()]

    if freq_keys:
        fig, ax = plt.subplots(figsize=(10, 6))

        for key in freq_keys:
            y_values = [d['results'].get(key, 0) for d in sim_data]
            label = key.replace('_', ' ').title()
            ax.plot(x_values, y_values, 'o-', linewidth=2, markersize=8, label=label)

        ax.set_xlabel(param_name.replace('_', ' ').title(), fontsize=12)
        ax.set_ylabel('Frequency (GHz)', fontsize=12)
        ax.set_title(f'Resonant Frequency vs {param_name.replace("_", " ").title()}\n{design}', fontsize=14)
        ax.legend()
        ax.grid(True, alpha=0.3)

        # Add timestamp annotation
        ax.text(0.02, 0.98, f'Sweep: {timestamp_str}',
               transform=ax.transAxes, fontsize=8, verticalalignment='top',
               bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.3))

        plt.tight_layout()
        plt.savefig(plots_folder / 'frequency.png', dpi=150)
        plt.close()


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
