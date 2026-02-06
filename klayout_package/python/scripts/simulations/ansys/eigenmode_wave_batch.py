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

print("="*70)
print("Eigenmode + Wave Simulation Workflow")
print("="*70)
print("Eigenmode JSON: {}".format(os.path.basename(eigenmode_json)))
print("Wave JSON: {}".format(os.path.basename(wave_json)))
print("Sweep width: +/- {} GHz around eigenfrequency".format(sweep_width_ghz / 2.0))
print("="*70)

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
with open(eig_file, "r") as f:
    lines = f.readlines()
    print("File has {} lines".format(len(lines)))

    # Find the data line (after the header)
    for i, line in enumerate(lines):
        if line.strip() and not line.strip().startswith("#"):
            print("Data line {}: {}".format(i, line.strip()))
            parts = line.split()
            if len(parts) >= 2:
                mode_number = int(parts[0])
                eigen_freq_ghz = float(parts[1])
                print("Mode {}: Frequency = {:.6f} GHz".format(mode_number, eigen_freq_ghz))
                break
    else:
        raise ValueError("No eigenmode data found in .eig file")

# Validate the frequency is reasonable (between 1 and 100 GHz)
if eigen_freq_ghz < 1.0 or eigen_freq_ghz > 100.0:
    raise ValueError("Eigenfrequency {:.6f} GHz is outside reasonable range (1-100 GHz)".format(eigen_freq_ghz))

print("\n" + "="*70)
print("SUCCESS: Eigenfrequency = {:.6f} GHz".format(eigen_freq_ghz))
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

# Close temporary wave project
temp_project_name = oProject_wave_temp.GetName()
oDesktop.CloseProject(temp_project_name)

# Set eigenmode project as active (it should still be open)
oDesktop.SetActiveProject(eigenmode_project_name)
oProject = oDesktop.GetActiveProject()

# Paste wave design into eigenmode project
oProject.Paste()
oProject.SetActiveDesign(wave_design_name)
oDesign_wave = oProject.GetActiveDesign()

print("Wave design copied to eigenmode project: {}".format(wave_design_name))

# Create reports for wave
oDesktop.RunScriptWithArguments(os.path.join(scriptpath, "create_reports.py"), wave_json)

# ===========================
# Step 3: Update Wave Frequency Sweep
# ===========================

print("\nStep 3: Updating wave setup frequency sweep...")
print("-"*70)

# Calculate sweep range centered on eigenfrequency
sweep_start_ghz = eigen_freq_ghz - sweep_width_ghz / 2.0
sweep_end_ghz = eigen_freq_ghz + sweep_width_ghz / 2.0
adaptive_freq_ghz = eigen_freq_ghz  # Adaptive solve at eigenfrequency

print("Adaptive frequency: {:.6f} GHz".format(adaptive_freq_ghz))
print("Sweep range: {:.6f} - {:.6f} GHz".format(sweep_start_ghz, sweep_end_ghz))

# Get analysis setup module
oAnalysisSetup_wave = oDesign_wave.GetModule("AnalysisSetup")
setup_names = oAnalysisSetup_wave.GetSetups()

if len(setup_names) > 0:
    setup_name = setup_names[0]

    print("Updating setup '{}' to use eigenfrequency {:.6f} GHz".format(setup_name, adaptive_freq_ghz))

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
    print("Setup frequency updated to {:.6f} GHz".format(adaptive_freq_ghz))

    # Update frequency sweep - delete old sweep and create new one
    sweep_names = oAnalysisSetup_wave.GetSweeps(setup_name)
    if len(sweep_names) > 0:
        # Delete existing sweep
        for sweep_name in sweep_names:
            oAnalysisSetup_wave.DeleteSweep(setup_name, sweep_name)
        print("Deleted existing sweep(s)")

    # Get sweep parameters from wave_data
    sweep_count = wave_data.get("sweep_count", 5001)
    sweep_type = wave_data.get("sweep_type", "Interpolating")

    # Create new sweep with eigenfrequency-centered range
    print("Creating new sweep: {:.6f} - {:.6f} GHz".format(sweep_start_ghz, sweep_end_ghz))
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
    print("Wave setup updated with eigenfrequency-centered sweep")
else:
    print("WARNING: No setup found in wave design")

# Save project after modifying wave setup
oProject.Save()

# ===========================
# Step 4: Import Mesh from Eigenmode Setup
# ===========================

print("\nStep 4: Importing mesh from eigenmode setup...")
print("-"*70)

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

print("\nNote: Mesh import not implemented - wave setup will generate mesh from scratch")
print("(This is OK - just takes a few extra adaptive passes)")

# ===========================
# Step 5: Run Wave Analysis
# ===========================

print("\nStep 5: Running wave simulation...")
print("-"*70)

oDesign_wave.AnalyzeAll()

# Save project
oProject.Save()

# ===========================
# Step 6: Export Results
# ===========================

print("\nStep 6: Exporting results...")
print("-"*70)

# Export wave results (S-parameters)
oDesktop.RunScriptWithArguments(
    os.path.join(scriptpath, "export_solution_data.py"),
    wave_json
)

print("\n" + "="*70)
print("SUCCESS!")
print("="*70)
print("Eigenfrequency: {:.6f} GHz".format(eigen_freq_ghz))
print("Wave sweep: {:.6f} - {:.6f} GHz".format(sweep_start_ghz, sweep_end_ghz))
print("Project saved: {}".format(os.path.join(path, project_name + ".aedt")))
print("="*70)

# Close project to prepare for next simulation
oProject.Close()
