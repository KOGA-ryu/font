from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from glyph_lab.atlas import generate_pack, stamp_for_index
from glyph_lab.candidate_filter import filter_candidates, write_candidate_review
from glyph_lab.measure import measure_stamp
from glyph_lab.review_export import generate_review_contact_sheet
from glyph_lab.transforms import bitmask_to_stamp, stamp_to_bitmask


def record(name, role, family, stamp):
    features = measure_stamp(stamp)
    features["bitmask"] = stamp_to_bitmask(stamp)
    return {
        "id": f"test.{name}",
        "token": name[:1],
        "index": 0,
        "role": role,
        "family": family,
        "layer": "edge" if role == "edge" else "detail",
        "palette_role": "ink",
        "cell_size": 4,
        "features": features,
        "constraints": {},
    }


class CandidateFilterTests(unittest.TestCase):
    def test_isolated_dot_is_rejected_as_edge(self):
        dot = record("dot_edge", "edge", "vertical", bitmask_to_stamp(1 << 5))

        result = filter_candidates([dot])

        self.assertEqual(result["rejected_candidates"][0]["rejection_reason"], "no-edge-contacts-for-edge-like-glyph")

    def test_isolated_dot_is_accepted_as_texture_damage(self):
        dot = record("dot_damage", "detail", "damage", bitmask_to_stamp(1 << 5))

        result = filter_candidates([dot])

        self.assertEqual(len(result["accepted_candidates"]), 1)
        self.assertEqual(result["accepted_candidates"][0]["rejection_reason"], None)

    def test_corner_top_left_is_accepted_as_corner(self):
        corner = record("corner", "edge", "corner", stamp_for_index(18))

        result = filter_candidates([corner])

        self.assertEqual(len(result["accepted_candidates"]), 1)

    def test_duplicate_canonical_id_is_rejected_after_first_representative(self):
        top_left = record("corner_a", "edge", "corner", stamp_for_index(18))
        bottom_right = record("corner_b", "edge", "corner", stamp_for_index(21))

        result = filter_candidates([top_left, bottom_right])

        self.assertEqual(len(result["accepted_candidates"]), 1)
        self.assertEqual(result["rejected_candidates"][0]["rejection_reason"], "duplicate-canonical-id")

    def test_review_json_files_are_written(self):
        with TemporaryDirectory() as tmp:
            pack = Path(tmp) / "pack"
            generate_pack(pack)

            write_candidate_review(pack)

            self.assertTrue((pack / "candidate_scores.json").exists())
            self.assertTrue((pack / "accepted_candidates.json").exists())
            self.assertTrue((pack / "rejected_candidates.json").exists())

    def test_review_contact_sheet_is_generated(self):
        with TemporaryDirectory() as tmp:
            pack = Path(tmp) / "pack"
            generate_pack(pack)
            result = write_candidate_review(pack)

            generate_review_contact_sheet(
                result["accepted_candidates"],
                result["rejected_candidates"],
                pack / "review_contact_sheet.png",
            )

            self.assertTrue((pack / "review_contact_sheet.png").exists())


if __name__ == "__main__":
    unittest.main()
