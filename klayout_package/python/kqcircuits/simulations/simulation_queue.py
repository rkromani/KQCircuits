"""
Simulation Queue System - Core Module

Provides configuration-driven orchestration for running multiple ANSYS simulations
sequentially with optional parameter injection.

Key Features:
- Sequential execution of multiple simulation scripts
- Parameter injection via --sweep-override argument
- Progress tracking and logging
- Error handling with continue/stop modes
- Resume capability after interruption
- Automatic result finalization to database

Author: Generated for KQCircuits
Date: 2026-01-26
"""

import json
import subprocess
import sys
import re
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any
from datetime import datetime
import traceback


@dataclass
class SimulationRun:
    """
    Represents a single simulation run in the queue.

    Attributes:
        script: Path to the Python simulation script (relative to repo root)
        description: Human-readable description of what this run does
        args: Additional command-line arguments (e.g., ["--no-gui"])
        sweep_overrides: Optional dict to override sweep parameters
                        (e.g., {"finger_length": [5, 10, 20]})
        enabled: Whether this run should be executed
        status: Current status - "pending", "running", "completed", "failed"
        output_folder: Path where simulation files were exported (set during execution)
        bat_file: Path to generated .bat file (set during execution)
        start_time: When execution started (ISO format)
        end_time: When execution finished (ISO format)
        duration_seconds: How long the run took
        error_message: Error details if status is "failed"
        exit_code: Exit code from batch file execution
    """
    script: str
    description: str
    args: List[str] = field(default_factory=list)
    sweep_overrides: Optional[Dict[str, Any]] = None
    enabled: bool = True
    status: str = "pending"
    output_folder: Optional[str] = None
    bat_file: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    duration_seconds: Optional[float] = None
    error_message: Optional[str] = None
    exit_code: Optional[int] = None

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> 'SimulationRun':
        """Create from dictionary (JSON deserialization)."""
        return cls(**data)


class SimulationQueue:
    """
    Manages a queue of simulation runs for sequential execution.

    Usage:
        queue = SimulationQueue("evening_parameter_study")
        queue.add_run("scripts/simulations/finger_cap_q3d_sim.py",
                     "Sweep finger length",
                     sweep_overrides={"finger_length": [5, 10, 20]},
                     args=["--no-gui"])
        queue.save("sim_queue.json")
        queue.execute()
    """

    def __init__(self, queue_name: str, error_handling: str = "continue"):
        """
        Initialize simulation queue.

        Args:
            queue_name: Name for this queue (used in logging)
            error_handling: "continue" to keep going after errors, "stop" to halt
        """
        self.queue_name = queue_name
        self.error_handling = error_handling
        self.runs: List[SimulationRun] = []
        self.created_at: str = datetime.now().isoformat()
        self.log_file: Optional[Path] = None

    def add_run(self, script: str, description: str,
                sweep_overrides: Optional[Dict[str, Any]] = None,
                args: Optional[List[str]] = None,
                enabled: bool = True) -> None:
        """
        Add a simulation run to the queue.

        Args:
            script: Path to simulation script (relative to repo root)
            description: Description of this run
            sweep_overrides: Optional parameter overrides for sweep
            args: Additional command-line arguments
            enabled: Whether to execute this run
        """
        run = SimulationRun(
            script=script,
            description=description,
            args=args or [],
            sweep_overrides=sweep_overrides,
            enabled=enabled
        )
        self.runs.append(run)

    def save(self, filepath: str) -> None:
        """
        Save queue configuration to JSON file.

        Args:
            filepath: Path to JSON file to create
        """
        data = {
            "queue_name": self.queue_name,
            "created_at": self.created_at,
            "error_handling": self.error_handling,
            "runs": [run.to_dict() for run in self.runs]
        }

        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)

        print(f"Queue configuration saved to: {filepath}")

    @classmethod
    def load(cls, filepath: str) -> 'SimulationQueue':
        """
        Load queue configuration from JSON file.

        Args:
            filepath: Path to JSON file

        Returns:
            SimulationQueue instance
        """
        with open(filepath, 'r') as f:
            data = json.load(f)

        queue = cls(data["queue_name"], data.get("error_handling", "continue"))
        queue.created_at = data.get("created_at", datetime.now().isoformat())
        queue.runs = [SimulationRun.from_dict(run_data) for run_data in data["runs"]]

        return queue

    def _log(self, message: str, also_print: bool = True) -> None:
        """
        Log message to console and log file.

        Args:
            message: Message to log
            also_print: Whether to also print to console
        """
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_line = f"[{timestamp}] {message}"

        if also_print:
            print(log_line)

        if self.log_file:
            with open(self.log_file, 'a') as f:
                f.write(log_line + "\n")

    def _setup_logging(self) -> None:
        """Create log file for this queue execution."""
        log_dir = Path("tmp/queue_logs")
        log_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = log_dir / f"{self.queue_name}_{timestamp}.log"

        self._log(f"Log file: {self.log_file}")

    def _build_command(self, run: SimulationRun) -> List[str]:
        """
        Build command to execute simulation script.

        Args:
            run: SimulationRun to build command for

        Returns:
            Command as list of strings for subprocess
        """
        # Start with python executable and script path
        cmd = [sys.executable, run.script]

        # Add sweep overrides if provided
        if run.sweep_overrides:
            override_json = json.dumps(run.sweep_overrides)
            cmd.extend(["--sweep-override", override_json])

        # Add any additional arguments
        cmd.extend(run.args)

        return cmd

    def _parse_output_folder(self, stdout: str) -> Optional[str]:
        """
        Parse output folder path from script stdout.

        Looks for pattern: "Exported .* simulation files to: (.+)"

        Args:
            stdout: Standard output from script execution

        Returns:
            Path to output folder or None if not found
        """
        # Look for export message
        pattern = r"Exported .* simulation files to:\s*(.+)"
        match = re.search(pattern, stdout)

        if match:
            folder = match.group(1).strip()
            return folder

        return None

    def _find_batch_file(self, output_folder: str) -> Optional[Path]:
        """
        Find the generated batch file in output folder.

        Args:
            output_folder: Path to simulation output folder

        Returns:
            Path to batch file or None if not found
        """
        folder_path = Path(output_folder)

        # Look for simulation.bat (default name from export_ansys)
        bat_file = folder_path / "simulation.bat"

        if bat_file.exists():
            return bat_file

        # Fallback: look for any .bat file
        bat_files = list(folder_path.glob("*.bat"))
        if bat_files:
            return bat_files[0]

        return None

    def _execute_python_script(self, run: SimulationRun) -> bool:
        """
        Execute the Python simulation script.

        Args:
            run: SimulationRun to execute

        Returns:
            True if successful, False otherwise
        """
        cmd = self._build_command(run)

        self._log(f"Executing: {' '.join(cmd)}")

        try:
            # Execute script and capture output
            # Auto-answer 'y' to any prompts (like "overwrite existing results?")
            result = subprocess.run(
                cmd,
                input='y\n',  # Auto-confirm prompts
                capture_output=True,
                text=True,
                check=False,
                cwd=Path.cwd()
            )

            # Log output
            if result.stdout:
                print(result.stdout)
                if self.log_file:
                    with open(self.log_file, 'a') as f:
                        f.write(result.stdout + "\n")

            if result.stderr:
                print(result.stderr, file=sys.stderr)
                if self.log_file:
                    with open(self.log_file, 'a') as f:
                        f.write("STDERR:\n" + result.stderr + "\n")

            # Check for errors
            if result.returncode != 0:
                run.error_message = f"Script failed with exit code {result.returncode}"
                run.exit_code = result.returncode
                return False

            # Parse output folder from stdout
            output_folder = self._parse_output_folder(result.stdout)

            if not output_folder:
                run.error_message = "Could not find output folder in script output"
                return False

            run.output_folder = output_folder
            self._log(f"Output folder: {output_folder}")

            return True

        except Exception as e:
            run.error_message = f"Exception during script execution: {str(e)}\n{traceback.format_exc()}"
            self._log(f"ERROR: {run.error_message}")
            return False

    def _execute_batch_file(self, run: SimulationRun) -> bool:
        """
        Execute the ANSYS batch file.

        Args:
            run: SimulationRun with batch file to execute

        Returns:
            True if successful, False otherwise
        """
        # Find batch file
        bat_file = self._find_batch_file(run.output_folder)

        if not bat_file:
            run.error_message = f"Could not find batch file in {run.output_folder}"
            self._log(f"ERROR: {run.error_message}")
            return False

        run.bat_file = str(bat_file)
        self._log(f"Batch file: {bat_file}")
        self._log("Executing ANSYS simulations (this may take a while)...")

        try:
            # Execute batch file
            result = subprocess.run(
                [str(bat_file)],
                capture_output=True,
                text=True,
                check=False,
                cwd=bat_file.parent
            )

            # Log batch file output
            if self.log_file:
                with open(self.log_file, 'a') as f:
                    f.write(f"\n=== Batch file output ===\n")
                    if result.stdout:
                        f.write(result.stdout + "\n")
                    if result.stderr:
                        f.write("STDERR:\n" + result.stderr + "\n")

            # Check exit code
            run.exit_code = result.returncode

            if result.returncode != 0:
                run.error_message = f"Batch file failed with exit code {result.returncode}"
                self._log(f"ERROR: {run.error_message}")
                return False

            self._log("ANSYS simulations completed successfully")
            return True

        except Exception as e:
            run.error_message = f"Exception during batch execution: {str(e)}\n{traceback.format_exc()}"
            self._log(f"ERROR: {run.error_message}")
            return False

    def _execute_run(self, run: SimulationRun, run_number: int, total_runs: int) -> bool:
        """
        Execute a single simulation run.

        Args:
            run: SimulationRun to execute
            run_number: Current run number (1-indexed)
            total_runs: Total number of runs in queue

        Returns:
            True if successful, False otherwise
        """
        # Print run header
        print("\n" + "=" * 60)
        print(f"Run {run_number}/{total_runs}: {run.description}")
        print(f"Script: {run.script}")
        if run.sweep_overrides:
            print(f"Sweep overrides: {json.dumps(run.sweep_overrides)}")
        print("=" * 60 + "\n")

        # Update status and timing
        run.status = "running"
        run.start_time = datetime.now().isoformat()
        start = datetime.now()

        # Execute Python script
        if not self._execute_python_script(run):
            run.status = "failed"
            run.end_time = datetime.now().isoformat()
            run.duration_seconds = (datetime.now() - start).total_seconds()
            self._log(f"Status: FAILED ✗")
            return False

        # Execute batch file
        if not self._execute_batch_file(run):
            run.status = "failed"
            run.end_time = datetime.now().isoformat()
            run.duration_seconds = (datetime.now() - start).total_seconds()
            self._log(f"Status: FAILED ✗")
            return False

        # Success
        run.status = "completed"
        run.end_time = datetime.now().isoformat()
        run.duration_seconds = (datetime.now() - start).total_seconds()

        self._log(f"Status: COMPLETED ✓")
        self._log(f"Duration: {run.duration_seconds:.1f} seconds")

        return True

    def execute(self, resume: bool = False) -> Dict[str, Any]:
        """
        Execute all runs in the queue sequentially.

        Args:
            resume: If True, skip completed runs and resume from next pending

        Returns:
            Summary dictionary with execution results
        """
        self._setup_logging()

        # Filter enabled runs
        enabled_runs = [run for run in self.runs if run.enabled]

        if not enabled_runs:
            self._log("No enabled runs in queue")
            return {"status": "empty", "runs_completed": 0, "runs_failed": 0}

        # Filter for resume mode
        if resume:
            pending_runs = [run for run in enabled_runs if run.status == "pending"]
            completed_count = len([run for run in enabled_runs if run.status == "completed"])

            self._log(f"Resume mode: {completed_count} runs already completed")
            runs_to_execute = pending_runs
        else:
            runs_to_execute = enabled_runs

        total_runs = len(runs_to_execute)

        self._log(f"Starting queue: {self.queue_name}")
        self._log(f"Total runs: {total_runs}")
        self._log(f"Error handling: {self.error_handling}")

        # Execute each run
        runs_completed = 0
        runs_failed = 0

        for idx, run in enumerate(runs_to_execute, 1):
            success = self._execute_run(run, idx, total_runs)

            if success:
                runs_completed += 1
            else:
                runs_failed += 1

                # Handle error based on policy
                if self.error_handling == "stop":
                    self._log("\nError handling set to 'stop' - halting queue")
                    break
                else:
                    self._log("\nError handling set to 'continue' - proceeding to next run")

        # Final summary
        print("\n" + "=" * 60)
        print("QUEUE EXECUTION COMPLETE")
        print("=" * 60)
        self._log(f"Runs completed: {runs_completed}")
        self._log(f"Runs failed: {runs_failed}")

        # Show results
        print("\nResults:")
        for run in enabled_runs:
            status_symbol = "✓" if run.status == "completed" else "✗" if run.status == "failed" else "○"
            print(f"  {status_symbol} {run.description}")
            if run.output_folder:
                print(f"    Output: {run.output_folder}")
            if run.error_message:
                print(f"    Error: {run.error_message}")

        return {
            "status": "completed",
            "runs_completed": runs_completed,
            "runs_failed": runs_failed,
            "total_runs": total_runs
        }

    def save_state(self, filepath: str) -> None:
        """
        Save current queue state (including run statuses).

        Used for resume capability.

        Args:
            filepath: Path to save state file
        """
        self.save(filepath)
