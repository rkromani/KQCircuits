"""
Post-processing script for fitting resonance models to HFSS wave equation S-parameter data.

Usage:
    python fit_s21_resonance.py <sweep_folder_path>

Example:
    python fit_s21_resonance.py "C:/Roger/Sim_Results/spike_resonator/20260204_143022_l_coupling_distance_sweep_hfss"

Output:
    - Individual fit_results.json in each simulation folder
    - Updated metadata.json with fit parameters in results_summary
    - Individual S21 fit plots in plots/ subfolder
    - Sweep-level summary plots (f_res, kappa, Q vs swept parameter)
    - s21_fit_summary.csv with all fit results
"""

import argparse
import csv
import json
import logging
import sys
from pathlib import Path
from typing import Dict, List
import numpy as np
import matplotlib.pyplot as plt
import skrf as rf

# Import resonance models
from resonance_models import fit_s21_resonance

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def load_s2p_file(filepath: Path) -> tuple:
    """
    Load S2P file and extract S21 data.

    Parameters:
        filepath: Path to .s2p file

    Returns:
        (freq_array, s21_complex_array)
    """
    try:
        network = rf.Network(str(filepath))
        freq = network.f  # Frequency in Hz
        s21 = network.s[:, 1, 0]  # S21 is s[freq_idx, port2, port1]
        return freq, s21
    except Exception as e:
        logger.error(f"Failed to load {filepath}: {e}")
        raise


def plot_individual_s21_fit(freq: np.ndarray, s21_data: np.ndarray,
                           fit_result: Dict, save_path: Path, title: str):
    """
    Plot S21 magnitude and phase with fitted model.
    Creates both full-range and zoomed-in plots.
    """
    from resonance_models import lorentzian_s21

    # Generate smooth frequency array for plotting fitted curve
    freq_smooth = np.linspace(freq[0], freq[-1], 2000)

    # Evaluate fitted model at smooth frequency points
    fit_params = fit_result['fit_params']
    s21_fit_smooth = lorentzian_s21(freq_smooth, *fit_params)

    # Create full-range plot
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8))

    # Magnitude
    ax1.plot(freq / 1e9, 20 * np.log10(np.abs(s21_data)), 'o',
             markersize=3, label='Simulation', alpha=0.6)
    ax1.plot(freq_smooth / 1e9, 20 * np.log10(np.abs(s21_fit_smooth)), '-',
             linewidth=2, label='Fit', color='red')
    ax1.set_xlabel('Frequency (GHz)')
    ax1.set_ylabel('|S21| (dB)')
    ax1.set_title(title)
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    # Add text box with hanger model fit parameters
    textstr = '\n'.join([
        f"f0 = {fit_result['f_res']/1e9:.6f} GHz",
        f"eta = {fit_result['eta']:.4f}",
        f"kappa = {fit_result['kappa_total']/1e6:.3f} MHz",
        f"Q_total = {fit_result['Q_total']:.0f}",
        f"Q_ext = {fit_result['Q_ext']:.0f}",
        f"Q_int = {fit_result['Q_int']:.0f}",
    ])
    ax1.text(0.02, 0.98, textstr, transform=ax1.transAxes,
             fontsize=10, verticalalignment='top',
             bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

    # Phase
    ax2.plot(freq / 1e9, np.angle(s21_data, deg=True), 'o',
             markersize=3, label='Simulation', alpha=0.6)
    ax2.plot(freq_smooth / 1e9, np.angle(s21_fit_smooth, deg=True), '-',
             linewidth=2, label='Fit', color='red')
    ax2.set_xlabel('Frequency (GHz)')
    ax2.set_ylabel('Phase(S21) (degrees)')
    ax2.legend()
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches='tight')
    plt.close()

    # Create zoomed-in plot (±3 linewidths around resonance)
    f_res = fit_result['f_res']
    kappa_total = fit_result['kappa_total']

    # Zoom range: ±3 * kappa_total (±3 linewidths)
    zoom_span = 3 * kappa_total  # Hz
    f_min = (f_res - zoom_span) / 1e9  # Convert to GHz
    f_max = (f_res + zoom_span) / 1e9

    # Find indices within zoom range for data points
    zoom_mask = (freq >= f_min * 1e9) & (freq <= f_max * 1e9)

    # Generate smooth frequency array for zoomed plot
    freq_zoom_smooth = np.linspace(f_min * 1e9, f_max * 1e9, 1000)
    s21_fit_zoom_smooth = lorentzian_s21(freq_zoom_smooth, *fit_params)

    if np.sum(zoom_mask) > 3:  # Only create zoom plot if enough points (reduced threshold for low-res data)
        fig_zoom, (ax1_zoom, ax2_zoom) = plt.subplots(2, 1, figsize=(10, 8))

        # Zoomed magnitude
        ax1_zoom.plot(freq[zoom_mask] / 1e9, 20 * np.log10(np.abs(s21_data[zoom_mask])), 'o',
                     markersize=5, label='Simulation', alpha=0.7)
        ax1_zoom.plot(freq_zoom_smooth / 1e9, 20 * np.log10(np.abs(s21_fit_zoom_smooth)), '-',
                     linewidth=2, label='Fit', color='red')
        ax1_zoom.set_xlabel('Frequency (GHz)')
        ax1_zoom.set_ylabel('|S21| (dB)')
        ax1_zoom.set_title(f"{title} (Zoomed)")
        ax1_zoom.legend()
        ax1_zoom.grid(True, alpha=0.3)

        # Add text box with hanger model fit parameters (same as full plot)
        ax1_zoom.text(0.02, 0.98, textstr, transform=ax1_zoom.transAxes,
                     fontsize=10, verticalalignment='top',
                     bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

        # Zoomed phase
        ax2_zoom.plot(freq[zoom_mask] / 1e9, np.angle(s21_data[zoom_mask], deg=True), 'o',
                     markersize=5, label='Simulation', alpha=0.7)
        ax2_zoom.plot(freq_zoom_smooth / 1e9, np.angle(s21_fit_zoom_smooth, deg=True), '-',
                     linewidth=2, label='Fit', color='red')
        ax2_zoom.set_xlabel('Frequency (GHz)')
        ax2_zoom.set_ylabel('Phase(S21) (degrees)')
        ax2_zoom.legend()
        ax2_zoom.grid(True, alpha=0.3)

        plt.tight_layout()

        # Save zoomed plot with "_zoom" suffix
        zoom_save_path = save_path.parent / f"{save_path.stem}_zoom{save_path.suffix}"
        plt.savefig(zoom_save_path, dpi=150, bbox_inches='tight')
        plt.close()


def plot_sweep_summary(sim_names: List[str], param_values: np.ndarray,
                      fit_results: List[Dict], param_name: str,
                      plots_folder: Path):
    """
    Generate sweep-level plots of fitted parameters vs swept parameter.
    """
    # Extract successful fits
    success_mask = np.array([r['success'] for r in fit_results])
    param_values_success = param_values[success_mask]

    f_res = np.array([r['f_res'] for r in fit_results if r['success']]) / 1e9
    kappa_ext = np.array([r['kappa_ext'] for r in fit_results if r['success']]) / 1e6
    kappa_int = np.array([r['kappa_int'] for r in fit_results if r['success']]) / 1e6
    Q_ext = np.array([r['Q_ext'] for r in fit_results if r['success']])
    Q_int = np.array([r['Q_int'] for r in fit_results if r['success']])
    Q_total = np.array([r['Q_total'] for r in fit_results if r['success']])

    # Plot 1: Resonance frequency vs parameter
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.plot(param_values_success, f_res, 'o-', markersize=8, linewidth=2)
    ax.set_xlabel(param_name)
    ax.set_ylabel('Resonance Frequency (GHz)')
    ax.set_title(f'Resonance Frequency vs {param_name}')
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(plots_folder / f'f_res_vs_{param_name}.png', dpi=150)
    plt.close()

    # Plot 2: Kappa (coupling rates) vs parameter
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.plot(param_values_success, kappa_ext, 'o-', markersize=8,
            linewidth=2, label='kappa_ext')
    ax.plot(param_values_success, kappa_int, 's-', markersize=8,
            linewidth=2, label='kappa_int')
    ax.set_xlabel(param_name)
    ax.set_ylabel('Coupling Rate (MHz)')
    ax.set_title(f'Coupling Rates vs {param_name}')
    ax.legend()
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(plots_folder / f'kappa_vs_{param_name}.png', dpi=150)
    plt.close()

    # Plot 3: Quality factors vs parameter
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.plot(param_values_success, Q_ext, 'o-', markersize=8,
            linewidth=2, label='Q_ext')
    ax.plot(param_values_success, Q_int, 's-', markersize=8,
            linewidth=2, label='Q_int')
    ax.plot(param_values_success, Q_total, '^-', markersize=8,
            linewidth=2, label='Q_total')
    ax.set_xlabel(param_name)
    ax.set_ylabel('Quality Factor')
    ax.set_title(f'Quality Factors vs {param_name}')
    ax.legend()
    ax.grid(True, alpha=0.3)
    ax.set_yscale('log')
    plt.tight_layout()
    plt.savefig(plots_folder / f'Q_factors_vs_{param_name}.png', dpi=150)
    plt.close()


def process_simulation(sim_folder: Path, plots_folder: Path) -> Dict:
    """
    Process a single simulation: fit S21 and generate plot.

    Parameters:
        sim_folder: Path to simulation folder (contains metadata.json and results/)
        plots_folder: Path to sweep-level plots folder

    Returns:
        Dictionary with fit results
    """
    sim_name = sim_folder.name
    logger.info(f"Processing {sim_name}...")

    # 1. Find .s2p file
    results_folder = sim_folder / "results"
    if not results_folder.exists():
        logger.warning(f"No results folder found in {sim_folder}")
        return {'success': False, 'error': 'No results folder'}

    s2p_files = list(results_folder.glob("*.s2p"))
    if len(s2p_files) == 0:
        logger.warning(f"No .s2p files found in {results_folder}")
        return {'success': False, 'error': 'No .s2p file'}

    # Use first .s2p file (typically only one)
    s2p_file = s2p_files[0]
    logger.info(f"  Found S2P: {s2p_file.name}")

    # 2. Load S21 data
    try:
        freq, s21 = load_s2p_file(s2p_file)
    except Exception as e:
        return {'success': False, 'error': f'Failed to load S2P: {str(e)}'}

    # 3. Fit resonance model
    fit_result = fit_s21_resonance(freq, s21, model='lorentzian')

    if not fit_result['success']:
        logger.error(f"  Fit failed: {fit_result.get('error', 'Unknown error')}")
        return fit_result

    # 4. Generate individual plot
    plot_individual_s21_fit(
        freq, s21, fit_result,
        save_path=plots_folder / f"s21_fit_{sim_name}.png",
        title=f"S21 Fit: {sim_name}"
    )

    # 5. Save fit results JSON
    fit_results_file = sim_folder / "fit_results.json"
    with open(fit_results_file, 'w') as f:
        # Convert numpy arrays to lists for JSON serialization
        fit_result_serializable = {
            k: (v.tolist() if isinstance(v, np.ndarray) else v)
            for k, v in fit_result.items()
            if k != 's21_fit'  # Don't save full fitted array in JSON
        }
        json.dump(fit_result_serializable, f, indent=2)

    logger.info(f"  f_res = {fit_result['f_res']/1e9:.6f} GHz")
    logger.info(f"  Q_ext = {fit_result['Q_ext']:.0f}")
    logger.info(f"  Q_int = {fit_result['Q_int']:.0f}")
    logger.info(f"  Q_total = {fit_result['Q_total']:.0f}")

    # 6. Update metadata.json
    metadata_file = sim_folder / "metadata.json"
    if metadata_file.exists():
        with open(metadata_file, 'r') as f:
            metadata = json.load(f)

        # Add fit results to results_summary
        if 'results_summary' not in metadata:
            metadata['results_summary'] = {}

        metadata['results_summary']['s21_fit'] = {
            'f_res_GHz': fit_result['f_res'] / 1e9,
            'kappa_ext_MHz': fit_result['kappa_ext'] / 1e6,
            'kappa_int_MHz': fit_result['kappa_int'] / 1e6,
            'kappa_total_MHz': fit_result['kappa_total'] / 1e6,
            'Q_ext': fit_result['Q_ext'],
            'Q_int': fit_result['Q_int'],
            'Q_total': fit_result['Q_total'],
            'chi_squared': fit_result['chi_squared'],
        }

        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)

    return fit_result


def create_csv_summary(simulations: List[Dict], fit_results: List[Dict],
                      varied_params: Dict, output_file: Path):
    """
    Create CSV file with sweep summary.
    """
    with open(output_file, 'w', newline='') as f:
        # Determine columns
        param_names = list(varied_params.keys())
        fieldnames = ['simulation_name'] + param_names + [
            'f_res_GHz', 'kappa_ext_MHz', 'kappa_int_MHz', 'kappa_total_MHz',
            'Q_ext', 'Q_int', 'Q_total', 'chi_squared', 'fit_success'
        ]

        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for sim_info, fit_result in zip(simulations, fit_results):
            row = {
                'simulation_name': sim_info['name'],
                'fit_success': fit_result['success']
            }

            # Add varied parameter values
            # Handle both formats: sim['varied_values'][i] or sim[param_name]
            for i, param_name in enumerate(param_names):
                if 'varied_values' in sim_info:
                    row[param_name] = sim_info['varied_values'][i]
                elif param_name in sim_info:
                    row[param_name] = sim_info[param_name]
                else:
                    row[param_name] = None

            # Add fit results if successful
            if fit_result['success']:
                row.update({
                    'f_res_GHz': fit_result['f_res'] / 1e9,
                    'kappa_ext_MHz': fit_result['kappa_ext'] / 1e6,
                    'kappa_int_MHz': fit_result['kappa_int'] / 1e6,
                    'kappa_total_MHz': fit_result['kappa_total'] / 1e6,
                    'Q_ext': fit_result['Q_ext'],
                    'Q_int': fit_result['Q_int'],
                    'Q_total': fit_result['Q_total'],
                    'chi_squared': fit_result['chi_squared'],
                })

            writer.writerow(row)


def process_sweep_folder(sweep_folder: Path):
    """
    Process all simulations in a sweep folder.
    """
    logger.info(f"Processing sweep folder: {sweep_folder}")

    # 1. Load sweep metadata
    sweep_metadata_file = sweep_folder / "sweep_metadata.json"
    if not sweep_metadata_file.exists():
        logger.error(f"No sweep_metadata.json found in {sweep_folder}")
        return

    with open(sweep_metadata_file, 'r') as f:
        sweep_metadata = json.load(f)

    # 2. Extract simulation list and varied parameters
    simulations = sweep_metadata.get('simulations', [])
    varied_params = sweep_metadata.get('varied_parameters', {})

    if len(simulations) == 0:
        logger.error("No simulations found in sweep metadata")
        return

    logger.info(f"Found {len(simulations)} simulations")
    logger.info(f"Varied parameters: {list(varied_params.keys())}")

    # 3. Create plots folder
    plots_folder = sweep_folder / "plots"
    plots_folder.mkdir(exist_ok=True)

    # 4. Process each simulation
    fit_results = []
    sim_names = []

    for sim_info in simulations:
        sim_name = sim_info['name']
        sim_folder = sweep_folder / sim_name

        if not sim_folder.exists():
            logger.warning(f"Simulation folder not found: {sim_folder}")
            fit_results.append({'success': False, 'error': 'Folder not found'})
            sim_names.append(sim_name)
            continue

        result = process_simulation(sim_folder, plots_folder)
        fit_results.append(result)
        sim_names.append(sim_name)

    # 5. Generate sweep-level summary plots
    if len(varied_params) == 1:
        # Single parameter sweep
        param_name = list(varied_params.keys())[0]
        # Extract parameter values from simulation entries
        # Format can be either sim['varied_values'][0] or sim[param_name]
        param_values = []
        for sim in simulations:
            if 'varied_values' in sim:
                param_values.append(sim['varied_values'][0])
            elif param_name in sim:
                param_values.append(sim[param_name])
            else:
                logger.warning(f"Could not find parameter value for {sim['name']}")
                param_values.append(None)
        param_values = np.array(param_values)

        plot_sweep_summary(sim_names, param_values, fit_results,
                          param_name, plots_folder)

    elif len(varied_params) > 1:
        # Multi-parameter sweep: plot for each parameter separately
        for i, param_name in enumerate(varied_params.keys()):
            param_values = []
            for sim in simulations:
                if 'varied_values' in sim:
                    param_values.append(sim['varied_values'][i])
                elif param_name in sim:
                    param_values.append(sim[param_name])
                else:
                    logger.warning(f"Could not find parameter {param_name} for {sim['name']}")
                    param_values.append(None)
            param_values = np.array(param_values)

            plot_sweep_summary(sim_names, param_values, fit_results,
                              param_name, plots_folder)

    # 6. Create CSV summary
    csv_file = sweep_folder / "s21_fit_summary.csv"
    create_csv_summary(simulations, fit_results, varied_params, csv_file)

    logger.info(f"\nProcessing complete!")
    logger.info(f"  Plots saved to: {plots_folder}")
    logger.info(f"  CSV summary: {csv_file}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Fit resonance models to HFSS wave equation S-parameter results'
    )
    parser.add_argument('sweep_folder', type=str,
                       help='Path to sweep folder containing simulations')

    args = parser.parse_args()

    sweep_folder = Path(args.sweep_folder)

    if not sweep_folder.exists():
        logger.error(f"Sweep folder not found: {sweep_folder}")
        sys.exit(1)

    process_sweep_folder(sweep_folder)
