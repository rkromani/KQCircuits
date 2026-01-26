# Simulation Queue System - Quick Start Guide

## Overview

The simulation queue system allows you to run multiple ANSYS simulations sequentially without manual intervention. The key feature is **parameter injection**, which lets you run the same simulation script with different sweep parameters.

## Basic Workflow

### 1. Create a Queue Configuration

Three options:

**Option A: Generate from examples**
```bash
python create_simulation_queue.py --example sweep -o my_queue.json
```

**Option B: Interactive mode**
```bash
python create_simulation_queue.py
```

**Option C: Manual JSON editing**
Edit any generated `.json` file directly.

### 2. Preview the Queue

```bash
python run_simulation_queue.py my_queue.json --dry-run
```

### 3. Execute the Queue

```bash
python run_simulation_queue.py my_queue.json
```

The queue will:
1. Run each simulation script with optional parameter overrides
2. Execute the generated ANSYS batch files automatically
3. Save results to the database
4. Continue to the next run (or stop on error, depending on settings)

## Queue Configuration Format

```json
{
  "queue_name": "my_study",
  "error_handling": "continue",
  "runs": [
    {
      "script": "klayout_package/python/scripts/simulations/finger_cap_q3d_sim.py",
      "description": "Sweep finger length",
      "sweep_overrides": {"finger_length": [5, 10, 20, 50, 100]},
      "args": ["--no-gui"],
      "enabled": true
    }
  ]
}
```

### Key Fields

- **queue_name**: Name for this batch run (used in logging)
- **error_handling**: `"continue"` (keep going after errors) or `"stop"` (halt on first error)
- **runs**: Array of simulation runs

Each run has:
- **script**: Path to simulation script (relative to repo root)
- **description**: Human-readable description
- **sweep_overrides**: Optional dict to override sweep parameters
- **args**: Additional command-line arguments (e.g., `["--no-gui"]`)
- **enabled**: Whether to run this simulation (true/false)

## Parameter Injection Feature

The **parameter injection** feature allows you to run the same script multiple times with different parameter sweeps. This is the recommended approach for parameter studies.

### Example: Multiple Parameter Sweeps

```json
{
  "queue_name": "finger_cap_full_study",
  "runs": [
    {
      "script": "klayout_package/python/scripts/simulations/finger_cap_q3d_sim.py",
      "description": "Sweep finger length (5-100 µm)",
      "sweep_overrides": {"finger_length": [5, 10, 20, 50, 100]},
      "args": ["--no-gui"]
    },
    {
      "script": "klayout_package/python/scripts/simulations/finger_cap_q3d_sim.py",
      "description": "Sweep finger width (1-5 µm)",
      "sweep_overrides": {"finger_width": [1, 2, 3, 4, 5]},
      "args": ["--no-gui"]
    },
    {
      "script": "klayout_package/python/scripts/simulations/finger_cap_q3d_sim.py",
      "description": "Sweep gap width (10-25 µm)",
      "sweep_overrides": {"gap_width": [10, 15, 20, 25]},
      "args": ["--no-gui"]
    }
  ]
}
```

This runs the **same script three times** with different parameters. No need to duplicate scripts!

### Supported Scripts (with --sweep-override)

The following scripts now support parameter injection:

1. **finger_cap_q3d_sim.py**
   - Override: `finger_length`, `finger_width`, `gap_width`, etc.

2. **spike_res_q3d_sim.py**
   - Override: `spike_number`, `spike_gap`, `spike_height`, `spike_base_width`, etc.

3. **spike_res_acrl_sim.py**
   - Override: `l_coupling_distance`, `l_coupling_length`, `feedline_spacing`, etc.

## Command-Line Options

### create_simulation_queue.py

```bash
# Generate example configurations
python create_simulation_queue.py --example simple     # Multiple different scripts
python create_simulation_queue.py --example sweep      # Same script, different parameters
python create_simulation_queue.py --example mixed      # Combination
python create_simulation_queue.py --example test       # Minimal test queue

# Custom output file
python create_simulation_queue.py --example sweep -o my_queue.json

# Interactive mode (asks which example to create)
python create_simulation_queue.py
```

### run_simulation_queue.py

```bash
# Normal execution (asks for confirmation)
python run_simulation_queue.py my_queue.json

# Skip confirmation
python run_simulation_queue.py my_queue.json --yes

# Preview without executing
python run_simulation_queue.py my_queue.json --dry-run

# Resume after interruption
python run_simulation_queue.py my_queue.json --resume

# Save state for later resume
python run_simulation_queue.py my_queue.json --save-state my_state.json
```

## Example Workflows

### Scenario 1: Overnight Parameter Study

You want to sweep three parameters for finger capacitor simulations. Each sweep takes 2-3 hours.

```bash
# 1. Create queue
python create_simulation_queue.py --example sweep -o overnight_run.json

# 2. Edit if needed (optional)
# Edit overnight_run.json to adjust parameter ranges

# 3. Preview
python run_simulation_queue.py overnight_run.json --dry-run

# 4. Start and walk away
python run_simulation_queue.py overnight_run.json

# All simulations run automatically!
# Results saved to C:\Roger\Sim_Results\ as each completes
```

### Scenario 2: Multiple Design Comparison

You want to compare capacitance and inductance for spike resonators.

```bash
# 1. Create simple queue
python create_simulation_queue.py --example simple -o comparison.json

# 2. Run
python run_simulation_queue.py comparison.json
```

### Scenario 3: Resume After Interruption

Queue was interrupted (power failure, Ctrl+C, etc.).

```bash
# Resume from where it left off
python run_simulation_queue.py my_queue.json --resume

# Or use auto-saved state file
python run_simulation_queue.py my_study_interrupted_state.json --resume
```

## Progress Tracking

The queue system provides real-time progress updates:

```
[10:30:00] Starting queue: evening_parameter_study
[10:30:00] Total runs: 3

========================================
Run 1/3: Sweep finger length (5-100 µm)
Script: finger_cap_q3d_sim.py
Sweep overrides: {"finger_length": [5, 10, 20, 50, 100]}
========================================

[10:30:05] Executing: python finger_cap_q3d_sim.py --sweep-override '{"finger_length": [5, 10, 20, 50, 100]}' --no-gui
[10:30:10] Applied sweep overrides: {"finger_length": [5, 10, 20, 50, 100]}
[10:30:10] Generated 5 simulations
[10:30:10] Output: tmp/finger_cap_q3d_sim_output
[10:30:10] Executing ANSYS simulations...
[11:30:45] ANSYS simulations complete
[11:30:52] Results finalized to database
[11:30:52] Status: COMPLETED ✓
[11:30:52] Duration: 3637.0 seconds

========================================
Run 2/3: Sweep finger width (1-5 µm)
...
```

## Log Files

Detailed logs are saved to:
```
tmp/queue_logs/<queue_name>_<timestamp>.log
```

## Results

Results are automatically saved to the database as each simulation completes:
```
C:\Roger\Sim_Results\
├── finger_cap_grounded\
│   ├── 20260126_103010_finger_length_sweep_q3d\
│   ├── 20260126_113055_finger_width_sweep_q3d\
│   └── 20260126_143420_gap_width_sweep_q3d\
└── spike_resonator\
    └── 20260126_153045_spike_number_sweep_q3d\
```

## Tips

1. **Use parameter injection**: Run the same script with different `sweep_overrides` rather than duplicating scripts.

2. **Test first**: Create a test queue with just 2-3 simulation points to verify everything works.

3. **Use --dry-run**: Always preview your queue before running overnight batches.

4. **Error handling**: Use `"error_handling": "continue"` for exploratory parameter sweeps where partial results are useful. Use `"stop"` for dependent simulations.

5. **Save state**: For long-running queues, use `--save-state` to enable easy resume if interrupted.

6. **Check logs**: If a run fails, check `tmp/queue_logs/<queue_name>_<timestamp>.log` for detailed error messages.

## Troubleshooting

### "Could not find output folder in script output"

The script didn't print the expected output pattern. Make sure the script uses `export_ansys()` and prints the output folder.

### "Could not find batch file"

The simulation script didn't generate a `.bat` file. Check that `export_ansys()` was called with correct parameters.

### "Script failed with exit code 1"

The simulation script itself failed. Run the script manually to debug:
```bash
python klayout_package/python/scripts/simulations/<script_name>.py
```

### Module import errors

Make sure you're using the correct Python environment:
```bash
# Use the virtual environment
C:/Roger/KQCircuits/env-kqcircuits-py312/Scripts/python.exe run_simulation_queue.py my_queue.json
```

## Advanced: Adding --sweep-override to Other Scripts

To add parameter injection support to additional simulation scripts:

1. **Add argument to parser**:
```python
parser.add_argument("--sweep-override", type=str, default=None,
                    help="Override sweep parameters as JSON")
```

2. **Add merge logic before cross_sweep_simulation**:
```python
import json

# Define base sweep parameters
sweep_params = {
    "param1": [1, 2, 3],
    "param2": [10, 20, 30],
}

# Apply overrides if provided
if args.sweep_override:
    try:
        sweep_overrides = json.loads(args.sweep_override)
        sweep_params.update(sweep_overrides)
        print(f"Applied sweep overrides: {sweep_overrides}")
    except json.JSONDecodeError as e:
        print(f"Warning: Could not parse sweep overrides: {e}")

# Use merged sweep_params
simulations = cross_sweep_simulation(layout, SimClass, sim_parameters, sweep_params)
```

That's it! The script now supports parameter injection.

## Summary

The simulation queue system provides:
- ✅ Sequential execution of multiple simulations
- ✅ Parameter injection for flexible parameter studies
- ✅ Automatic result finalization to database
- ✅ Progress tracking and logging
- ✅ Resume capability after interruption
- ✅ Simple JSON configuration format
- ✅ Minimal modifications to existing scripts

**Key benefit**: Set up a multi-hour parameter study in 2 minutes, walk away, and have all results waiting in the database the next morning!
