from kqcircuits.pya_resolver import pya
from kqcircuits.util.parameters import Param, pdt
from kqcircuits.elements.element import Element


class TrenchCapacitor(Element):
    """Parallel-plate capacitor whose electrodes conform to a substrate trench.

        """

    electrode_height = Param(pdt.TypeDouble, "Height of each electrode (x)", 30, unit="um")
    electrode_gap_width = Param(pdt.TypeDouble, "Gap between electrodes (central gap)", 1.9, unit="um")
    electrode_width = Param(pdt.TypeDouble, "Width of each electrode", 10, unit="um")
    electrode_ground_gap = Param(pdt.TypeDouble, "Gap between electrodes and ground", 20, unit="um")
    trench_height = Param(pdt.TypeDouble, "Trench height", 100, unit="um")
    trench_width = Param(pdt.TypeDouble, "Trench width ", 2, unit="um")

    def build(self):

        pts_trench = [
            pya.DPoint(self.trench_width/2, self.trench_height/2),
            pya.DPoint(self.trench_width/2, -self.trench_height/2),
            pya.DPoint(-self.trench_width/2, -self.trench_height/2),
            pya.DPoint(-self.trench_width/2, self.trench_height/2),
        ]
        region_trench = pya.Region(pya.DPolygon(pts_trench).to_itype(self.layout.dbu))

        self.cell.shapes(self.get_layer("trench_etch")).insert(
            region_trench
        )

        pts_left_electrode = [
            pya.DPoint(-self.electrode_gap_width/2 - self.electrode_width, self.electrode_height/2),
            pya.DPoint(-self.electrode_gap_width/2 - self.electrode_width, -self.electrode_height/2),
            pya.DPoint(-self.electrode_gap_width/2, -self.electrode_height/2),
            pya.DPoint(-self.electrode_gap_width/2, self.electrode_height/2),
        ]
        region_left_electrode = pya.Region(pya.DPolygon(pts_left_electrode).to_itype(self.layout.dbu))
        pts_right_electrode = [
            pya.DPoint(self.electrode_gap_width/2 + self.electrode_width, self.electrode_height/2),
            pya.DPoint(self.electrode_gap_width/2 + self.electrode_width, -self.electrode_height/2),
            pya.DPoint(self.electrode_gap_width/2, -self.electrode_height/2),
            pya.DPoint(self.electrode_gap_width/2, self.electrode_height/2),
        ]
        region_right_electrode = pya.Region(pya.DPolygon(pts_right_electrode).to_itype(self.layout.dbu))

        pts_gap = [
            pya.DPoint(-self.electrode_gap_width/2 - self.electrode_width - self.electrode_ground_gap, self.electrode_height/2 + self.electrode_ground_gap),
            pya.DPoint(self.electrode_gap_width/2 + self.electrode_width + self.electrode_ground_gap, self.electrode_height/2 + self.electrode_ground_gap),
            pya.DPoint(self.electrode_gap_width/2 + self.electrode_width + self.electrode_ground_gap, -self.electrode_height/2 - self.electrode_ground_gap),
            pya.DPoint(-self.electrode_gap_width/2 - self.electrode_width - self.electrode_ground_gap, -self.electrode_height/2 - self.electrode_ground_gap),
        ]
        region_gap = pya.Region(pya.DPolygon(pts_gap).to_itype(self.layout.dbu))

        self.cell.shapes(self.get_layer("base_metal_gap_wo_grid")).insert(
            region_gap - region_left_electrode - region_right_electrode
        )

        # Refpoints at center of each electrode pad (on top surface, z=0)
        self.refpoints["electrode_a"] = pya.DPoint(-(self.electrode_gap_width / 2 + self.electrode_width / 2), 0)
        self.refpoints["electrode_b"] = pya.DPoint(self.electrode_gap_width / 2 + self.electrode_width / 2, 0)
