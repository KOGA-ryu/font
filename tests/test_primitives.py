import unittest

from glyph_lab.measure import measure_stamp
from glyph_lab.primitives import fill, line, point, primitive_stamp
from glyph_lab.transforms import stamp_to_bitmask


class PrimitiveTests(unittest.TestCase):
    def test_point_sets_exactly_one_pixel(self):
        stamp = point(1, 2)

        self.assertEqual(measure_stamp(stamp)["density"], 1 / 16)
        self.assertEqual(stamp_to_bitmask(stamp), 1 << (2 * 4 + 1))

    def test_horizontal_line_touches_left_and_right(self):
        contacts = measure_stamp(line("horizontal"))["edge_contacts"]

        self.assertTrue(contacts["left"])
        self.assertTrue(contacts["right"])

    def test_vertical_line_touches_top_and_bottom(self):
        contacts = measure_stamp(line("vertical"))["edge_contacts"]

        self.assertTrue(contacts["top"])
        self.assertTrue(contacts["bottom"])

    def test_diagonals_generate_expected_pixel_patterns(self):
        rise = stamp_to_bitmask(line("diagonal_rise"))
        fall = stamp_to_bitmask(line("diagonal_fall"))

        self.assertEqual(rise, (1 << 3) | (1 << 6) | (1 << 9) | (1 << 12))
        self.assertEqual(fall, (1 << 0) | (1 << 5) | (1 << 10) | (1 << 15))

    def test_thickness_two_line_has_higher_density(self):
        thin = measure_stamp(line("horizontal", thickness=1))["density"]
        thick = measure_stamp(line("horizontal", thickness=2))["density"]

        self.assertGreater(thick, thin)

    def test_broken_line_has_lower_density_than_unbroken(self):
        unbroken = measure_stamp(line("horizontal", thickness=1))["density"]
        broken = measure_stamp(line("horizontal", thickness=1, broken=True))["density"]

        self.assertLess(broken, unbroken)

    def test_checker_fill_density_is_half(self):
        self.assertEqual(measure_stamp(fill("checker"))["density"], 0.5)

    def test_noise_fill_is_deterministic_for_seed(self):
        first = stamp_to_bitmask(fill("noise", seed=7))
        second = stamp_to_bitmask(fill("noise", seed=7))

        self.assertEqual(first, second)

    def test_invalid_primitive_params_raise_clear_error(self):
        with self.assertRaisesRegex(ValueError, "unknown params"):
            primitive_stamp("point", x=1, y=2, z=3)


if __name__ == "__main__":
    unittest.main()
