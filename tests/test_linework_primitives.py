import unittest

from glyph_lab.linework_primitives import hatch_pattern, linework_corner, linework_line, linework_metadata
from glyph_lab.measure import measure_stamp
from glyph_lab.transforms import stamp_to_bitmask


class LineworkPrimitiveTests(unittest.TestCase):
    def test_horizontal_top_line_sets_top_row(self):
        stamp = linework_line("horizontal", offset="top")

        self.assertEqual(stamp_to_bitmask(stamp), 0b0000000000001111)

    def test_vertical_right_line_sets_right_column(self):
        stamp = linework_line("vertical", offset="right")

        self.assertEqual(stamp_to_bitmask(stamp), (1 << 3) | (1 << 7) | (1 << 11) | (1 << 15))

    def test_soft_corner_has_lower_density_than_sharp_corner(self):
        sharp = measure_stamp(linework_corner("top_left", radius="sharp"))["density"]
        soft = measure_stamp(linework_corner("top_left", radius="soft"))["density"]

        self.assertLess(soft, sharp)

    def test_cross_hatch_has_more_density_than_light_diagonal_hatch(self):
        cross = measure_stamp(hatch_pattern("cross", density="medium"))["density"]
        diagonal = measure_stamp(hatch_pattern("diagonal_rise", density="light"))["density"]

        self.assertGreater(cross, diagonal)

    def test_linework_metadata_records_angle_and_connector_sides(self):
        metadata = linework_metadata(
            {
                "kind": "line",
                "params": {"direction": "vertical", "offset": "left", "thickness": 1},
            }
        )

        self.assertEqual(metadata["angle_degrees"], 90.0)
        self.assertEqual(metadata["connector_sides"], ["top", "bottom", "left"])


if __name__ == "__main__":
    unittest.main()
