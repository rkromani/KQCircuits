"""Q3D capacitance simulation for a trench capacitor.

Tests the 3D conformal metal pipeline: substrate trench + vertical wall sheets + floor metal.
The trench walls contribute the dominant capacitance between the two electrodes.

Run with:
    env-kqcircuits-py312\Scripts\python.exe klayout_package\python\scripts\simulations\trench_cap_q3d_sim.py --no-gui
"""

import argparse
import logging
import sys
from pathlib import Path

from kqcircuits.pya_resolver import pya
from kqcircuits.simulations.export.ansys.ansys_export import export_ansys
from kqcircuits.simulations.export.simulation_export import export_simulation_oas, cross_sweep_simulation
from kqcircuits.elements.trench_capacitor import TrenchCapacitor
from kqcircuits.simulations.port import InternalPort
from kqcircuits.simulations.post_process import PostProcess
from kqcircuits.simulations.single_element_simulation import get_single_element_sim_class
from kqcircuits.util.export_helper import (
    create_or_empty_tmp_directory,
    get_active_or_new_layout,
    open_with_klayout_or_default_application,
)

parser = argparse.ArgumentParser(description="Q3D simulation for trench capacitor")
parser.add_argument("--no-gui", action="store_true", help="Skip opening KLayout")
args = parser.parse_args()

dir_path = create_or_empty_tmp_directory(Path(__file__).stem + "_output")

BaseSimClass = get_single_element_sim_class(TrenchCapacitor)


class TrenchCapQ3dSim(BaseSimClass):
    """Q3D simulation that places an internal port on electrode A (signal net).

    Electrode B remains ground. Q3D extracts the capacitance matrix between them,
    which includes the contribution from the vertical trench walls.
    """

    def build(self):
        super().build()
        self.ports = []

        # Signal at center of electrode A (left electrode), top surface
        signal_loc = self.refpoints["electrode_a"]
        self.ports.append(
            InternalPort(
                number=1,
                signal_location=signal_loc,
                ground_location=None,
            )
        )


SimClass = TrenchCapQ3dSim

logging.basicConfig(level=logging.WARN, stream=sys.stdout)
layout = get_active_or_new_layout()

sim_parameters = {
    "name": "trench_cap_q3d",
    "use_internal_ports": True,
    "use_ports": True,
    "box": pya.DBox(pya.DPoint(-200, -200), pya.DPoint(200, 200)),
    "face_stack": ["1t1"],
    "trench_depth": 5.0,   # 5 um deep trench
}

export_parameters = {
    "path": dir_path,
    "ansys_tool": "q3d",
    "post_process": PostProcess("produce_cmatrix_table.py"),
    "exit_after_run": False,
    "percent_error": 0.5,
    "minimum_converged_passes": 2,
    "maximum_passes": 15,
    "mesh_size": {
        "1t1_mesh_4": 5,
    },
}

simulations = cross_sweep_simulation(
    layout,
    SimClass,
    sim_parameters,
    {
        "trench_depth": [1.0, 2.5, 5.0, 10, 15],
        "electrode_gap_width": [0.95, 1.9],
    },
)

export_ansys(simulations, **export_parameters)
oas_file = export_simulation_oas(simulations, dir_path)

print(f"Exported {len(simulations)} Q3D simulation(s) to: {dir_path}")
print(f"OAS file: {oas_file}")
print(f"\nNext step: run ANSYS simulations via {dir_path}/simulation.bat")

if not args.no_gui:
    open_with_klayout_or_default_application(oas_file)
else:
    print("Skipping KLayout GUI (--no-gui flag set)")
