# Simulation Queue System

Automated sequential execution of ANSYS simulations with parameter injection support.

## Quick Start

```bash
# From the repo root, create a queue
python simulation_queue/create_simulation_queue.py --example sweep -o my_queue.json

# Preview it
python simulation_queue/run_simulation_queue.py my_queue.json --dry-run

# Run it
python simulation_queue/run_simulation_queue.py my_queue.json
```

## Files

- **`run_simulation_queue.py`** - Execute simulation queues
- **`create_simulation_queue.py`** - Create queue configurations
- **`QUICKSTART.md`** - Comprehensive user guide
- **`examples/`** - Example queue configurations

## Example Configurations

The `examples/` folder contains:

- **`test_queue.json`** - Minimal test with 2 simulation points
- **`parameter_sweep_example.json`** - Same script with 3 different parameter sweeps
- **`simple_queue_example.json`** - Multiple different simulation scripts

You can use these as templates or generate new ones:

```bash
python simulation_queue/create_simulation_queue.py --example test
python simulation_queue/create_simulation_queue.py --example sweep
python simulation_queue/create_simulation_queue.py --example simple
python simulation_queue/create_simulation_queue.py --example mixed
```

## Documentation

See **`QUICKSTART.md`** for:
- Complete usage guide
- Configuration format reference
- Parameter injection examples
- Troubleshooting tips
- Advanced workflows

## Core Implementation

The queue system is implemented in:
```
klayout_package/python/kqcircuits/simulations/simulation_queue.py
```

Simulation scripts with `--sweep-override` support:
- `finger_cap_q3d_sim.py`
- `spike_res_q3d_sim.py`
- `spike_res_acrl_sim.py`

## Key Features

✅ Sequential execution of multiple simulations
✅ Parameter injection (run same script with different sweeps)
✅ Automatic result saving to database
✅ Progress tracking and logging
✅ Resume capability after interruption
✅ Error handling (continue or stop modes)
✅ Dry-run preview mode
