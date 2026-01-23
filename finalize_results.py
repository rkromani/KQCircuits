"""
Finalize Simulation Results

Copies ANSYS simulation results to the database and updates metadata.

Usage:
    python finalize_results.py tmp/spike_res_q3d_sim_output
"""

import sys
import json
from pathlib import Path

# Add repo root to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from simulations_database.tools.simulation_db import SimulationDB
from simulations_database.tools.plot_sweep import plot_sweep_results


def main():
    if len(sys.argv) < 2:
        print("Usage: python finalize_results.py <ansys_output_folder>")
        print("Example: python finalize_results.py tmp/spike_res_q3d_sim_output")
        sys.exit(1)

    ansys_output_folder = Path(sys.argv[1])

    if not ansys_output_folder.exists():
        print(f"Error: Folder not found: {ansys_output_folder}")
        sys.exit(1)

    # Look for the db_mapping.json file
    mapping_file = ansys_output_folder.parent / f'{ansys_output_folder.name}_db_mapping.json'

    if not mapping_file.exists():
        print(f"Error: No database mapping file found at {mapping_file}")
        print("This simulation may not have been registered with the database.")
        print("Make sure the simulation script uses SimulationDB.register_simulations()")
        sys.exit(1)

    # Load the mapping
    with open(mapping_file, 'r') as f:
        db_folders = json.load(f)

    print(f"Found {len(db_folders)} simulations to finalize\n")

    # Initialize database
    db = SimulationDB()

    # Finalize each simulation
    for i, (sim_name, db_folder) in enumerate(db_folders.items(), 1):
        print(f"[{i}/{len(db_folders)}] {sim_name}")

        files_copied = db.finalize_simulation(sim_name, db_folder, ansys_output_folder)

        print(f"  [OK] Copied {files_copied} files to database")
        print(f"  [OK] Updated metadata")

    # Copy sweep-level result files (CSV aggregated results)
    sweep_folder = None
    if db_folders:
        first_folder = Path(list(db_folders.values())[0])
        sweep_folder = first_folder.parent

        # Find and copy sweep-level CSV files
        sweep_csv_files = list(ansys_output_folder.glob('*_results.csv'))
        if sweep_csv_files:
            print(f"\nCopying sweep-level result files...")
            for csv_file in sweep_csv_files:
                dest = sweep_folder / csv_file.name
                if not dest.exists():
                    import shutil
                    shutil.copy2(csv_file, dest)
                    print(f"  [OK] Copied {csv_file.name}")

    print(f"\n{'='*60}")
    print(f"[OK] All simulations finalized!")

    # Show where results are
    if sweep_folder:
        print(f"  Results: {sweep_folder}")
    print(f"{'='*60}")

    # Generate plots for the sweep
    if sweep_folder:
        print(f"\nGenerating plots...")
        try:
            plot_sweep_results(sweep_folder)
        except Exception as e:
            print(f"Warning: Could not generate plots: {e}")
            import traceback
            traceback.print_exc()


if __name__ == '__main__':
    main()
