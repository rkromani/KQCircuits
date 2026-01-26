"""
Simulation Queue Runner - Command-Line Interface

Execute a queue of ANSYS simulations sequentially from a JSON configuration file.

Usage:
    python run_simulation_queue.py sim_queue.json              # Normal run
    python run_simulation_queue.py sim_queue.json --dry-run    # Preview only
    python run_simulation_queue.py sim_queue.json --yes        # Skip confirmation
    python run_simulation_queue.py sim_queue.json --resume     # Resume after failure

Author: Generated for KQCircuits
Date: 2026-01-26
"""

import argparse
import sys
import json
from pathlib import Path

# Add klayout_package to path (go up to repo root, then down to klayout_package)
sys.path.insert(0, str(Path(__file__).parent.parent / "klayout_package" / "python"))

from kqcircuits.simulations.simulation_queue import SimulationQueue


def display_queue_summary(queue: SimulationQueue) -> None:
    """
    Display a summary of the queue before execution.

    Args:
        queue: SimulationQueue to summarize
    """
    print("\n" + "=" * 70)
    print(f"Queue: {queue.queue_name}")
    print("=" * 70)

    enabled_runs = [run for run in queue.runs if run.enabled]

    print(f"\nTotal runs: {len(enabled_runs)}")
    print(f"Error handling: {queue.error_handling}")

    if queue.error_handling == "continue":
        print("  (Will continue to next run if one fails)")
    else:
        print("  (Will stop entire queue if one fails)")

    print("\nRuns:")
    for idx, run in enumerate(enabled_runs, 1):
        status_info = ""
        if run.status != "pending":
            status_info = f" [{run.status.upper()}]"

        print(f"\n  {idx}. {run.description}{status_info}")
        print(f"     Script: {run.script}")

        if run.sweep_overrides:
            print(f"     Sweep overrides: {json.dumps(run.sweep_overrides, indent=16)[0:100]}...")

        if run.args:
            print(f"     Args: {' '.join(run.args)}")

    print("\n" + "=" * 70)


def confirm_execution() -> bool:
    """
    Ask user to confirm execution.

    Returns:
        True if user confirms, False otherwise
    """
    response = input("\nProceed with execution? [y/N]: ").strip().lower()
    return response == 'y' or response == 'yes'


def main():
    """Main entry point for queue runner."""
    parser = argparse.ArgumentParser(
        description="Execute a queue of ANSYS simulations sequentially",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_simulation_queue.py sim_queue.json
  python run_simulation_queue.py sim_queue.json --dry-run
  python run_simulation_queue.py sim_queue.json --yes
  python run_simulation_queue.py sim_queue.json --resume

For more information, see the implementation plan documentation.
        """
    )

    parser.add_argument(
        "queue_file",
        type=str,
        help="Path to queue configuration JSON file"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview queue without executing"
    )

    parser.add_argument(
        "--yes", "-y",
        action="store_true",
        help="Skip confirmation prompt"
    )

    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume execution, skipping completed runs"
    )

    parser.add_argument(
        "--save-state",
        type=str,
        default=None,
        help="Save queue state to file after execution (for resume capability)"
    )

    args = parser.parse_args()

    # Check if queue file exists
    queue_file = Path(args.queue_file)
    if not queue_file.exists():
        print(f"ERROR: Queue file not found: {queue_file}", file=sys.stderr)
        sys.exit(1)

    # Load queue
    try:
        print(f"Loading queue from: {queue_file}")
        queue = SimulationQueue.load(str(queue_file))
    except Exception as e:
        print(f"ERROR: Failed to load queue file: {e}", file=sys.stderr)
        sys.exit(1)

    # Display summary
    display_queue_summary(queue)

    # Dry run mode - just show summary and exit
    if args.dry_run:
        print("\n[DRY RUN MODE - No simulations will be executed]")
        return

    # Resume mode info
    if args.resume:
        completed = len([r for r in queue.runs if r.enabled and r.status == "completed"])
        if completed > 0:
            print(f"\n[RESUME MODE - {completed} runs already completed, will skip]")
        else:
            print("\n[RESUME MODE - No completed runs found, will run all]")

    # Confirm execution (unless --yes flag)
    if not args.yes:
        if not confirm_execution():
            print("Execution cancelled.")
            return

    # Execute queue
    print("\n" + "=" * 70)
    print("STARTING QUEUE EXECUTION")
    print("=" * 70 + "\n")

    try:
        summary = queue.execute(resume=args.resume)

        # Save state if requested
        if args.save_state:
            queue.save_state(args.save_state)
            print(f"\nQueue state saved to: {args.save_state}")

        # Exit with appropriate code
        if summary["runs_failed"] > 0:
            print(f"\nWARNING: {summary['runs_failed']} runs failed")
            sys.exit(1)
        else:
            print("\nAll runs completed successfully!")
            sys.exit(0)

    except KeyboardInterrupt:
        print("\n\nExecution interrupted by user")

        # Save state for resume
        state_file = f"{queue.queue_name}_interrupted_state.json"
        queue.save_state(state_file)
        print(f"Queue state saved to: {state_file}")
        print(f"Resume with: python run_simulation_queue.py {state_file} --resume")

        sys.exit(130)

    except Exception as e:
        print(f"\nERROR: Unexpected exception during execution: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()

        # Save state for debugging
        state_file = f"{queue.queue_name}_error_state.json"
        queue.save_state(state_file)
        print(f"Queue state saved to: {state_file}")

        sys.exit(1)


if __name__ == "__main__":
    main()
