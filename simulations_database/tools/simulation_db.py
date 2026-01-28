"""
Simulation Database Manager

Simple tool to organize ANSYS simulation results with metadata.
"""

import json
import os
import shutil
from datetime import datetime
from pathlib import Path


class SimulationDB:
    """
    Manages simulation file organization and metadata storage.

    Usage:
        db = SimulationDB()
        db_folders = db.register_simulations(
            simulations=simulations,
            design_name='spike_resonator',
            sim_parameters=sim_parameters,
            export_parameters=export_parameters,
            output_folder='tmp/spike_res_q3d_sim_output'
        )
    """

    def __init__(self, base_path=None):
        """
        Initialize database manager.

        Args:
            base_path: Root directory for database (default: simulations_database/ in repo root)
        """
        if base_path is None:
            # Assume we're in klayout_package/python or repo root
            repo_root = Path(__file__).resolve().parents[2]
            base_path = repo_root / 'simulations_database'

            base_path = r'C:\Roger\Sim_Results'

        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

        # Create tools directory if it doesn't exist
        (self.base_path / 'tools').mkdir(exist_ok=True)

    def register_simulations(self, simulations, design_name, sim_parameters,
                           export_parameters, output_folder=None):
        """
        Register simulations in the database before export.

        Creates a sweep folder containing all simulations and sweep metadata.

        Args:
            simulations: List of simulation objects from cross_sweep_simulation
            design_name: Name of the design (e.g., 'spike_resonator')
            sim_parameters: Base simulation parameters dict
            export_parameters: Export parameters dict
            output_folder: Where export_ansys will put files (e.g., 'tmp/spike_res_q3d_sim_output')

        Returns:
            dict: Mapping of simulation names to database folder paths
        """
        timestamp = datetime.now()

        # Create design folder
        design_folder = self.base_path / design_name
        design_folder.mkdir(parents=True, exist_ok=True)

        # Detect varied parameters to name the sweep
        varied_params = self._detect_varied_parameters(simulations, sim_parameters)

        # Generate sweep folder name
        sweep_folder_name = self._generate_sweep_folder_name(timestamp, varied_params, export_parameters)
        sweep_folder = design_folder / sweep_folder_name
        sweep_folder.mkdir(exist_ok=True)

        # Create sweep metadata
        sweep_metadata = self._generate_sweep_metadata(
            simulations, design_name, sim_parameters, export_parameters,
            timestamp, varied_params
        )
        sweep_metadata_path = sweep_folder / 'sweep_metadata.json'
        with open(sweep_metadata_path, 'w') as f:
            json.dump(sweep_metadata, f, indent=2)

        db_folders = {}

        # Create individual simulation folders inside the sweep folder
        for sim in simulations:
            # Generate simple folder name (no timestamp, just sim name)
            folder_name = self._generate_sim_folder_name(sim, export_parameters)
            sim_folder = sweep_folder / folder_name
            sim_folder.mkdir(exist_ok=True)

            # Create results subfolder
            (sim_folder / 'results').mkdir(exist_ok=True)

            # Generate and save metadata
            metadata = self._generate_metadata(
                sim, design_name, sim_parameters, export_parameters, timestamp
            )
            # Add sweep reference
            metadata['sweep_folder'] = sweep_folder_name
            metadata['varied_parameters'] = varied_params

            metadata_path = sim_folder / 'metadata.json'
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)

            # Store mapping for later
            db_folders[sim.name] = str(sim_folder)

        # Save mapping file for finalize_results script
        if output_folder:
            mapping_path = Path(output_folder).parent / f'{Path(output_folder).name}_db_mapping.json'
            with open(mapping_path, 'w') as f:
                json.dump(db_folders, f, indent=2)

        print(f"\n[OK] Registered {len(simulations)} simulations in sweep")
        print(f"  Location: {sweep_folder}")

        return db_folders

    def finalize_simulation(self, sim_name, db_folder, ansys_output_folder):
        """
        Finalize a simulation by copying results and updating metadata.

        Args:
            sim_name: Name of the simulation
            db_folder: Database folder path for this simulation
            ansys_output_folder: Folder containing ANSYS output files

        Returns:
            int: Number of files copied
        """
        db_path = Path(db_folder)
        output_path = Path(ansys_output_folder)

        # Find all result files for this simulation
        result_files = []

        # Common result file patterns
        # Use more specific patterns to avoid matching similar names
        # e.g., "sim_50" shouldn't match "sim_500"
        patterns = [
            f'{sim_name}_*.json',          # sim_name_project_results.json
            f'{sim_name}_*results.json',   # sim_name_project_results.json
            f'{sim_name}_*CMatrix.txt',    # sim_name_project_CMatrix.txt
            f'{sim_name}_*LMatrix.txt',    # sim_name_project_LMatrix.txt
            f'{sim_name}_*RMatrix.txt',    # sim_name_project_RMatrix.txt
            f'{sim_name}.s2p',             # sim_name.s2p (exact match)
            f'{sim_name}_*.s2p',           # sim_name_*.s2p
            f'{sim_name}.csv',             # sim_name.csv (exact match)
            f'{sim_name}_*.csv',           # sim_name_*.csv
        ]

        for pattern in patterns:
            result_files.extend(output_path.glob(pattern))

        # Also copy the input files (gds, json)
        input_patterns = [
            f'{sim_name}.gds',             # Exact match for geometry
            f'{sim_name}.json',            # Exact match for setup
            f'{sim_name}_*.json',          # sim_name_1.json, sim_name_5.json (for frequency sweeps)
        ]

        for pattern in input_patterns:
            result_files.extend(output_path.glob(pattern))

        # Copy files to database
        files_copied = 0
        for file_path in result_files:
            # Determine destination
            if 'results' in file_path.name or 'Matrix' in file_path.name or file_path.suffix in ['.s2p', '.csv']:
                dest = db_path / 'results' / file_path.name
            else:
                dest = db_path / file_path.name

            if file_path.is_file() and not dest.exists():
                shutil.copy2(file_path, dest)
                files_copied += 1

        # Update metadata status
        metadata_path = db_path / 'metadata.json'
        if metadata_path.exists():
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)

            metadata['status'] = 'completed'
            metadata['completion_time'] = datetime.now().isoformat()

            # Try to extract key results if available
            results_json = db_path / 'results' / f'{sim_name}_project_results.json'
            if results_json.exists():
                try:
                    with open(results_json, 'r') as f:
                        results = json.load(f)

                    # Get net names from simulation parameters
                    # Handle case where extra_json_data is None
                    extra_json = metadata.get('parameters', {}).get('extra_json_data') or {}
                    net_names = extra_json.get('net_names', {})

                    metadata['results_summary'] = self._extract_results_summary(results, net_names)
                except Exception as e:
                    print(f"Warning: Could not extract results summary for {sim_name}: {e}")

            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)

        return files_copied

    def _detect_varied_parameters(self, simulations, base_params):
        """Detect which parameters vary across simulations."""
        if len(simulations) <= 1:
            return {}

        # Parameters to exclude from varied parameter detection
        # These are metadata or auto-generated values, not real sweep parameters
        excluded_params = {
            'name',              # Simulation name (auto-generated)
            'extra_json_data',   # Auto-generated port locations, etc.
            'box',               # Simulation box (usually constant)
            'face_stack',        # Layer stack (usually constant)
        }

        varied = {}

        # Get parameters from all simulations
        all_sim_params = []
        for sim in simulations:
            params = {}
            if hasattr(sim, 'get_parameters'):
                try:
                    params = sim.get_parameters()
                except:
                    pass
            all_sim_params.append(params)

        # Find parameters that vary
        if all_sim_params:
            # Check each parameter
            first_params = all_sim_params[0]
            for key in first_params:
                # Skip excluded metadata parameters
                if key in excluded_params:
                    continue

                values = []
                for params in all_sim_params:
                    if key in params:
                        val = params[key]
                        # Convert to string for comparison if not JSON serializable
                        try:
                            json.dumps(val)
                            values.append(val)
                        except (TypeError, ValueError):
                            values.append(str(val))

                # Check if all values are the same
                if len(set(str(v) for v in values)) > 1:
                    # For dict/list types, keep the actual values (can't use set)
                    # For other types, deduplicate
                    try:
                        unique_values = sorted(set(values), key=str)
                    except TypeError:
                        # Can't hash (dict, list, etc.) - keep all values
                        unique_values = values
                    varied[key] = unique_values

        return varied

    def _generate_sweep_folder_name(self, timestamp, varied_params, export_parameters):
        """Generate descriptive folder name for a parameter sweep."""
        timestamp_str = timestamp.strftime('%Y%m%d_%H%M%S')
        tool = export_parameters.get('ansys_tool', 'sim')

        # Distinguish between Q3D capacitance and ACRL (inductance) simulations
        if tool == 'q3d' and export_parameters.get('solve_acrl', False):
            tool = 'q3d_acrl'

        # Filter out metadata parameters that shouldn't be in folder name
        excluded_params = {'name', 'box', 'face_stack', 'use_ports', 'use_internal_ports'}
        meaningful_params = {k: v for k, v in varied_params.items() if k not in excluded_params}

        # Create name from varied parameters
        if meaningful_params:
            # Use first 2 meaningful varied params
            param_names = '_'.join(sorted(meaningful_params.keys())[:2])
            folder_name = f"{timestamp_str}_{param_names}_sweep_{tool}"
        else:
            # Single simulation or no varied parameters
            folder_name = f"{timestamp_str}_single_{tool}"

        # Sanitize
        folder_name = folder_name.replace(' ', '_').replace('/', '_')
        return folder_name

    def _generate_sim_folder_name(self, sim, export_parameters):
        """Generate simple folder name for individual simulation (no timestamp)."""
        # Just use the simulation name
        folder_name = sim.name

        # Sanitize folder name
        folder_name = folder_name.replace(' ', '_').replace('/', '_')

        return folder_name

    def _generate_sweep_metadata(self, simulations, design_name, sim_parameters,
                                export_parameters, timestamp, varied_params):
        """Generate metadata for the entire sweep."""
        # Get constant parameters (not varied)
        constant_params = {}
        if simulations and hasattr(simulations[0], 'get_parameters'):
            try:
                first_params = simulations[0].get_parameters()
                for key, value in first_params.items():
                    if key not in varied_params:
                        try:
                            json.dumps(value)
                            constant_params[key] = value
                        except (TypeError, ValueError):
                            constant_params[key] = str(value)
            except:
                pass

        # Create simulation list with their varied parameter values
        simulation_list = []
        for sim in simulations:
            sim_info = {
                'name': sim.name,
                'status': 'pending'
            }
            # Add varied parameter values for this sim
            if hasattr(sim, 'get_parameters'):
                try:
                    params = sim.get_parameters()
                    for key in varied_params:
                        if key in params:
                            try:
                                json.dumps(params[key])
                                sim_info[key] = params[key]
                            except (TypeError, ValueError):
                                sim_info[key] = str(params[key])
                except:
                    pass
            simulation_list.append(sim_info)

        # Serialize export parameters
        serializable_export = {}
        for key, value in export_parameters.items():
            if key == 'post_process':
                continue
            try:
                json.dumps(value)
                serializable_export[key] = value
            except (TypeError, ValueError):
                serializable_export[key] = str(value)

        metadata = {
            'timestamp': timestamp.isoformat(),
            'design': design_name,
            'ansys_tool': export_parameters.get('ansys_tool', 'unknown'),
            'num_simulations': len(simulations),
            'varied_parameters': varied_params,
            'constant_parameters': constant_params,
            'export_parameters': serializable_export,
            'simulations': simulation_list
        }

        return metadata

    def _generate_metadata(self, sim, design_name, sim_parameters, export_parameters, timestamp):
        """Generate comprehensive metadata for a simulation."""
        # Combine all parameters from sim object
        all_params = {}

        # Get parameters from simulation object
        if hasattr(sim, 'get_parameters'):
            try:
                all_params = sim.get_parameters()
            except:
                pass

        # Merge with base parameters
        for key, value in sim_parameters.items():
            if key not in all_params:
                all_params[key] = value

        # Convert non-serializable types
        serializable_params = {}
        for key, value in all_params.items():
            try:
                json.dumps(value)
                serializable_params[key] = value
            except (TypeError, ValueError):
                serializable_params[key] = str(value)

        # Same for export parameters
        serializable_export = {}
        for key, value in export_parameters.items():
            if key == 'post_process':
                # Skip post_process object
                continue
            try:
                json.dumps(value)
                serializable_export[key] = value
            except (TypeError, ValueError):
                serializable_export[key] = str(value)

        metadata = {
            'timestamp': timestamp.isoformat(),
            'design': design_name,
            'simulation_name': sim.name,
            'ansys_tool': export_parameters.get('ansys_tool', 'unknown'),
            'parameters': serializable_params,
            'export_parameters': serializable_export,
            'status': 'pending',
            'files': {
                'geometry': f'{sim.name}.gds',
                'simulation_json': f'{sim.name}_{export_parameters.get("ansys_tool", "sim")}.json',
            }
        }

        return metadata

    def _extract_results_summary(self, results, net_names=None):
        """Extract key metrics from results JSON for quick reference.

        Args:
            results: Results JSON from ANSYS containing matrices
            net_names: Optional dict mapping port numbers to net names (e.g., {1: "feedline", 2: "inductor"})

        Uses descriptive net names if available, otherwise falls back to numbered indices.
        """
        summary = {}

        # Convert string keys to int keys if needed
        if net_names and isinstance(net_names, dict):
            net_names = {int(k) if isinstance(k, str) and k.isdigit() else k: v
                        for k, v in net_names.items()}
        else:
            net_names = {}

        # Helper function to create matrix element key
        def get_matrix_key(matrix_type, i, j, net_names):
            """Generate matrix element key with descriptive net names if available."""
            port_i = i + 1  # Convert to 1-based
            port_j = j + 1

            if net_names and port_i in net_names and port_j in net_names:
                name_i = net_names[port_i]
                name_j = net_names[port_j]

                if i == j:
                    # Self-inductance/capacitance
                    return f'{matrix_type}_{name_i}'
                else:
                    # Mutual inductance/capacitance
                    return f'{matrix_type}_{name_i}_{name_j}'
            else:
                # Fall back to numbered labels
                return f'{matrix_type}_{port_i}{port_j}'

        # Capacitance matrix elements
        if 'CMatrix' in results:
            cmatrix = results['CMatrix']
            if isinstance(cmatrix, list) and len(cmatrix) > 0:
                for i, row in enumerate(cmatrix):
                    if isinstance(row, list):
                        for j, val in enumerate(row):
                            key = get_matrix_key('C', i, j, net_names)
                            summary[key] = val

        # Inductance matrix elements
        if 'LMatrix' in results:
            lmatrix = results['LMatrix']
            if isinstance(lmatrix, list) and len(lmatrix) > 0:
                for i, row in enumerate(lmatrix):
                    if isinstance(row, list):
                        for j, val in enumerate(row):
                            key = get_matrix_key('L', i, j, net_names)
                            summary[key] = val

        # Resistance matrix elements
        if 'RMatrix' in results:
            rmatrix = results['RMatrix']
            if isinstance(rmatrix, list) and len(rmatrix) > 0:
                for i, row in enumerate(rmatrix):
                    if isinstance(row, list):
                        for j, val in enumerate(row):
                            key = get_matrix_key('R', i, j, net_names)
                            summary[key] = val

        # Other common metrics
        if 'convergence_passes' in results:
            summary['convergence_passes'] = results['convergence_passes']

        return summary
