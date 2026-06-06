import unittest

from glyph_lab.brush_primitives import (
    brush_metadata,
    brush_stamp,
    chip,
    default_brush_specs,
    dry_brush,
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


if __name__ == "__main__":
    unittest.main()
