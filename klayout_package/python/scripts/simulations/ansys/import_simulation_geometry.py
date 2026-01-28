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


# This is a Python 2.7 script that should be run in Ansys Electronic Desktop in order to import and run the simulation
import time
import os
import sys
import json
import ScriptEnv

# TODO: Figure out how to set the python path for the Ansys internal IronPython
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "util"))
from geometry import (  # pylint: disable=wrong-import-position
    create_box,
    create_rectangle,
    create_polygon,
    thicken_sheet,
    set_material,
    add_layer,
    subtract,
    move_vertically,
    delete,
    add_material,
    color_by_material,
    set_color,
    scale,
    match_layer,
)
from field_calculation import (  # pylint: disable=wrong-import-position
    add_squared_electric_field_expression,
    add_energy_integral_expression,
    add_magnetic_flux_integral_expression,
)

# pylint: disable=consider-using-f-string
# Set up environment
ScriptEnv.Initialize("Ansoft.ElectronicsDesktop")

# Import metadata (bounding box and port information)
jsonfile = ScriptArgument
path = os.path.dirname(jsonfile)

with open(jsonfile, "r") as fjsonfile:  # pylint: disable=unspecified-encoding
    data = json.load(fjsonfile)

ansys_tool = data.get("ansys_tool", "hfss")
solve_acrl = data.get("analysis_setup", {}).get("solve_acrl", False)

simulation_flags = data["simulation_flags"]
gds_file = data["gds_file"]
units = data.get("units", "um")
material_dict = data.get("material_dict", {})
box = data["box"]

ansys_project_template = data.get("ansys_project_template", "")
vertical_over_etching = data.get("vertical_over_etching", 0)
mesh_size = data.get("mesh_size", {})

# Create project
oDesktop.RestoreWindow()
oProject = oDesktop.NewProject()
oDefinitionManager = oProject.GetDefinitionManager()

hfss_tools = {"hfss", "current", "voltage", "eigenmode"}

design_name = ansys_tool.capitalize() + "Design"
if ansys_tool == "eigenmode":
    oProject.InsertDesign("HFSS", design_name, "Eigenmode", "")
elif ansys_tool in hfss_tools:
    oProject.InsertDesign("HFSS", design_name, "HFSS Terminal Network", "")
elif ansys_tool == "q3d":
    oProject.InsertDesign("Q3D Extractor", design_name, "", "")
else:
    raise ValueError("Unkown ansys_tool: {}".format(ansys_tool))

oDesign = oProject.SetActiveDesign(design_name)
oEditor = oDesign.SetActiveEditor("3D Modeler")
oBoundarySetup = oDesign.GetModule("BoundarySetup")
oAnalysisSetup = oDesign.GetModule("AnalysisSetup")
oOutputVariable = oDesign.GetModule("OutputVariable")
oSolutions = oDesign.GetModule("Solutions")
oReportSetup = oDesign.GetModule("ReportSetup")

# Set units
oEditor.SetModelUnits(["NAME:Units Parameter", "Units:=", units, "Rescale:=", False])

# Add materials
for name, params in material_dict.items():
    add_material(oDefinitionManager, name, **params)

# Import GDSII geometry
layers = data.get("layers", {})
refine_layers = [n for n in layers if any(match_layer(n, p) for p in mesh_size)]
lumped_rlc_layers = [n for n in layers if "lumped_rlc" in n]  # Lumped RLC element layers
layers = {n: d for n, d in layers.items() if not n.endswith("_gap") or n in refine_layers}  # ignore unused gap layers
metal_layers = {n: d for n, d in layers.items() if "excitation" in d}

order_map = []
layer_map = ["NAME:LayerMap"]
order = 0
for lname, ldata in layers.items():
    if "layer" in ldata:
        add_layer(layer_map, order_map, ldata["layer"], lname, order)
        order += 1

oEditor.ImportGDSII(
    [
        "NAME:options",
        "FileName:=",
        os.path.join(path, gds_file),
        "FlattenHierarchy:=",
        True,
        "ImportMethod:=",
        1,
        layer_map,
        "OrderMap:=",
        order_map,
        ["NAME:Structs", ["NAME:GDSIIStruct", "ImportStruct:=", True, "CreateNewCell:=", True, "StructName:=", "SIM1"]],
    ]
)
scale(oEditor, oEditor.GetObjectsInGroup("Sheets"), data["gds_scaling"])

# Create 3D geometry
objects = {}
metal_sheets = []
for lname, ldata in layers.items():
    z = ldata.get("z", 0.0)
    thickness = ldata.get("thickness", 0.0)
    if "layer" in ldata:
        # Get imported objects
        objects[lname] = [n for n in oEditor.GetMatchedObjectName(lname + "_*") if n[len(lname) + 1 :].isdigit()]
        move_vertically(oEditor, objects[lname], z, units)
        thicken_sheet(oEditor, objects[lname], thickness, units)
    else:
        # Create object covering full box
        objects[lname] = [lname]
        if thickness != 0.0:
            create_box(
                oEditor,
                lname,
                box["p1"]["x"],
                box["p1"]["y"],
                z,
                box["p2"]["x"] - box["p1"]["x"],
                box["p2"]["y"] - box["p1"]["y"],
                thickness,
                units,
            )
        else:
            create_rectangle(
                oEditor,
                lname,
                box["p1"]["x"],
                box["p1"]["y"],
                z,
                box["p2"]["x"] - box["p1"]["x"],
                box["p2"]["y"] - box["p1"]["y"],
                "Z",
                units,
            )

    # Set material
    material = ldata.get("material")
    if thickness != 0.0:
        # Solve Inside parameter must be set in hfss_tools simulations to avoid warnings.
        # Solve Inside doesn't exist in 'q3d', so we use None to ignore the parameter.
        solve_inside = lname not in metal_layers if ansys_tool in hfss_tools else None
        set_material(oEditor, objects[lname], material, solve_inside)
    elif lname in metal_layers:  # is metal
        metal_sheets += objects[lname]
    elif lname not in refine_layers and lname not in lumped_rlc_layers:
        set_material(oEditor, objects[lname], None, None)  # set sheet as non-model
    # Note: refine_layers (mesh) and lumped_rlc_layers remain as model objects with no material (unassigned)

    set_color(oEditor, objects[lname], *color_by_material(material, material_dict, thickness == 0.0))

# Assign perfect electric conductor to metal sheets
if metal_sheets:
    if ansys_tool in hfss_tools:
        oBoundarySetup.AssignPerfectE(["NAME:PerfE1", "Objects:=", metal_sheets, "InfGroundPlane:=", False])
    elif ansys_tool == "q3d":
        oBoundarySetup.AssignThinConductor(
            [
                "NAME:ThinCond1",
                "Objects:=",
                metal_sheets,
                "Material:=",
                "pec",
                "Thickness:=",
                "1nm",  # thickness does not matter when material is pec
            ]
        )


# Subtract objects from others. Each tool layer subtraction is performed before it's used as tool for other subtraction.
need_subtraction = [n for n, d in layers.items() if "subtract" in d]
while need_subtraction:
    for name in need_subtraction:
        if not any(s in need_subtraction for s in layers[name]["subtract"]):
            subtract(oEditor, objects[name], [o for n in layers[name]["subtract"] for o in objects[n]], True)
            need_subtraction = [s for s in need_subtraction if s != name]
            break
    else:
        oDesktop.AddMessage("", "", 0, "Encountered circular subtractions in layers {}.".format(need_subtraction))
        break


# Create ports or nets
if ansys_tool in hfss_tools:
    ports = sorted(data["ports"], key=lambda k: k["number"])
    for port in ports:
        is_wave_port = port["type"] == "EdgePort"

        # Check if this is a lumped element (doesn't need polygon)
        is_lumped = port.get("junction", False) or port.get("lumped_element", False)

        if not is_wave_port or not ansys_project_template:
            # Lumped elements don't need polygon geometry - they use imported layer objects
            if not is_lumped:
                if "polygon" not in port:
                    continue

                polyname = "Port%d" % port["number"]

                # Create polygon spanning the two edges
                create_polygon(oEditor, polyname, [list(p) for p in port["polygon"]], units)
                set_color(oEditor, [polyname], 240, 180, 180, 0.8)
            else:
                # For lumped elements, use objects from lumped_rlc layer instead of creating polygon
                # Find the lumped_rlc layer objects to use as boundary geometry
                lumped_layer_name = None
                for lname in layers:
                    if "lumped_rlc" in lname:
                        lumped_layer_name = lname
                        break

                if lumped_layer_name and lumped_layer_name in objects:
                    # Use the first object from lumped_rlc layer
                    polyname = objects[lumped_layer_name][0]
                else:
                    # Fallback: skip this port if no lumped_rlc layer found
                    oDesktop.AddMessage("", "", 2, "Warning: No lumped_rlc layer found for port %d" % port["number"])
                    continue

            if ansys_tool == "hfss":
                ground_objects = [o for n, d in metal_layers.items() if d["excitation"] == 0 for o in objects[n]]
                oBoundarySetup.AutoIdentifyPorts(
                    ["NAME:Faces", int(oEditor.GetFaceIDs(polyname)[0])],
                    is_wave_port,
                    ["NAME:ReferenceConductors"] + ground_objects,
                    str(port["number"]),
                    False,
                )

                renorm = port.get("renormalization", None)
                oBoundarySetup.SetTerminalReferenceImpedances(
                    "" if renorm is None else "{}ohm".format(renorm), str(port["number"]), renorm is not None
                )

                deembed_len = port.get("deembed_len", None)
                if deembed_len is not None:
                    oBoundarySetup.EditWavePort(
                        str(port["number"]),
                        [
                            "Name:%d" % port["number"],
                            "DoDeembed:=",
                            True,
                            "DeembedDist:=",
                            "%f%s" % (deembed_len, units),
                        ],
                    )

            elif ansys_tool == "current":
                oBoundarySetup.AssignCurrent(
                    [
                        "NAME:{}".format(polyname),
                        "Objects:=",
                        [polyname],
                        [
                            "NAME:Direction",
                            "Coordinate System:=",
                            "Global",
                            "Start:=",
                            ["%.32e%s" % (p, units) for p in port["signal_location"]],
                            "End:=",
                            ["%.32e%s" % (p, units) for p in port["ground_location"]],
                        ],
                    ]
                )
            elif ansys_tool == "voltage":
                oBoundarySetup.AssignVoltage(
                    [
                        "NAME:{}".format(polyname),
                        "Objects:=",
                        [polyname],
                        [
                            "NAME:Direction",
                            "Coordinate System:=",
                            "Global",
                            "Start:=",
                            ["%.32e%s" % (p, units) for p in port["signal_location"]],
                            "End:=",
                            ["%.32e%s" % (p, units) for p in port["ground_location"]],
                        ],
                    ]
                )

            elif (port.get("junction", False) or port.get("lumped_element", False)):
                # Create lumped RLC element for junctions or general lumped elements
                # Determine variable prefix based on element type
                if port.get("junction", False):
                    var_prefix = "Lj"  # Junction inductance (for EPR compatibility)
                    element_name = "jj"
                else:
                    var_prefix = "L"   # General lumped element
                    element_name = "elem"

                # Create ANSYS variables for inductance if specified
                if port.get("inductance", 0) != 0:
                    oDesign.ChangeProperty(
                        [
                            "NAME:AllTabs",
                            [
                                "NAME:LocalVariableTab",
                                ["NAME:PropServers", "LocalVariables"],
                                [
                                    "NAME:NewProps",
                                    [
                                        "NAME:%s_%d" % (var_prefix, port["number"]),
                                        "PropType:=",
                                        "VariableProp",
                                        "UserDef:=",
                                        True,
                                        "Value:=",
                                        "%.32eH" % port["inductance"],
                                    ],
                                ],
                            ],
                        ]
                    )

                # Create ANSYS variable for capacitance if specified
                if port.get("capacitance", 0) != 0:
                    cap_var_name = "Cj_%d" if port.get("junction", False) else "C_%d"
                    oDesign.ChangeProperty(
                        [
                            "NAME:AllTabs",
                            [
                                "NAME:LocalVariableTab",
                                ["NAME:PropServers", "LocalVariables"],
                                [
                                    "NAME:NewProps",
                                    [
                                        "NAME:" + (cap_var_name % port["number"]),
                                        "PropType:=",
                                        "VariableProp",
                                        "UserDef:=",
                                        True,
                                        "Value:=",
                                        "%.32efarad" % port["capacitance"],
                                    ],
                                ],
                            ],
                        ]
                    )

                # Create ANSYS variable for resistance if non-default
                if port.get("resistance", 50) != 50:
                    oDesign.ChangeProperty(
                        [
                            "NAME:AllTabs",
                            [
                                "NAME:LocalVariableTab",
                                ["NAME:PropServers", "LocalVariables"],
                                [
                                    "NAME:NewProps",
                                    [
                                        "NAME:R_%d" % port["number"],
                                        "PropType:=",
                                        "VariableProp",
                                        "UserDef:=",
                                        True,
                                        "Value:=",
                                        "%.32eohm" % port["resistance"],
                                    ],
                                ],
                            ],
                        ]
                    )

                # Create lumped RLC boundary condition
                current_start = ["%.32e%s" % (p, units) for p in port["signal_location"]]
                current_end = ["%.32e%s" % (p, units) for p in port["ground_location"]]

                # Get RLC configuration type (parallel or series)
                rlc_config = port.get("rlc_type", "parallel").capitalize()

                # Build RLC parameters
                rlc_params = [
                    "NAME:LumpRLC_%s_%d" % (element_name, port["number"]),
                    "Objects:=",
                    [polyname],
                    [
                        "NAME:CurrentLine",
                        "Coordinate System:=",
                        "Global",
                        "Start:=",
                        current_start,
                        "End:=",
                        current_end,
                    ],
                    "RLC Type:=",
                    rlc_config,
                ]

                # Add inductance if specified
                if port.get("inductance", 0) != 0:
                    rlc_params.extend([
                        "UseInduct:=",
                        True,
                        "Inductance:=",
                        "%s_%d" % (var_prefix, port["number"]),
                    ])
                else:
                    rlc_params.extend(["UseInduct:=", False])

                # Add capacitance if specified
                if port.get("capacitance", 0) != 0:
                    cap_var_name = "Cj_%d" if port.get("junction", False) else "C_%d"
                    rlc_params.extend([
                        "UseCap:=",
                        True,
                        "Capacitance:=",
                        cap_var_name % port["number"],
                    ])
                else:
                    rlc_params.extend(["UseCap:=", False])

                # Add resistance if specified
                if port.get("resistance", 50) != 50:
                    rlc_params.extend([
                        "UseResist:=",
                        True,
                        "Resistance:=",
                        "R_%d" % port["number"],
                    ])
                else:
                    rlc_params.extend(["UseResist:=", False])

                # Add face for boundary assignment
                rlc_params.extend(["Faces:=", [int(oEditor.GetFaceIDs(polyname)[0])]])

                # Assign the lumped RLC
                oBoundarySetup.AssignLumpedRLC(rlc_params)

                if "pyepr" in simulation_flags:
                    # add polyline across junction for voltage across the junction
                    oEditor.CreatePolyline(
                        [
                            "NAME:PolylineParameters",
                            "IsPolylineCovered:=",
                            True,
                            "IsPolylineClosed:=",
                            False,
                            [
                                "NAME:PolylinePoints",
                                [
                                    "NAME:PLPoint",
                                    "X:=",
                                    current_start[0],
                                    "Y:=",
                                    current_start[1],
                                    "Z:=",
                                    current_start[2],
                                ],
                                ["NAME:PLPoint", "X:=", current_end[0], "Y:=", current_end[1], "Z:=", current_end[2]],
                            ],
                            [
                                "NAME:PolylineSegments",
                                ["NAME:PLSegment", "SegmentType:=", "Line", "StartIndex:=", 0, "NoOfPoints:=", 2],
                            ],
                            [
                                "NAME:PolylineXSection",
                                "XSectionType:=",
                                "None",
                                "XSectionOrient:=",
                                "Auto",
                                "XSectionWidth:=",
                                "0" + units,
                                "XSectionTopWidth:=",
                                "0" + units,
                                "XSectionHeight:=",
                                "0" + units,
                                "XSectionNumSegments:=",
                                "0",
                                "XSectionBendType:=",
                                "Corner",
                            ],
                        ],
                        [
                            "NAME:Attributes",
                            "Name:=",
                            "Junction%d" % port["number"],
                            "Flags:=",
                            "",
                            "Color:=",
                            "(143 175 143)",
                            "Transparency:=",
                            0.4,
                            "PartCoordinateSystem:=",
                            "Global",
                            "UDMId:=",
                            "",
                            "MaterialValue:=",
                            '"vacuum"',
                            "SurfaceMaterialValue:=",
                            '""',
                            "SolveInside:=",
                            True,
                            "ShellElement:=",
                            False,
                            "ShellElementThickness:=",
                            "0" + units,
                            "IsMaterialEditable:=",
                            True,
                            "UseMaterialAppearance:=",
                            False,
                            "IsLightweight:=",
                            False,
                        ],
                    )

                    oEditor.ChangeProperty(
                        [
                            "NAME:AllTabs",
                            [
                                "NAME:Geometry3DAttributeTab",
                                ["NAME:PropServers", "Junction%d" % port["number"]],
                                ["NAME:ChangedProps", ["NAME:Show Direction", "Value:=", True]],
                            ],
                        ]
                    )


elif ansys_tool == "q3d":
    # Check if this is an ACRL simulation (needs conductor as SignalNet, not ground)
    # solve_acrl is now defined globally at the top of the script

    excitations = {d["excitation"] for d in metal_layers.values()}
    for excitation in excitations:
        objs = [o for n, d in metal_layers.items() if d["excitation"] == excitation for o in objects[n]]
        if not objs:
            continue
        # For ACRL simulations with ports, treat excitation==0 as Net1 (SignalNet) instead of ground
        # This allows ACRL source/sink assignment on the main conductor
        if excitation == 0 and solve_acrl and len(data.get("ports", [])) > 0:
            oBoundarySetup.AssignSignalNet(["NAME:Net1", "Objects:=", objs])
        elif excitation == 0:
            for i, obj in enumerate(objs):
                oBoundarySetup.AssignGroundNet(["NAME:Ground{}".format(i + 1), "Objects:=", [obj]])
        elif excitation > len(data["ports"]) and data.get("use_floating_islands", False):
            oBoundarySetup.AssignFloatingNet(["NAME:Floating{}".format(excitation), "Objects:=", objs])
        else:
            oBoundarySetup.AssignSignalNet(["NAME:Net{}".format(excitation), "Objects:=", objs])
    oBoundarySetup.AutoIdentifyNets()  # Combine Nets by conductor connections. Order: GroundNet, SignalNet, FloatingNet


# Add field calculations
if data.get("integrate_energies", False) and ansys_tool in hfss_tools:
    # Create term for squared E fields
    oModule = oDesign.GetModule("FieldsReporter")
    add_squared_electric_field_expression(oModule, "Esq", "Mag")
    add_squared_electric_field_expression(oModule, "Ezsq", "ScalarZ")

    # Create energy integral terms for each object
    epsilon_0 = 8.8541878128e-12
    for lname, ldata in layers.items():
        if lname in metal_layers:
            continue

        thickness = ldata.get("thickness", 0.0)
        if thickness == 0.0:
            add_energy_integral_expression(oModule, "Ez_{}".format(lname), objects[lname], "Ezsq", 2, epsilon_0, "")
            add_energy_integral_expression(
                oModule, "Exy_{}".format(lname), objects[lname], "Esq", 2, epsilon_0, "Ez_{}".format(lname)
            )
        else:
            material = ldata.get("material", None)
            if material is not None:
                epsilon = epsilon_0 * material_dict.get(material, {}).get("permittivity", 1.0)
                add_energy_integral_expression(oModule, "E_{}".format(lname), objects[lname], "Esq", 3, epsilon, "")

if data.get("integrate_magnetic_flux", False) and ansys_tool in hfss_tools:
    oModule = oDesign.GetModule("FieldsReporter")
    for lname, ldata in layers.items():
        if ldata.get("thickness", 0.0) != 0.0 or lname in metal_layers:
            continue

        add_magnetic_flux_integral_expression(oModule, "flux_{}".format(lname), objects[lname])

# Manual mesh refinement
mesh_layers_all = []  # Track all mesh layer names for cleanup
for mesh_name, mesh_length in mesh_size.items():
    mesh_layers = [n for n in layers if match_layer(n, mesh_name)]
    mesh_layers_all.extend(mesh_layers)
    mesh_objects = [o for l in mesh_layers if l in objects for o in objects[l]]
    if mesh_objects:
        oMeshSetup = oDesign.GetModule("MeshSetup")
        oMeshSetup.AssignLengthOp(
            [
                "NAME:mesh_size_{}".format(mesh_name),
                "RefineInside:=",
                all(layers[n].get("thickness", 0.0) != 0.0 for n in mesh_layers),
                "Enabled:=",
                True,
                "Objects:=",
                mesh_objects,
                "RestrictElem:=",
                False,
                "RestrictLength:=",
                True,
                "MaxLength:=",
                str(mesh_length) + units,
            ]
        )

# Delete mesh layer objects for ACRL simulations only
# ACRL simulations: Mesh objects cause disjoint net errors, so delete after mesh assignment
# Capacitance-only simulations: Keep mesh objects for proper mesh refinement
if mesh_layers_all and solve_acrl:
    mesh_objects_to_delete = [o for l in set(mesh_layers_all) if l in objects for o in objects[l]]
    if mesh_objects_to_delete:
        oEditor.Delete(["NAME:Selections", "Selections:=", ",".join(mesh_objects_to_delete)])
        # Remove mesh layers from objects dict so they won't be referenced later
        for l in set(mesh_layers_all):
            if l in objects:
                del objects[l]

if not ansys_project_template:
    # Insert analysis setup
    setup = data["analysis_setup"]

    if ansys_tool == "hfss":
        # create setup_list for analysis setup (adaptive meshing) with 3 options:
        # single frequency, multiple frequencies, and broadband between sweep_start and sweep_end
        is_broadband = setup["frequency"] == "broadband"
        multiple_frequency = isinstance(setup["frequency"], list)
        setup_list = ["NAME:Setup1", "AdaptMultipleFreqs:=", multiple_frequency or is_broadband]
        if multiple_frequency:
            max_delta_s = setup["max_delta_s"]
            if not isinstance(type(max_delta_s), list):
                max_delta_s = [max_delta_s] * len(setup["frequency"])  # make max_delta_s a list
            maf_setup_list = ["NAME:MultipleAdaptiveFreqsSetup"]
            for f, s in zip(setup["frequency"], max_delta_s):
                maf_setup_list += [str(f) + setup["frequency_units"] + ":=", [s]]
            setup_list += [maf_setup_list]
        elif is_broadband:
            maf_setup_list = [
                "NAME:MultipleAdaptiveFreqsSetup",
                [
                    "NAME:Broadband",
                    "Low:=",
                    str(setup["sweep_start"]) + setup["frequency_units"],
                    "High:=",
                    str(setup["sweep_end"]) + setup["frequency_units"],
                ],
            ]
            setup_list += [
                maf_setup_list,
                "MaxDeltaS:=",
                setup["max_delta_s"],
            ]
        else:
            setup_list += [
                "Frequency:=",
                str(setup["frequency"]) + setup["frequency_units"],
                "MaxDeltaS:=",
                setup["max_delta_s"],
            ]

        setup_list += [
            "MaximumPasses:=",
            setup["maximum_passes"],
            "MinimumPasses:=",
            setup["minimum_passes"],
            "MinimumConvergedPasses:=",
            setup["minimum_converged_passes"],
            "PercentRefinement:=",
            setup["percent_refinement"],
            "IsEnabled:=",
            True,
            ["NAME:MeshLink", "ImportMesh:=", False],
            "BasisOrder:=",
            setup["basis_order"],
            "DoLambdaRefine:=",
            True,
            "DoMaterialLambda:=",
            True,
            "SetLambdaTarget:=",
            False,
            "Target:=",
            0.3333,
            "UseMaxTetIncrease:=",
            False,
            "PortAccuracy:=",
            0.2,
            "UseABCOnPort:=",
            False,
            "SetPortMinMaxTri:=",
            False,
            "UseDomains:=",
            False,
            "UseIterativeSolver:=",
            setup["use_iterative_solver"],
            "IterativeResidual:=",
            setup["iterative_residual"],
            "SaveRadFieldsOnly:=",
            False,
            "SaveAnyFields:=",
            True,
            "IESolverType:=",
            "Auto",
            "LambdaTargetForIESolver:=",
            0.15,
            "UseDefaultLambdaTgtForIESolver:=",
            True,
        ]
        oAnalysisSetup.InsertSetup("HfssDriven", setup_list)

        oAnalysisSetup.InsertFrequencySweep(
            "Setup1",
            [
                "NAME:Sweep",
                "IsEnabled:=",
                setup["sweep_enabled"],
                "RangeType:=",
                "LinearCount",
                "RangeStart:=",
                str(setup["sweep_start"]) + setup["frequency_units"],
                "RangeEnd:=",
                str(setup["sweep_end"]) + setup["frequency_units"],
                "RangeCount:=",
                setup["sweep_count"],
                "Type:=",
                setup["sweep_type"],
                "SaveFields:=",
                False,
                "SaveRadFields:=",
                False,
                "InterpTolerance:=",
                0.5,
                "InterpMaxSolns:=",
                250,
                "InterpMinSolns:=",
                0,
                "InterpMinSubranges:=",
                1,
                "ExtrapToDC:=",
                setup["sweep_start"] == 0,
                "MinSolvedFreq:=",
                "0.01GHz",
                "InterpUseS:=",
                True,
                "InterpUsePortImped:=",
                True,
                "InterpUsePropConst:=",
                True,
                "UseDerivativeConvergence:=",
                False,
                "InterpDerivTolerance:=",
                0.2,
                "UseFullBasis:=",
                True,
                "EnforcePassivity:=",
                True,
                "PassivityErrorTolerance:=",
                0.0001,
                "EnforceCausality:=",
                False,
            ],
        )
    elif ansys_tool in ["current", "voltage"]:
        oAnalysisSetup.InsertSetup(
            "HfssDriven",
            [
                "NAME:Setup1",
                "SolveType:=",
                "Single",
                "Frequency:=",
                str(setup["frequency"]) + setup["frequency_units"],
                "MaxDeltaE:=",
                setup["max_delta_e"],
                "MaximumPasses:=",
                setup["maximum_passes"],
                "MinimumPasses:=",
                setup["minimum_passes"],
                "MinimumConvergedPasses:=",
                setup["minimum_converged_passes"],
                "PercentRefinement:=",
                setup["percent_refinement"],
                "IsEnabled:=",
                True,
                ["NAME:MeshLink", "ImportMesh:=", False],
                "BasisOrder:=",
                setup["basis_order"],
                "UseIterativeSolver:=",
                setup["use_iterative_solver"],
                "IterativeResidual:=",
                setup["iterative_residual"],
                "DoLambdaRefine:=",
                True,
                "DoMaterialLambda:=",
                True,
                "SetLambdaTarget:=",
                False,
                "Target:=",
                0.3333,
                "UseMaxTetIncrease:=",
                False,
                "DrivenSolverType:=",
                "Direct Solver",
                "EnhancedLowFreqAccuracy:=",
                False,
                "SaveRadFieldsOnly:=",
                False,
                "SaveAnyFields:=",
                True,
                "IESolverType:=",
                "Auto",
                "LambdaTargetForIESolver:=",
                0.15,
                "UseDefaultLambdaTgtForIESolver:=",
                True,
                "IE Solver Accuracy:=",
                "Balanced",
                "InfiniteSphereSetup:=",
                "",
            ],
        )
    elif ansys_tool == "q3d":
        # Check if ACRL (inductance/resistance) extraction is enabled
        solve_acrl = setup.get("solve_acrl", False)
        oDesktop.AddMessage("", "", 0, "Q3D setup: solve_acrl = {}".format(solve_acrl))

        # Build setup parameters
        setup_params = [
            "NAME:Setup1",
            "AdaptiveFreq:=",
            str(setup["frequency"]) + setup["frequency_units"],
            "SaveFields:=",
            False,
            "Enabled:=",
            True,
        ]

        # Choose between Cap-only or ACRL-only mode
        if solve_acrl:
            oDesktop.AddMessage("", "", 0, "Creating ACRL (AC block) setup")
            # ACRL mode: Only AC block (skip Cap to avoid conflicts)
            setup_params.append([
                "NAME:AC",
                "MaxPass:=",
                setup["maximum_passes"],
                "MinPass:=",
                setup["minimum_passes"],
                "MinConvPass:=",
                setup["minimum_converged_passes"],
                "PerError:=",
                setup["percent_error"],
                "PerRefine:=",
                setup["percent_refinement"],
                "AutoIncreaseSolutionOrder:=",
                True,
                "SolutionOrder:=",
                "High",
                "Solver Type:=",
                "Iterative",
                "ACRLSolverType:=",
                "ACA",
            ])
        else:
            # Capacitance-only mode: Only Cap block
            setup_params.append([
                "NAME:Cap",
                "MaxPass:=",
                setup["maximum_passes"],
                "MinPass:=",
                setup["minimum_passes"],
                "MinConvPass:=",
                setup["minimum_converged_passes"],
                "PerError:=",
                setup["percent_error"],
                "PerRefine:=",
                setup["percent_refinement"],
                "AutoIncreaseSolutionOrder:=",
                True,
                "SolutionOrder:=",
                "High",
                "Solver Type:=",
                "Iterative",
            ])

        oAnalysisSetup.InsertSetup("Matrix", setup_params)

        # Configure source/sink for ACRL if enabled
        if solve_acrl:
            # Get ACRL source/sink configuration
            acrl_sources = setup.get("acrl_sources", {})

            # If no explicit acrl_sources, try to derive from extra_json_data or ports
            if not acrl_sources:
                # First try extra_json_data (preferred method - doesn't create port excitations)
                # extra_json_data is in parameters section
                params = data.get("parameters", {})
                extra_data = params.get("extra_json_data", {})
                acrl_locs = extra_data.get("acrl_port_locations", {})

                # Check if using numbered format (new): {1: {"source": [...], "sink": [...]}, 2: {...}}
                if acrl_locs and isinstance(acrl_locs.get(next(iter(acrl_locs.keys()), 1)), dict):
                    # Numbered format - create source/sink for each numbered inductor
                    acrl_sources = {}
                    for num, locs in acrl_locs.items():
                        if "source" in locs and "sink" in locs:
                            acrl_sources["Net{}".format(num)] = {
                                "source_location": locs["source"],
                                "sink_location": locs["sink"],
                            }
                # Check if using legacy format (old): {"source": [...], "sink": [...]}
                elif "source" in acrl_locs and "sink" in acrl_locs:
                    acrl_sources = {
                        "Net1": {
                            "source_location": acrl_locs["source"],
                            "sink_location": acrl_locs["sink"],
                        }
                    }
                # Fallback: try ports (legacy method)
                elif "ports" in data and len(data["ports"]) >= 2:
                    port1 = data["ports"][0]
                    port2 = data["ports"][1]
                    if "signal_location" in port1 and "signal_location" in port2:
                        acrl_sources = {
                            "Net1": {
                                "source_location": port1["signal_location"],
                                "sink_location": port2["signal_location"],
                            }
                        }

            if acrl_sources:
                # User specified source/sink locations manually
                try:
                    # Get all excitations to find signal nets
                    excitations = oBoundarySetup.GetExcitations()
                    nets = excitations[::2]
                    net_types = excitations[1::2]

                    # Helper function to find edge nearest to a location on a specific net
                    def find_nearest_edge(target_location, net_name, tolerance=1e-3):
                        """Find edge ID closest to target location [x, y, z] on objects belonging to net_name"""
                        best_edge = None
                        best_distance = float('inf')

                        # Get objects assigned to this net
                        try:
                            # Get the signal net properties to find which objects belong to it
                            all_objs = oEditor.GetObjectsInGroup("Sheets")
                            # Filter to only metal sheets (excludes substrate, vacuum, etc.)
                            obj_names = [obj for obj in all_objs if obj in metal_sheets]
                        except:
                            # Fallback: just use metal_sheets
                            obj_names = metal_sheets

                        for obj_name in obj_names:
                            try:
                                edges = oEditor.GetEdgeIDsFromObject(obj_name)
                                if not edges:
                                    continue

                                for edge_id in edges:
                                    # Get edge center position
                                    try:
                                        # Get vertices of the edge
                                        vertices = oEditor.GetVertexIDsFromEdge(edge_id)
                                        if len(vertices) >= 2:
                                            # Get positions of first two vertices (convert strings to floats)
                                            pos1_raw = oEditor.GetVertexPosition(vertices[0])
                                            pos2_raw = oEditor.GetVertexPosition(vertices[1])
                                            pos1 = [float(x) for x in pos1_raw]
                                            pos2 = [float(x) for x in pos2_raw]

                                            # Calculate edge center
                                            edge_center = [
                                                (pos1[0] + pos2[0]) / 2.0,
                                                (pos1[1] + pos2[1]) / 2.0,
                                                (pos1[2] + pos2[2]) / 2.0,
                                            ]

                                            # Calculate distance to target
                                            # Ensure target_location has 3 components (handle 2D input)
                                            if len(target_location) == 2:
                                                target_3d = [target_location[0], target_location[1], 0.0]
                                            else:
                                                target_3d = target_location

                                            dx = edge_center[0] - target_3d[0]
                                            dy = edge_center[1] - target_3d[1]
                                            dz = edge_center[2] - target_3d[2]
                                            distance = (dx**2 + dy**2 + dz**2)**0.5

                                            if distance < best_distance:
                                                best_distance = distance
                                                best_edge = edge_id
                                    except:
                                        pass
                            except:
                                pass

                        return best_edge, best_distance

                    # Assign source/sink for each net with specified locations
                    for net_name, net_type in zip(nets, net_types):
                        if net_type == "SignalNet" and net_name in acrl_sources:
                            net_config = acrl_sources[net_name]
                            source_loc = net_config.get("source_location")
                            sink_loc = net_config.get("sink_location")

                            if source_loc and sink_loc:
                                try:
                                    # Find edges nearest to specified locations on metal conductor objects only
                                    source_edge_id, source_dist = find_nearest_edge(source_loc, net_name)
                                    sink_edge_id, sink_dist = find_nearest_edge(sink_loc, net_name)

                                    if source_edge_id and sink_edge_id:
                                        # Assign source
                                        oBoundarySetup.AssignSource(
                                            [
                                                "NAME:Source_" + net_name,
                                                "Edges:=", [int(source_edge_id)],
                                                "TerminalType:=", "ConstantVoltage",
                                                "Net:=", net_name,
                                            ]
                                        )

                                        # Assign sink
                                        oBoundarySetup.AssignSink(
                                            [
                                                "NAME:Sink_" + net_name,
                                                "Edges:=", [int(sink_edge_id)],
                                                "TerminalType:=", "ConstantVoltage",
                                                "Net:=", net_name,
                                            ]
                                        )
                                    else:
                                        oDesktop.AddMessage("", "", 2, "Warning: Could not find edges for {}: source_edge={}, sink_edge={}".format(
                                            net_name, source_edge_id, sink_edge_id))
                                except Exception as e:
                                    oDesktop.AddMessage("", "", 2, "Warning: Failed to assign source/sink for {}: {}".format(net_name, str(e)))
                except Exception as e:
                    oDesktop.AddMessage("", "", 2, "Warning: ACRL source/sink assignment failed: " + str(e))

    elif ansys_tool == "eigenmode":
        # Create EM setup
        setup_list = [
            "NAME:Setup1",
            "MinimumFrequency:=",
            str(setup["min_frequency"]) + setup["frequency_units"],
            "NumModes:=",
            setup["n_modes"],
            "MaxDeltaFreq:=",
            setup["max_delta_f"],
            "ConvergeOnRealFreq:=",
            True,
            "MaximumPasses:=",
            setup["maximum_passes"],
            "MinimumPasses:=",
            setup["minimum_passes"],
            "MinimumConvergedPasses:=",
            setup["minimum_converged_passes"],
            "PercentRefinement:=",
            setup["percent_refinement"],
            "IsEnabled:=",
            True,
            "BasisOrder:=",
            setup["basis_order"],
        ]
        oAnalysisSetup.InsertSetup("HfssEigen", setup_list)

else:  # use ansys_project_template
    # delete substrate and vacuum objects
    delete(oEditor, [o for n, v in objects.items() if "substrate" in n or "vacuum" in n for o in v])

    scriptpath = os.path.dirname(__file__)
    aedt_path = os.path.join(scriptpath, "../")
    basename = os.path.splitext(os.path.basename(jsonfile))[0]
    build_geom_name = basename + "_build_geometry"
    template_path = data["ansys_project_template"]
    template_basename = os.path.splitext(os.path.basename(template_path))[0]

    oProject = oDesktop.GetActiveProject()
    oProject.SaveAs(os.path.join(aedt_path, build_geom_name + ".aedt"), True)

    oDesign = oProject.GetActiveDesign()
    oEditor = oDesign.SetActiveEditor("3D Modeler")
    sheet_name_list = oEditor.GetObjectsInGroup("Sheets") + oEditor.GetObjectsInGroup("Solids")
    oEditor.Copy(["NAME:Selections", "Selections:=", ",".join(sheet_name_list)])

    oDesktop.OpenProject(os.path.join(aedt_path, template_path))
    oProject = oDesktop.SetActiveProject(template_basename)
    oDesign = oProject.GetActiveDesign()
    oEditor = oDesign.SetActiveEditor("3D Modeler")
    oEditor.Paste()
    oDesktop.CloseProject(build_geom_name)


# Fit window to objects
oEditor.FitAll()

# pylint: enable=consider-using-f-string
