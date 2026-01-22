# This code is part of KQCircuits
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


# This is a Python 2.7 script that runs multiple simulations in ANSYS sequentially without restarting
import os
import json
import sys
import platform
import ScriptEnv

# Set up environment
ScriptEnv.Initialize("Ansoft.ElectronicsDesktop")
scriptpath = os.path.dirname(__file__)

# ScriptArgument contains a semicolon-separated list of JSON files
json_files_str = ScriptArgument
json_files = json_files_str.split(";")

print("Batch processing {} simulations...".format(len(json_files)))

for i, jsonfile in enumerate(json_files):
    print("\n" + "="*60)
    print("Simulation {}/{}: {}".format(i+1, len(json_files), os.path.basename(jsonfile)))
    print("="*60)

    path = os.path.abspath(os.path.dirname(jsonfile))
    basename = os.path.splitext(os.path.basename(jsonfile))[0]

    # Read simulation_flags settings from .json
    with open(jsonfile, "r") as fp:  # pylint: disable=unspecified-encoding
        data = json.load(fp)
    simulation_flags = data["simulation_flags"]

    # Create project and geometry
    if data["ansys_tool"] == "cross-section":
        oDesktop.RunScriptWithArguments(os.path.join(scriptpath, "import_cross_section_geometry.py"), jsonfile)
    else:
        oDesktop.RunScriptWithArguments(os.path.join(scriptpath, "import_simulation_geometry.py"), jsonfile)

    # Set up capacitive PI model
    if data.get("ansys_tool", "hfss") in ["q3d", "cross-section"] or data.get("capacitance_export", False):
        oDesktop.RunScript(os.path.join(scriptpath, "create_capacitive_pi_model.py"))

    # Create reports
    oDesktop.RunScriptWithArguments(os.path.join(scriptpath, "create_reports.py"), jsonfile)
    oDesktop.TileWindows(0)

    # Save project
    oProject = oDesktop.GetActiveProject()
    oProject.SaveAs(os.path.join(path, basename + "_project.aedt"), True)

    # only import geometry for pyEPR simulations
    if "pyepr" in simulation_flags:
        oProject.Close()
        continue

    # Run
    oDesign = oProject.GetActiveDesign()
    oDesign.AnalyzeAll()

    # Save solution
    oProject.Save()

    # Export results
    oDesktop.RunScriptWithArguments(os.path.join(scriptpath, "export_solution_data.py"), jsonfile)

    #######################
    # Optional processing #
    #######################

    # Time Domain Reflectometry
    if "tdr" in simulation_flags:
        oDesktop.RunScript(os.path.join(scriptpath, "export_tdr.py"))

    # Export Touchstone S-matrix (.sNp) w/o de-embedding
    if "snp_no_deembed" in simulation_flags:
        oDesktop.RunScript(os.path.join(scriptpath, "export_snp_no_deembed.py"))

    # Write version info (only once, at the end)
    if i == 0:
        def write_simulation_machine_versions_file(oDesktop):
            versions = {}
            versions["platform"] = platform.platform()
            versions["python"] = sys.version_info
            versions["Ansys ElectronicsDesktop"] = oDesktop.GetVersion()
            with open("SIMULATION_MACHINE_VERSIONS.json", "w") as file:
                json.dump(versions, file)
        write_simulation_machine_versions_file(oDesktop)

    # Close project to prepare for next simulation
    oProject.Close()
    print("Simulation {}/{} complete!".format(i+1, len(json_files)))

print("\n" + "="*60)
print("All {} simulations complete!".format(len(json_files)))
print("="*60)
