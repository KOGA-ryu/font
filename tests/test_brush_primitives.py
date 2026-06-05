import unittest

from glyph_lab.brush_primitives import brush_metadata, brush_stamp, dry_brush, spray, stipple
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


if __name__ == "__main__":
    unittest.main()
