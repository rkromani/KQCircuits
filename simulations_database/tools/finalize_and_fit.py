"""
Automated post-processing script for HFSS wave equation simulations.

This script:
1. Finds all .s2p files in the tmp output folder
2. Copies them to the corresponding database results folders
3. Runs resonance fitting on all simulations
4. Generates plots and summaries

Usage:
    python finalize_and_fit.py <tmp_output_folder>

Example:
    python finalize_and_fit.py "C:/Roger/KQCircuits/tmp/spike_res_hfss_wave_sim_output"
"""

import argparse
import json
import logging
import shutil
import sys
from pathlib import Path

# Import the fitting script
from fit_s21_resonance import process_sweep_folder

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def find_database_folder(tmp_folder: Path) -> Path:
    """
    Find the database folder corresponding to the tmp output folder.

    Reads the simulation metadata to find where results should be copied.
    """
    # First, check for database reference file (created by simulation script)
    db_ref_file = tmp_folder / "database_folders.json"
    if db_ref_file.exists():
        with open(db_ref_file, 'r') as f:
            db_info = json.load(f)
            if 'sweep_folder' in db_info:
                db_folder = Path(db_info['sweep_folder'])
                logger.info(f"Found database folder from reference: {db_folder}")
                return db_folder

    # Alternative: look for simulation JSON files
    json_files = list(tmp_folder.glob("*_hfss.json"))

    if len(json_files) > 0:
        # Read first JSON to get database path
        with open(json_files[0], 'r') as f:
            sim_data = json.load(f)

        # The database path is stored in the simulation data
        # We need to reconstruct it from the simulation name
        if 'simulations' in sim_data and len(sim_data['simulations']) > 0:
            first_sim = sim_data['simulations'][0]
            if 'folder' in first_sim:
                db_folder = Path(first_sim['folder']).parent
                logger.info(f"Found database folder: {db_folder}")
                return db_folder

    logger.error(f"Could not find database reference in {tmp_folder}")
    return None


def copy_s2p_files(tmp_folder: Path, db_folder: Path) -> int:
    """
    Copy all .s2p files from tmp folder to database results folders.

    Returns:
        Number of files copied
    """
    if db_folder is None or not db_folder.exists():
        logger.error(f"Database folder does not exist: {db_folder}")
        return 0

    # Find all .s2p files in tmp folder
    s2p_files = list(tmp_folder.glob("*.s2p"))

    if len(s2p_files) == 0:
        logger.warning(f"No .s2p files found in {tmp_folder}")
        return 0

    logger.info(f"Found {len(s2p_files)} .s2p file(s) to copy")

    copied_count = 0

    for s2p_file in s2p_files:
        # Parse simulation name from S2P filename
        # Format: <sim_name>_project_SMatrix.s2p or similar
        s2p_stem = s2p_file.stem

        # Try to match with simulation folders in database
        # The simulation name is typically the prefix before "_project"
        sim_name_candidates = []

        if "_project" in s2p_stem:
            sim_name_candidates.append(s2p_stem.split("_project")[0])

        # Also try the stem with trailing underscore removed
        if s2p_stem.endswith("_"):
            sim_name_candidates.append(s2p_stem[:-1])
        else:
            sim_name_candidates.append(s2p_stem)

        # Find matching simulation folder in database
        sim_folder = None
        for candidate in sim_name_candidates:
            potential_folder = db_folder / candidate
            if potential_folder.exists():
                sim_folder = potential_folder
                break

        if sim_folder is None:
            # Try with trailing underscore
            for candidate in sim_name_candidates:
                potential_folder = db_folder / (candidate + "_")
                if potential_folder.exists():
                    sim_folder = potential_folder
                    break

        if sim_folder is None:
            logger.warning(f"Could not find database folder for {s2p_file.name}")
            logger.warning(f"  Tried: {sim_name_candidates}")
            continue

        # Create results folder if it doesn't exist
        results_folder = sim_folder / "results"
        results_folder.mkdir(exist_ok=True)

        # Determine destination filename (use simulation folder name)
        dest_filename = sim_folder.name + ".s2p"
        dest_path = results_folder / dest_filename

        # Copy file
        logger.info(f"  Copying {s2p_file.name} -> {sim_folder.name}/results/{dest_filename}")
        shutil.copy2(s2p_file, dest_path)
        copied_count += 1

    return copied_count


def save_database_reference(tmp_folder: Path, db_folder: Path):
    """
    Save a reference file in tmp folder pointing to database folder.
    This helps with future processing.
    """
    db_ref_file = tmp_folder / "database_folders.json"

    ref_data = {
        'sweep_folder': str(db_folder),
        'tmp_folder': str(tmp_folder),
    }

    with open(db_ref_file, 'w') as f:
        json.dump(ref_data, f, indent=2)


def main():
    parser = argparse.ArgumentParser(
        description='Finalize HFSS results and run resonance fitting'
    )
    parser.add_argument('tmp_folder', type=str,
                       help='Path to tmp output folder (e.g., tmp/spike_res_hfss_wave_sim_output)')
    parser.add_argument('--db-folder', type=str, default=None,
                       help='Path to database sweep folder (auto-detected if not specified)')
    parser.add_argument('--skip-fit', action='store_true',
                       help='Only copy files, skip fitting')

    args = parser.parse_args()

    tmp_folder = Path(args.tmp_folder)

    if not tmp_folder.exists():
        logger.error(f"Tmp folder not found: {tmp_folder}")
        sys.exit(1)

    logger.info(f"Processing tmp folder: {tmp_folder}")

    # Find or use specified database folder
    if args.db_folder:
        db_folder = Path(args.db_folder)
    else:
        db_folder = find_database_folder(tmp_folder)

    if db_folder is None:
        logger.error("Could not find database folder. Please specify with --db-folder")
        sys.exit(1)

    # Save reference for future use
    save_database_reference(tmp_folder, db_folder)

    # Copy .s2p files
    logger.info("\n=== Copying S-parameter files ===")
    copied_count = copy_s2p_files(tmp_folder, db_folder)

    if copied_count == 0:
        logger.error("No files were copied. Cannot proceed with fitting.")
        sys.exit(1)

    logger.info(f"Successfully copied {copied_count} file(s)")

    # Run fitting
    if not args.skip_fit:
        logger.info("\n=== Running resonance fitting ===")
        try:
            process_sweep_folder(db_folder)
        except Exception as e:
            logger.error(f"Fitting failed: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)

    logger.info("\n=== Processing complete! ===")
    logger.info(f"Results saved in: {db_folder}")


if __name__ == '__main__':
    main()
