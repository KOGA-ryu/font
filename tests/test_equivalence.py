import unittest

from glyph_lab.atlas import generated_variant_demo, stamp_for_index
from glyph_lab.equivalence import canonical_bitmask
from glyph_lab.transforms import bitmask_to_stamp, shift


class EquivalenceTests(unittest.TestCase):
    def test_diagonal_rise_and_fall_share_mirror_canonical_id(self):
        rise = canonical_bitmask(stamp_for_index(16), "mirrors")[0]
        fall = canonical_bitmask(stamp_for_index(17), "mirrors")[0]

        self.assertEqual(rise, fall)

    def test_corner_top_left_and_bottom_right_share_dihedral8_id(self):
        top_left = canonical_bitmask(stamp_for_index(18), "dihedral8")[0]
        bottom_right = canonical_bitmask(stamp_for_index(21), "dihedral8")[0]

        self.assertEqual(top_left, bottom_right)

    def test_exact_equivalence_does_not_collapse_shifted_dots(self):
        dot = bitmask_to_stamp(1 << 5)
        shifted = shift(dot, 1, 0)

        self.assertNotEqual(canonical_bitmask(dot, "exact")[0], canonical_bitmask(shifted, "exact")[0])

    def test_normalized_translation_equivalence_collapses_dot_variants(self):
        dot = bitmask_to_stamp(1 << 5)
        shifted = shift(dot, 1, 1)

        self.assertEqual(
            canonical_bitmask(dot, "translations_normalized")[0],
            canonical_bitmask(shifted, "translations_normalized")[0],
        )

    def test_generated_variant_metadata_records_lineage(self):
        variants = generated_variant_demo()
        diagonal_fall = next(variant for variant in variants if variant.token == "\\")

        self.assertTrue(diagonal_fall.generated)
        self.assertIn("diagonal_rise", diagonal_fall.source_glyph_id)
        self.assertEqual(diagonal_fall.transform_chain, ["flip_horizontal"])
        self.assertEqual(diagonal_fall.layer, "edge")
        self.assertEqual(diagonal_fall.palette_role, "ink")


if __name__ == "__main__":
    unittest.main()
