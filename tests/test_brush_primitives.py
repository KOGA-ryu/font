import unittest

from glyph_lab.brush_primitives import (
    brush_metadata,
    brush_stamp,
    charcoal_drag,
    chip,
    default_brush_specs,
    dot_field,
    dry_brush,
    edge_wear,
    scratch,
    spray,
    stipple,
    tone_hatch,
)
from glyph_lab.measure import measure_stamp
from glyph_lab.transforms import stamp_to_bitmask


class BrushPrimitiveTests(unittest.TestCase):
    def test_stipple_sparse_has_lower_density_than_dense(self):
        sparse = measure_stamp(stipple("sparse"))["density"]
        dense = measure_stamp(stipple("dense", seed=11))["density"]

        self.assertLess(sparse, dense)

    def test_spray_is_deterministic_for_same_seed(self):
        first = stamp_to_bitmask(spray("medium", seed=17, direction="left"))
        second = stamp_to_bitmask(spray("medium", seed=17, direction="left"))

        self.assertEqual(first, second)

    def test_dry_brush_has_lower_density_than_heavy_dry_brush(self):
        light = measure_stamp(dry_brush("horizontal", "light"))["density"]
        heavy = measure_stamp(dry_brush("horizontal", "heavy"))["density"]

        self.assertLess(light, heavy)

    def test_brush_stamp_rejects_unknown_family(self):
        with self.assertRaisesRegex(ValueError, "brush_family"):
            brush_stamp("unknown")

    def test_brush_metadata_includes_engine_and_fallback(self):
        metadata = brush_metadata(
            {
                "brush_family": "hatch",
                "params": {"angle": "diagonal_rise", "density": "light"},
            }
        )

        self.assertEqual(metadata["brush_engine"], "directional-stroke")
        self.assertEqual(metadata["ascii_fallback"], "/")

    def test_scratch_long_has_more_density_than_short(self):
        short = measure_stamp(scratch("horizontal", "short"))["density"]
        long = measure_stamp(scratch("horizontal", "long"))["density"]

        self.assertGreater(long, short)

    def test_broken_scratch_has_lower_density_than_unbroken(self):
        unbroken = measure_stamp(scratch("vertical", "long"))["density"]
        broken = measure_stamp(scratch("vertical", "long", broken=True))["density"]

        self.assertLess(broken, unbroken)

    def test_chip_large_has_more_density_than_small(self):
        small = measure_stamp(chip("left", "small"))["density"]
        large = measure_stamp(chip("left", "large"))["density"]

        self.assertGreater(large, small)

    def test_damage_brush_specs_are_generic_detail_packages(self):
        specs = [spec for spec in default_brush_specs() if spec["brush_family"] in {"scratch", "chip"}]
        families = {spec["brush_family"] for spec in specs}

        self.assertEqual(families, {"scratch", "chip"})
        self.assertTrue(all(spec["role"] == "detail" for spec in specs))
        self.assertTrue(all(spec["family"] == "damage" for spec in specs))

    def test_tone_hatch_gradient_has_mid_density(self):
        density = measure_stamp(tone_hatch("gradient_left"))["density"]

        self.assertEqual(density, 6 / 16)

    def test_tone_hatch_contour_differs_from_straight_hatch(self):
        contour = stamp_to_bitmask(tone_hatch("contour_rise"))
        straight = stamp_to_bitmask(brush_stamp("hatch", angle="diagonal_rise", density="medium"))

        self.assertNotEqual(contour, straight)

    def test_tone_hatch_metadata_records_engine(self):
        metadata = brush_metadata(
            {
                "brush_family": "tone_hatch",
                "params": {"pattern": "woven"},
            }
        )

        self.assertEqual(metadata["brush_engine"], "tone-hatch")
        self.assertEqual(metadata["density_class"], "woven")
        self.assertEqual(metadata["ascii_fallback"], "+")

    def test_dot_field_dense_has_more_density_than_light(self):
        light = measure_stamp(dot_field("dust_light"))["density"]
        dense = measure_stamp(dot_field("dust_dense"))["density"]

        self.assertGreater(dense, light)

    def test_dot_field_is_deterministic(self):
        first = stamp_to_bitmask(dot_field("pitted_surface"))
        second = stamp_to_bitmask(dot_field("pitted_surface"))

        self.assertEqual(first, second)

    def test_dot_field_metadata_records_engine(self):
        metadata = brush_metadata(
            {
                "brush_family": "dot_field",
                "params": {"pattern": "speckle_even"},
            }
        )

        self.assertEqual(metadata["brush_engine"], "dot-field")
        self.assertEqual(metadata["density_class"], "speckle_even")
        self.assertEqual(metadata["ascii_fallback"], "*")

    def test_charcoal_drag_heavy_has_more_density_than_light(self):
        light = measure_stamp(charcoal_drag("horizontal", "light"))["density"]
        heavy = measure_stamp(charcoal_drag("horizontal", "heavy"))["density"]

        self.assertGreater(heavy, light)

    def test_charcoal_drag_is_deterministic(self):
        first = stamp_to_bitmask(charcoal_drag("diagonal_rise", "medium"))
        second = stamp_to_bitmask(charcoal_drag("diagonal_rise", "medium"))

        self.assertEqual(first, second)

    def test_charcoal_drag_metadata_records_engine(self):
        metadata = brush_metadata(
            {
                "brush_family": "charcoal_drag",
                "params": {"direction": "vertical", "pressure": "medium"},
            }
        )

        self.assertEqual(metadata["brush_engine"], "charcoal-drag")
        self.assertEqual(metadata["density_class"], "medium")
        self.assertEqual(metadata["ascii_fallback"], "|")

    def test_edge_wear_broken_has_more_density_than_nick(self):
        nick = measure_stamp(edge_wear("left", "nick"))["density"]
        broken = measure_stamp(edge_wear("left", "broken"))["density"]

        self.assertGreater(broken, nick)

    def test_edge_wear_is_deterministic(self):
        first = stamp_to_bitmask(edge_wear("corner_bottom_right", "broken"))
        second = stamp_to_bitmask(edge_wear("corner_bottom_right", "broken"))

        self.assertEqual(first, second)

    def test_edge_wear_metadata_records_engine(self):
        metadata = brush_metadata(
            {
                "brush_family": "edge_wear",
                "params": {"side": "top", "wear": "rubbed"},
            }
        )

        self.assertEqual(metadata["brush_engine"], "edge-wear")
        self.assertEqual(metadata["density_class"], "rubbed")
        self.assertEqual(metadata["ascii_fallback"], "x")


if __name__ == "__main__":
    unittest.main()
