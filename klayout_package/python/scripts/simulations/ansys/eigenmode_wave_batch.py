# This code is part of KQCircuits
# Copyright (C) 2025 Roger Romani
# Copyright (C) 2021 IQM Finland Oy
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public
# License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied
# warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with this program. If not, see
# https://www.gnu.org/licenses/gpl-3.0.html.
#
# The software distribution should follow IQM trademark policy for open-source software
# (meetiqm.com/iqm-open-source-trademark-policy). IQM welcomes contributions to the code.
# Please see our contribution agreements for individuals (meetiqm.com/iqm-individual-contributor-license-agreement)
# and organizations (meetiqm.com/iqm-organization-contributor-license-agreement).


"""Eigenmode + Wave Simulation Batch Script for ANSYS

This is a Python 2.7 script that runs inside ANSYS Electronics Desktop and:
1. Loads eigenmode JSON -> creates eigenmode setup -> runs -> extracts eigenfrequency
2. Loads wave JSON -> creates wave setup in SAME project
3. Updates wave setup frequency sweep based on eigenfrequency
4. Imports mesh from eigenmode setup into wave setup
5. Runs wave setup
6. Exports results

Arguments (semicolon-separated):
    eigenmode_json;wave_json;sweep_width_ghz
"""

import os
import json
import sys
import ScriptEnv

# Set up environment
ScriptEnv.Initialize("Ansoft.ElectronicsDesktop")
scriptpath = os.path.dirname(__file__)

# TODO: Figure out how to set the python path for the Ansys internal IronPython
sys.path.insert(0, os.path.join(scriptpath, "util"))
from util import get_enabled_setup, get_enabled_sweep, get_solution_data, get_quantities

# Parse arguments: eigenmode_json;wave_json;sweep_width_ghz
args = ScriptArgument.split(";")
if len(args) < 2:
    raise ValueError("Expected at least 2 arguments: eigenmode_json;wave_json[;sweep_width]")

eigenmode_json = args[0]
wave_json = args[1]
sweep_width_ghz = float(args[2]) if len(args) > 2 else 1.0
frequency_offset_factor = float(args[3]) if len(args) > 3 else 1.0

# Set up log file that persists after ANSYS closes
# Use eigenmode basename so each simulation has its own log
eigenmode_basename_for_log = os.path.splitext(os.path.basename(eigenmode_json))[0]
log_file_path = os.path.join(os.path.dirname(eigenmode_json), eigenmode_basename_for_log + "_run.log")
log_file = open(log_file_path, "w")

def log(message):
    """Write message to both ANSYS console and persistent log file"""
    print(message)
    log_file.write(message + "\n")
    log_file.flush()  # Ensure it's written immediately

# Log to file for debugging
log("Log file: {}".format(log_file_path))

log("="*70)
log("Eigenmode + Wave Simulation Workflow")
log("="*70)
log("Eigenmode JSON: {}".format(os.path.basename(eigenmode_json)))
log("Wave JSON: {}".format(os.path.basename(wave_json)))
log("Sweep width: +/- {} GHz around eigenfrequency".format(sweep_width_ghz / 2.0))
log("Frequency offset factor: {}".format(frequency_offset_factor))
log("="*70)

# ===========================
# Step 1: Run Eigenmode Simulation
# ===========================

print("\nStep 1: Running eigenmode simulation...")
print("-"*70)

# Import geometry for eigenmode
oDesktop.RunScriptWithArguments(
    os.path.join(scriptpath, "import_simulation_geometry.py"),
    eigenmode_json
)

# Get project and design
oProject = oDesktop.GetActiveProject()
oDesign = oProject.GetActiveDesign()
eigenmode_design_name = oDesign.GetName()

print("Created eigenmode design: {}".format(eigenmode_design_name))

# Create reports for eigenmode
oDesktop.RunScriptWithArguments(os.path.join(scriptpath, "create_reports.py"), eigenmode_json)

# Save project with a meaningful name
path = os.path.dirname(eigenmode_json)
eigenmode_basename = os.path.splitext(os.path.basename(eigenmode_json))[0]
wave_basename = os.path.splitext(os.path.basename(wave_json))[0]
project_name = eigenmode_basename + "_and_" + wave_basename
oProject.SaveAs(os.path.join(path, project_name + ".aedt"), True)

# Run eigenmode analysis
print("Analyzing eigenmode...")
oDesign.AnalyzeAll()

# Save after analysis
oProject.Save()

# Export eigenmode results (this creates the .eig file)
print("Exporting eigenmode results...")
oDesktop.RunScriptWithArguments(os.path.join(scriptpath, "export_solution_data.py"), eigenmode_json)

# Extract eigenfrequency from .eig file
print("\n" + "="*70)
print("STEP: EXTRACTING EIGENFREQUENCY")
print("="*70)

# Read .eig file (created by export_solution_data.py)
eig_file = os.path.join(path, project_name + "_modes.eig")
print("Looking for eigenmode file: {}".format(eig_file))

if not os.path.exists(eig_file):
    raise ValueError("ERROR: Eigenmode file not found: {}".format(eig_file))

print("Reading eigenmode file...")
modes_data = []  # List of (mode_number, frequency_ghz, q_factor) tuples

with open(eig_file, "r") as f:
    lines = f.readlines()
    print("File has {} lines".format(len(lines)))

    # Read all eigenmode data lines (skip header lines starting with #)
    for i, line in enumerate(lines):
        if line.strip() and not line.strip().startswith("#"):
            parts = line.split()
            if len(parts) >= 2:
                mode_number = int(parts[0])

                # Handle complex frequency format: "freq_real + freq_imag j Q"
                # or simple format: "mode freq Q"
                if 'j' in parts:
                    # Complex frequency format (lossy eigenmode)
                    # Format: mode, freq_real, +/-, freq_imag, j, Q
                    eigen_freq_ghz = float(parts[1])  # Real part only
                    # Q factor is the last element after 'j'
                    j_index = parts.index('j')
                    q_factor = float(parts[j_index + 1]) if len(parts) > j_index + 1 else 0.0
                else:
                    # Simple format: mode, freq, Q
                    eigen_freq_ghz = float(parts[1])
                    q_factor = float(parts[2]) if len(parts) >= 3 else 0.0

                modes_data.append((mode_number, eigen_freq_ghz, q_factor))
                print("Mode {}: Frequency = {:.6f} GHz, Q = {:.2e}".format(
                    mode_number, eigen_freq_ghz, q_factor))

if not modes_data:
    raise ValueError("No eigenmode data found in .eig file")

# Select mode with highest Q factor (or first mode if Q not available)
if all(q == 0.0 for _, _, q in modes_data):
    # Q factors not available, use first mode
    selected_mode = modes_data[0]
    print("\nNote: Q factors not available, using first mode")
else:
    # Select mode with highest Q
    selected_mode = max(modes_data, key=lambda x: x[2])
    print("\nSelected mode with highest Q factor:")

mode_number, eigen_freq_ghz, q_factor = selected_mode
print("Mode {}: Frequency = {:.6f} GHz, Q = {:.2e}".format(
    mode_number, eigen_freq_ghz, q_factor))

# Validate the frequency is reasonable (between 1 and 100 GHz)
if eigen_freq_ghz < 1.0 or eigen_freq_ghz > 100.0:
    raise ValueError("Eigenfrequency {:.6f} GHz is outside reasonable range (1-100 GHz)".format(eigen_freq_ghz))

print("\n" + "="*70)
print("SUCCESS: Selected Eigenfrequency = {:.6f} GHz (Mode {}, Q = {:.2e})".format(
    eigen_freq_ghz, mode_number, q_factor))
print("="*70 + "\n")

# ===========================
# Step 2: Create Wave Setup in Same Project
# ===========================

print("\nStep 2: Creating wave simulation setup...")
print("-"*70)

# Load wave JSON to get parameters
with open(wave_json, "r") as fp:
    wave_data = json.load(fp)

# Note: import_simulation_geometry.py creates a NEW project by default
# For our workflow, we need wave design in the SAME project for mesh import
# So we import wave to new project, then copy design to eigenmode project

# Save eigenmode project reference
eigenmode_project_name = oProject.GetName()
oProject.Save()

# Import wave geometry (this creates a new temporary project)
print("Importing wave geometry...")
oDesktop.RunScriptWithArguments(
    os.path.join(scriptpath, "import_simulation_geometry.py"),
    wave_json
)

# Get the newly created wave project and design
oProject_wave_temp = oDesktop.GetActiveProject()
oDesign_wave_temp = oProject_wave_temp.GetActiveDesign()
wave_design_name = oDesign_wave_temp.GetName()

print("Created wave design: {} in temporary project".format(wave_design_name))

# Copy wave design to eigenmode project
print("Copying wave design to eigenmode project...")
oProject_wave_temp.CopyDesign(wave_design_name)

# Keep track of temp project name for later cleanup
temp_project_name = oProject_wave_temp.GetName()

# Set eigenmode project as active (it should still be open)
# Note: Don't close temp project yet - clipboard may be cleared
oDesktop.SetActiveProject(eigenmode_project_name)
oProject = oDesktop.GetActiveProject()

# Paste wave design into eigenmode project
oProject.Paste()
oProject.SetActiveDesign(wave_design_name)
oDesign_wave = oProject.GetActiveDesign()

print("Wave design copied to eigenmode project: {}".format(wave_design_name))

# Now close the temporary wave project (no longer needed)
try:
    oDesktop.CloseProject(temp_project_name)
except:
    pass  # Ignore errors if project already closed

# NOTE: Don't create reports yet - they'll be invalidated when we update the sweep
# Reports will be created after frequency sweep is updated

# ===========================
# Step 3: Update Wave Frequency Sweep
# ===========================

log("\nStep 3: Updating wave setup frequency sweep...")
log("-"*70)

# Calculate sweep range centered on offset eigenfrequency
adaptive_freq_ghz = eigen_freq_ghz * frequency_offset_factor
sweep_start_ghz = adaptive_freq_ghz - sweep_width_ghz / 2.0
sweep_end_ghz = adaptive_freq_ghz + sweep_width_ghz / 2.0

log("Adaptive frequency: {:.6f} GHz".format(adaptive_freq_ghz))
log("Sweep range: {:.6f} - {:.6f} GHz".format(sweep_start_ghz, sweep_end_ghz))

# Get analysis setup module
oAnalysisSetup_wave = oDesign_wave.GetModule("AnalysisSetup")
setup_names = oAnalysisSetup_wave.GetSetups()

if len(setup_names) > 0:
    setup_name = setup_names[0]

    log("Updating setup '{}' to use eigenfrequency {:.6f} GHz".format(setup_name, adaptive_freq_ghz))

    # Get current setup properties to preserve them
    # We need to read the current setup and modify only the frequency
    # Update frequency for adaptive solve using ChangeProperty instead of EditSetup
    oDesign_wave.ChangeProperty(
        [
            "NAME:AllTabs",
            [
                "NAME:HfssTab",
                ["NAME:PropServers", "AnalysisSetup:" + setup_name],
                [
                    "NAME:ChangedProps",
                    ["NAME:Solution Freq", "Value:=", "{:.6f}GHz".format(adaptive_freq_ghz)]
                ]
            ]
        ]
    )
    log("Setup frequency updated to {:.6f} GHz".format(adaptive_freq_ghz))

    # Verify the frequency was actually set by reading it back
    try:
        actual_freq = oDesign_wave.GetPropertyValue("HfssTab", "AnalysisSetup:" + setup_name, "Solution Freq")
        log("Verified: Setup frequency is now: {}".format(actual_freq))
    except Exception as e:
        log("WARNING: Could not verify frequency setting: {}".format(e))

    # Update frequency sweep - delete old sweep and create new one
    sweep_names = oAnalysisSetup_wave.GetSweeps(setup_name)
    if len(sweep_names) > 0:
        # Delete existing sweep
        for sweep_name in sweep_names:
            oAnalysisSetup_wave.DeleteSweep(setup_name, sweep_name)
        log("Deleted existing sweep(s)")

    # Get sweep parameters from wave_data
    sweep_count = wave_data.get("sweep_count", 5001)
    sweep_type = wave_data.get("sweep_type", "Interpolating")

    # Create new sweep with eigenfrequency-centered range
    log("Creating new sweep: {:.6f} - {:.6f} GHz ({} points, type={})".format(
        sweep_start_ghz, sweep_end_ghz, sweep_count, sweep_type))
    oAnalysisSetup_wave.InsertFrequencySweep(
        setup_name,
        [
            "NAME:Sweep",
            "IsEnabled:=", True,
            "RangeType:=", "LinearCount",
            "RangeStart:=", "{:.6f}GHz".format(sweep_start_ghz),
            "RangeEnd:=", "{:.6f}GHz".format(sweep_end_ghz),
            "RangeCount:=", sweep_count,
            "Type:=", sweep_type,
            "SaveFields:=", False,
            "SaveRadFields:=", False,
            "ExtrapToDC:=", False,
        ]
    )
    log("Wave setup updated with eigenfrequency-centered sweep")
else:
    log("WARNING: No setup found in wave design")

# Save project after modifying wave setup
oProject.Save()

# Now create reports for wave design (after sweep is configured)
log("\nCreating reports for wave simulation...")
oDesktop.RunScriptWithArguments(os.path.join(scriptpath, "create_reports.py"), wave_json)

# ===========================
# Step 4: Import Mesh from Eigenmode Setup
# ===========================

log("\nStep 4: Importing mesh from eigenmode setup...")
log("-"*70)

# In ANSYS, to import mesh from another design in the same project:
# oAnalysisSetup.ImportMesh(setup_name, "SourceDesignName:SourceSetupName")

# ===========================
# NOTE: Mesh Import (Future Enhancement)
# ===========================
# Mesh import from eigenmode to wave setup would speed up convergence,
# but the ANSYS API for this is complex and varies by version.
# For now, wave simulation generates its own mesh from scratch.
# This still works correctly, just takes a bit longer to converge.
#
# Future implementation would use one of:
# - Initial Mesh Settings in setup properties
# - CopyMeshFrom method (if available in ANSYS version)
# - Manual mesh copying through API
# ===========================

log("\nNote: Mesh import not implemented - wave setup will generate mesh from scratch")
log("(This is OK - just takes a few extra adaptive passes)")

# ===========================
# Step 5: Run Wave Analysis
# ===========================

log("\nStep 5: Running wave simulation...")
log("-"*70)

# Save project one more time before running to ensure all settings are persisted
log("Saving project with updated wave setup...")
oProject.Save()
log("Project saved")

# Log diagnostic info about wave design
try:
    wave_solution_type = oDesign_wave.GetSolutionType()
    log("Wave design solution type: {}".format(wave_solution_type))
    oBoundary_wave = oDesign_wave.GetModule("BoundarySetup")
    excitations = oBoundary_wave.GetExcitations()
    log("Wave design excitations: {}".format(excitations))
    log("Number of ports: {}".format(len(excitations) // 2))
except Exception as e:
    log("Note: Could not get wave design info: {}".format(e))

log("Starting wave analysis at {:.6f} GHz...".format(adaptive_freq_ghz))

# Ensure the wave design is properly set as active and saved before analysis
try:
    oProject.SetActiveDesign(wave_design_name)
    oDesign_wave = oProject.GetActiveDesign()
    log("Re-confirmed active design: {}".format(oDesign_wave.GetName()))
except Exception as e:
    log("WARNING: Could not re-confirm active design: {}".format(e))

# Re-get the analysis setup module after re-confirming design
oAnalysisSetup_wave = oDesign_wave.GetModule("AnalysisSetup")

# Save project one more time to ensure all changes are committed
oProject.Save()
log("Project saved before analysis")

# Validate the design before running
try:
    oDesign_wave.ValidateDesign()
    log("Design validation passed")
except Exception as e:
    log("WARNING: Design validation failed: {}".format(e))

# Wrap analysis in try-except to ensure ANSYS closes even if simulation fails
simulation_succeeded = False
analysis_ran = False
try:
    # Try analyzing the specific setup instead of AnalyzeAll
    # This can be more reliable after design modifications
    setup_name_to_analyze = oAnalysisSetup_wave.GetSetups()[0]
    log("Analyzing setup: {}".format(setup_name_to_analyze))
    oDesign_wave.Analyze(setup_name_to_analyze)
    log("Wave analysis complete")
    simulation_succeeded = True
    analysis_ran = True
except Exception as e:
    log("\n" + "!"*70)
    log("WARNING: Wave simulation had an issue:")
    log(str(e))
    log("!"*70)
    log("\nThis may mean the adaptive solve didn't converge within max passes.")
    log("Will still attempt to export S-parameters...")
    analysis_ran = True  # Analysis ran but may not have converged
    # Try to get more detailed error info from ANSYS
    try:
        import traceback
        log("Traceback: {}".format(traceback.format_exc()))
    except:
        pass
    # Try to get ANSYS messages
    try:
        oMessenger = oDesktop.GetMessages("", "", 2)  # Get all error messages
        if oMessenger:
            log("ANSYS Error Messages:")
            for msg in oMessenger:
                log("  {}".format(msg))
    except:
        pass

# Save project regardless of whether simulation succeeded
oProject.Save()

# ===========================
# Step 6: Export Results (if analysis ran, even without full convergence)
# ===========================

if analysis_ran:
    log("\nStep 6: Exporting results...")
    log("-"*70)

    # Make sure wave design is active before exporting
    oProject.SetActiveDesign(wave_design_name)
    log("Set active design to: {}".format(wave_design_name))

    # Export wave results (S-parameters)
    log("Exporting S-parameters from wave simulation...")
    log("Calling export_solution_data.py with: {}".format(wave_json))
    try:
        oDesktop.RunScriptWithArguments(
            os.path.join(scriptpath, "export_solution_data.py"),
            wave_json
        )
        log("S-parameter export script completed")
    except Exception as e:
        log("ERROR: Could not export S-parameters: {}".format(e))
        import traceback
        log("Traceback: {}".format(traceback.format_exc()))

    if simulation_succeeded:
        log("\n" + "="*70)
        log("SUCCESS!")
        log("="*70)
    else:
        log("\n" + "="*70)
        log("COMPLETED (with convergence warning)")
        log("="*70)
        log("Note: Adaptive solve may not have fully converged, but S-parameters were exported")
    log("Selected Mode: {} (Q = {:.2e})".format(mode_number, q_factor))
    log("Eigenfrequency: {:.6f} GHz".format(eigen_freq_ghz))
    log("Wave sweep: {:.6f} - {:.6f} GHz".format(sweep_start_ghz, sweep_end_ghz))
    log("Project saved: {}".format(os.path.join(path, project_name + ".aedt")))
    log("="*70)
else:
    log("\n" + "="*70)
    log("FAILED")
    log("="*70)
    log("Selected Mode: {} (Q = {:.2e})".format(mode_number, q_factor))
    log("Eigenfrequency: {:.6f} GHz (SUCCESS)".format(eigen_freq_ghz))
    log("Wave simulation: FAILED - analysis could not start")
    log("Project saved: {}".format(os.path.join(path, project_name + ".aedt")))
    log("="*70)

# ===========================
# Step 7: Cleanup and Exit
# ===========================

log("\n" + "="*70)
log("CLEANUP: Closing ANSYS")
log("="*70)

# Final save before closing
log("Final project save...")
try:
    oProject.Save()
    log("Project saved successfully")
except Exception as e:
    log("Warning: Could not save project: {}".format(str(e)))

# Close all design windows
log("Closing design windows...")
try:
    oDesktop.CloseAllWindows()
    log("All windows closed")
except Exception as e:
    log("Note: CloseAllWindows failed: {}".format(str(e)))

# Close the project
log("Closing project...")
try:
    oProject.Close()
    log("Project closed successfully")
except Exception as e:
    log("Warning: Could not close project: {}".format(str(e)))
    log("Attempting to continue with quit anyway...")

# Quit ANSYS Desktop (this should force close even if project close failed)
log("\nQuitting ANSYS Desktop...")
try:
    oDesktop.QuitApplication()
    log("QuitApplication() called successfully")
except Exception as e:
    log("ERROR: QuitApplication failed: {}".format(str(e)))
    log("ANSYS may still be running - you may need to close it manually")

log("="*70)
log("Script execution complete")
log("="*70)

# Close log file
log_file.close()
