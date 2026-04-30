"""
Update S-parameter files from ANSYS and regenerate plots.

This script is useful when you manually update ANSYS simulations and want to:
1. Copy the updated .s2p files to the database
2. Regenerate all plots and fits

Usage:
    python update_from_ansys.py <ansys_folder> [--db-folder <database_folder>]

Examples:
    # Auto-detect database folder from ansys folder
    python update_from_ansys.py tmp/spike_res_eigenmode_wave_sim_output

    # Specify database folder explicitly
    python update_from_ansys.py tmp/spike_res_eigenmode_wave_sim_output --db-folder C:/Roger/Sim_Results/spike_resonator/20260206_113051
"""

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Optional, List, Tuple


def find_database_folder(ansys_folder: Path) -> Optional[Path]:
    """Find the database folder from database_folders.json in ansys folder."""
    db_ref_file = ansys_folder / "database_folders.json"

    if db_ref_file.exists():
        with open(db_ref_file) as f:
            data = json.load(f)
            sweep_folder = data.get('sweep_folder')
            if sweep_folder:
                return Path(sweep_folder)

    return None


def find_s2p_files(ansys_folder: Path) -> List[Tuple[Path, str, str]]:
    """
    Find all .s2p files in the ANSYS folder.

    Returns:
        List of tuples: (s2p_file_path, eigenmode_name, wave_name)
    """
    s2p_files = []

    # Pattern: spike_res_eigenmode_XXX_and_spike_res_wave_XXX_SMatrix.s2p
    for s2p_file in ansys_folder.glob("*_SMatrix.s2p"):
        filename = s2p_file.stem  # Remove .s2p extension

        # Try to parse eigenmode + wave pattern
        if "_and_" in filename:
            parts = filename.split("_and_")
            eigenmode_name = parts[0]  # spike_res_eigenmode_XXX
            wave_part = parts[1].replace("_SMatrix", "")  # spike_res_wave_XXX
            wave_name = wave_part

            s2p_files.append((s2p_file, eigenmode_name, wave_name))
        else:
            # Fallback: just use the filename without _SMatrix
            wave_name = filename.replace("_SMatrix", "")
            s2p_files.append((s2p_file, None, wave_name))

    return s2p_files


def copy_s2p_to_database(s2p_file: Path, wave_name: str, db_folder: Path) -> bool:
    """
    Copy .s2p file to the database folder structure.

    Args:
        s2p_file: Path to source .s2p file
        wave_name: Name of the wave simulation (e.g., spike_res_wave_100)
        db_folder: Database sweep folder

    Returns:
        True if successful, False otherwise
    """
    # Database structure: db_folder/wave_name/results/wave_name.s2p
    dst_folder = db_folder / wave_name / "results"
    dst_file = dst_folder / f"{wave_name}.s2p"

    # Create results folder if it doesn't exist
    dst_folder.mkdir(parents=True, exist_ok=True)

    # Copy file
    try:
        shutil.copy2(s2p_file, dst_file)
        print(f"  [OK] {wave_name}.s2p")
        return True
    except Exception as e:
        print(f"  [ERROR] {wave_name}.s2p: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Copy updated S-parameter files from ANSYS and regenerate plots",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        "ansys_folder",
        type=Path,
        help="Folder containing ANSYS simulation results with .s2p files"
    )
    parser.add_argument(
        "--db-folder",
        type=Path,
        help="Database sweep folder (auto-detected if not specified)"
    )
    parser.add_argument(
        "--skip-plots",
        action="store_true",
        help="Skip regenerating plots (only copy files)"
    )
    parser.add_argument(
        "--show-internal",
        action="store_true",
        help="Include kappa_internal and Q_internal in plots (default: hide them)"
    )

    args = parser.parse_args()

    # Validate ANSYS folder
    if not args.ansys_folder.exists():
        print(f"ERROR: ANSYS folder not found: {args.ansys_folder}")
        sys.exit(1)

    print("="*70)
    print("Update S-parameters from ANSYS and Regenerate Plots")
    print("="*70)
    print(f"ANSYS folder: {args.ansys_folder}")

    # Find or validate database folder
    if args.db_folder:
        db_folder = args.db_folder
        print(f"Database folder (specified): {db_folder}")
    else:
        db_folder = find_database_folder(args.ansys_folder)
        if db_folder:
            print(f"Database folder (auto-detected): {db_folder}")
        else:
            print("\nERROR: Could not auto-detect database folder.")
            print("Please specify with --db-folder argument")
            sys.exit(1)

    if not db_folder.exists():
        print(f"\nERROR: Database folder not found: {db_folder}")
        sys.exit(1)

    # Find .s2p files
    print("\n" + "="*70)
    print("Finding S-parameter files...")
    print("="*70)

    s2p_files = find_s2p_files(args.ansys_folder)

    if not s2p_files:
        print("WARNING: No .s2p files found in ANSYS folder")
        sys.exit(1)

    print(f"Found {len(s2p_files)} S-parameter file(s)")

    # Copy files
    print("\n" + "="*70)
    print("Copying S-parameter files to database...")
    print("="*70)

    copied_count = 0
    for s2p_file, eigenmode_name, wave_name in s2p_files:
        if copy_s2p_to_database(s2p_file, wave_name, db_folder):
            copied_count += 1

    print(f"\nCopied {copied_count}/{len(s2p_files)} files successfully")

    if copied_count == 0:
        print("\nERROR: No files were copied. Cannot proceed.")
        sys.exit(1)

    # Regenerate plots
    if not args.skip_plots:
        print("\n" + "="*70)
        print("Regenerating plots and fits...")
        print("="*70)

        # Import and run the fitting script
        try:
            # Add tools directory to path
            tools_dir = Path(__file__).parent
            sys.path.insert(0, str(tools_dir))

            from fit_s21_resonance import process_sweep_folder

            # Run the fitting
            process_sweep_folder(db_folder, show_internal=args.show_internal)

            print("\n" + "="*70)
            print("SUCCESS!")
            print("="*70)
            print(f"Updated files and plots saved to:")
            print(f"  {db_folder}")
            print(f"\nPlots folder: {db_folder / 'plots'}")
            print(f"CSV summary: {db_folder / 's21_fit_summary.csv'}")

        except Exception as e:
            print(f"\nERROR during plotting: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)
    else:
        print("\n" + "="*70)
        print("Files copied successfully (plots skipped)")
        print("="*70)


if __name__ == "__main__":
    main()
