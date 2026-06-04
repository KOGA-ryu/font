from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from glyph_lab.atlas import generate_pack
from glyph_lab.generate_candidates import generate_primitive_candidates, write_primitive_review


class GenerateCandidateTests(unittest.TestCase):
    def test_primitive_candidate_metadata_includes_family_and_params(self):
        candidate = generate_primitive_candidates()[0]

        self.assertTrue(candidate["generated"])
        self.assertEqual(candidate["source"], "primitive")
        self.assertIn("primitive_family", candidate)
        self.assertIn("primitive_params", candidate)

    def test_primitive_generation_produces_accepted_and_rejected_candidates(self):
        with TemporaryDirectory() as tmp:
            pack = Path(tmp) / "pack"
            generate_pack(pack)

            result = write_primitive_review(pack)

            self.assertGreaterEqual(len(result["accepted_candidates"]), 1)
            self.assertGreaterEqual(len(result["rejected_candidates"]), 1)

    def test_primitive_review_artifacts_are_generated(self):
        with TemporaryDirectory() as tmp:
            pack = Path(tmp) / "pack"
            generate_pack(pack)

            write_primitive_review(pack)

            self.assertTrue((pack / "primitive_candidates.json").exists())
            self.assertTrue((pack / "primitive_candidate_scores.json").exists())
            self.assertTrue((pack / "primitive_accepted_candidates.json").exists())
            self.assertTrue((pack / "primitive_rejected_candidates.json").exists())
            self.assertTrue((pack / "primitive_review_contact_sheet.png").exists())


if __name__ == "__main__":
    unittest.main()
