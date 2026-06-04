import unittest

from glyph_lab.atlas import stamp_for_index
from glyph_lab.measure import measure_stamp


class MeasureTests(unittest.TestCase):
    def test_solid_density_is_one(self):
        self.assertEqual(measure_stamp(stamp_for_index(1))["density"], 1.0)

    def test_empty_density_is_zero(self):
        self.assertEqual(measure_stamp(stamp_for_index(0))["density"], 0.0)

    def test_vertical_edge_touches_top_and_bottom(self):
        contacts = measure_stamp(stamp_for_index(15))["edge_contacts"]
        self.assertTrue(contacts["top"])
        self.assertTrue(contacts["bottom"])

    def test_horizontal_edge_touches_left_and_right(self):
        contacts = measure_stamp(stamp_for_index(14))["edge_contacts"]
        self.assertTrue(contacts["left"])
        self.assertTrue(contacts["right"])


if __name__ == "__main__":
    unittest.main()
