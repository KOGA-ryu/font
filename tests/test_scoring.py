import unittest

from glyph_lab.atlas import stamp_for_index
from glyph_lab.measure import measure_stamp
from glyph_lab.scoring import score_glyph
from glyph_lab.transforms import bitmask_to_stamp, stamp_to_bitmask


def record(role, family, stamp):
    features = measure_stamp(stamp)
    features["bitmask"] = stamp_to_bitmask(stamp)
    return {
        "id": f"test.{role}.{family}",
        "token": "?",
        "index": 0,
        "role": role,
        "family": family,
        "layer": "edge" if role == "edge" else "detail",
        "palette_role": "ink",
        "cell_size": 4,
        "features": features,
        "constraints": {},
    }


class ScoringTests(unittest.TestCase):
    def test_empty_glyph_scores_low_unless_role_is_empty(self):
        empty = score_glyph(record("empty", "none", stamp_for_index(0)))
        non_empty = score_glyph(record("edge", "horizontal", stamp_for_index(0)))

        self.assertLess(empty["usefulness_score"], 0.3)
        self.assertIsNone(empty["rejection_reason"])
        self.assertEqual(non_empty["rejection_reason"], "empty-density-for-non-empty-role")

    def test_solid_glyph_is_accepted_for_mass_or_solid_role(self):
        scored = score_glyph(record("mass", "solid", stamp_for_index(1)))

        self.assertIsNone(scored["rejection_reason"])
        self.assertIn("solid", scored["review_tags"])

    def test_solid_glyph_is_rejected_for_edge_role(self):
        scored = score_glyph(record("edge", "horizontal", stamp_for_index(1)))

        self.assertEqual(scored["rejection_reason"], "solid-density-for-non-solid-role")

    def test_vertical_edge_with_top_bottom_contacts_scores_as_edge(self):
        scored = score_glyph(record("edge", "vertical", stamp_for_index(15)))

        self.assertIsNone(scored["rejection_reason"])
        self.assertGreater(scored["usefulness_score"], 0.5)

    def test_scoring_output_includes_score_and_tags(self):
        scored = score_glyph(record("detail", "damage", bitmask_to_stamp(1 << 5)))

        self.assertIn("usefulness_score", scored)
        self.assertIn("review_tags", scored)


if __name__ == "__main__":
    unittest.main()
