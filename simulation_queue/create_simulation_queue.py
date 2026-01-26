"""
Simulation Queue Builder - Example Templates

Create simulation queue configurations programmatically.

This script provides examples of different queue configurations:
1. Simple queue - Multiple different simulation scripts
2. Parameter sweep - Same script with different parameter overrides
3. Mixed queue - Combination of different scripts and parameter sweeps

Usage:
    python create_simulation_queue.py                    # Interactive mode
    python create_simulation_queue.py --example simple   # Generate simple example
    python create_simulation_queue.py --example sweep    # Generate parameter sweep example
    python create_simulation_queue.py --example mixed    # Generate mixed example

Author: Generated for KQCircuits
Date: 2026-01-26
"""

import argparse
import sys
from pathlib import Path

# Add klayout_package to path (go up to repo root, then down to klayout_package)
sys.path.insert(0, str(Path(__file__).parent.parent / "klayout_package" / "python"))

from kqcircuits.simulations.simulation_queue import SimulationQueue


def create_simple_queue() -> SimulationQueue:
    """
    Create a simple queue with multiple different simulation scripts.

    Example: Run capacitance and inductance simulations for spike resonator.
    """
    queue = SimulationQueue("multi_design_study", error_handling="continue")

    # Add spike resonator capacitance simulation
    queue.add_run(
        script="klayout_package/python/scripts/simulations/spike_res_q3d_sim.py",
        description="Spike resonator - capacitance (Q3D)",
        args=["--no-gui"],
        enabled=True
    )

    # Add spike resonator inductance simulation
    queue.add_run(
        script="klayout_package/python/scripts/simulations/spike_res_acrl_sim.py",
        description="Spike resonator - inductance (Q3D+ACRL)",
        args=["--no-gui"],
        enabled=True
    )

    return queue


def create_parameter_sweep_queue() -> SimulationQueue:
    """
    Create a queue that runs the same script with different parameter sweeps.

    Example: Sweep finger length, width, and gap for finger capacitor.
    This is the RECOMMENDED approach for parameter studies.
    """
    queue = SimulationQueue("finger_cap_parameter_study", error_handling="continue")

    # Sweep 1: Finger length
    queue.add_run(
        script="klayout_package/python/scripts/simulations/finger_cap_q3d_sim.py",
        description="Sweep finger length (5-100 µm)",
        sweep_overrides={"finger_length": [5, 10, 20, 50, 100]},
        args=["--no-gui"],
        enabled=True
    )

    # Sweep 2: Finger width
    queue.add_run(
        script="klayout_package/python/scripts/simulations/finger_cap_q3d_sim.py",
        description="Sweep finger width (1-5 µm)",
        sweep_overrides={"finger_width": [1, 2, 3, 4, 5]},
        args=["--no-gui"],
        enabled=True
    )

    # Sweep 3: Gap width
    queue.add_run(
        script="klayout_package/python/scripts/simulations/finger_cap_q3d_sim.py",
        description="Sweep gap width (10-25 µm)",
        sweep_overrides={"gap_width": [10, 15, 20, 25]},
        args=["--no-gui"],
        enabled=True
    )

    return queue


def create_mixed_queue() -> SimulationQueue:
    """
    Create a queue with both different scripts and parameter sweeps.

    Example: Run multiple designs with parameter variations.
    """
    queue = SimulationQueue("evening_batch_run", error_handling="continue")

    # Different design 1: Spike resonator with spike number sweep
    queue.add_run(
        script="klayout_package/python/scripts/simulations/spike_res_q3d_sim.py",
        description="Spike resonator - spike number sweep",
        sweep_overrides={"n_spikes": [1, 2, 3, 5, 8]},
        args=["--no-gui"],
        enabled=True
    )

    # Different design 2: Finger capacitor with finger count sweep
    queue.add_run(
        script="klayout_package/python/scripts/simulations/finger_cap_q3d_sim.py",
        description="Finger capacitor - finger count sweep",
        sweep_overrides={"n_fingers": [4, 8, 12, 16, 20]},
        args=["--no-gui"],
        enabled=True
    )

    # Different design 3: Spike resonator inductance (no sweep)
    queue.add_run(
        script="klayout_package/python/scripts/simulations/spike_res_acrl_sim.py",
        description="Spike resonator - inductance baseline",
        args=["--no-gui"],
        enabled=True
    )

    return queue


def create_test_queue() -> SimulationQueue:
    """
    Create a minimal test queue with fast simulations.

    Use this to verify the queue system is working.
    """
    queue = SimulationQueue("test_queue", error_handling="stop")

    # Just one simple simulation
    queue.add_run(
        script="klayout_package/python/scripts/simulations/finger_cap_q3d_sim.py",
        description="Test run - finger capacitor baseline",
        sweep_overrides={"finger_length": [10, 20]},  # Just 2 points for speed
        args=["--no-gui"],
        enabled=True
    )

    return queue


def interactive_mode():
    """
    Interactive mode - ask user which example to create.
    """
    print("\n" + "=" * 70)
    print("Simulation Queue Builder - Interactive Mode")
    print("=" * 70)

    print("\nAvailable examples:")
    print("  1. Simple queue - Multiple different scripts")
    print("  2. Parameter sweep - Same script with different parameters (RECOMMENDED)")
    print("  3. Mixed queue - Combination of scripts and parameter sweeps")
    print("  4. Test queue - Minimal test configuration")

    choice = input("\nSelect example (1-4): ").strip()

    if choice == "1":
        queue = create_simple_queue()
        filename = "simple_queue.json"
    elif choice == "2":
        queue = create_parameter_sweep_queue()
        filename = "parameter_sweep_queue.json"
    elif choice == "3":
        queue = create_mixed_queue()
        filename = "mixed_queue.json"
    elif choice == "4":
        queue = create_test_queue()
        filename = "test_queue.json"
    else:
        print("Invalid choice. Exiting.")
        return

    # Ask for custom filename
    custom_name = input(f"\nSave as [{filename}]: ").strip()
    if custom_name:
        filename = custom_name if custom_name.endswith(".json") else custom_name + ".json"

    # Save queue
    queue.save(filename)

    print(f"\nQueue configuration saved to: {filename}")
    print(f"\nTo execute: python run_simulation_queue.py {filename}")
    print(f"To preview: python run_simulation_queue.py {filename} --dry-run")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Create simulation queue configurations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python create_simulation_queue.py                    # Interactive mode
  python create_simulation_queue.py --example simple   # Simple queue
  python create_simulation_queue.py --example sweep    # Parameter sweep
  python create_simulation_queue.py --example mixed    # Mixed queue
  python create_simulation_queue.py --example test     # Test queue

The generated JSON file can be executed with:
  python run_simulation_queue.py <queue_file>.json

For more information, see the implementation plan documentation.
        """
    )

    parser.add_argument(
        "--example",
        type=str,
        choices=["simple", "sweep", "mixed", "test"],
        help="Generate specific example (simple, sweep, mixed, or test)"
    )

    parser.add_argument(
        "--output", "-o",
        type=str,
        default=None,
        help="Output filename (default: auto-generated based on example type)"
    )

    args = parser.parse_args()

    # Interactive mode if no example specified
    if not args.example:
        interactive_mode()
        return

    # Generate requested example
    if args.example == "simple":
        queue = create_simple_queue()
        default_filename = "simple_queue.json"
    elif args.example == "sweep":
        queue = create_parameter_sweep_queue()
        default_filename = "parameter_sweep_queue.json"
    elif args.example == "mixed":
        queue = create_mixed_queue()
        default_filename = "mixed_queue.json"
    elif args.example == "test":
        queue = create_test_queue()
        default_filename = "test_queue.json"

    # Determine output filename
    filename = args.output if args.output else default_filename
    if not filename.endswith(".json"):
        filename += ".json"

    # Save queue
    queue.save(filename)

    print(f"\n{'='*70}")
    print(f"Queue configuration created: {filename}")
    print(f"{'='*70}\n")

    print("Next steps:")
    print(f"  1. Review:  python run_simulation_queue.py {filename} --dry-run")
    print(f"  2. Execute: python run_simulation_queue.py {filename}")
    print(f"  3. Or edit: {filename} (JSON format)\n")


if __name__ == "__main__":
    main()
