from pathlib import Path
from tempfile import TemporaryDirectory
import json
import subprocess
import unittest

from glyph_lab.atlas import generate_pack
from glyph_lab.brush_candidates import generate_brush_candidates, write_brush_review


class BrushCandidateTests(unittest.TestCase):
    def test_brush_candidate_metadata_includes_brush_fields(self):
        candidate = generate_brush_candidates()[0]

        self.assertTrue(candidate["generated"])
        self.assertEqual(candidate["source"], "brush_geometry")
        self.assertEqual(candidate["primitive_family"], "brush")
        self.assertIn("brush_family", candidate)
        self.assertIn("brush_engine", candidate)
        self.assertIn("ascii_fallback", candidate)

    def test_brush_review_produces_accepted_and_rejected_candidates(self):
        with TemporaryDirectory() as tmp:
            pack = Path(tmp) / "pack"
            generate_pack(pack)

            result = write_brush_review(pack)

            self.assertGreaterEqual(len(result["accepted_candidates"]), 1)
            self.assertGreaterEqual(len(result["rejected_candidates"]), 1)

    def test_brush_palettes_are_unique_and_mapped(self):
        with TemporaryDirectory() as tmp:
            pack = Path(tmp) / "pack"
            generate_pack(pack)

            result = write_brush_review(pack)
            bridge = result["ascii_bridge"]

            self.assertEqual(len(bridge["texture_palette"]), len(set(bridge["texture_palette"])))
            self.assertEqual(len(bridge["spray_palette"]), len(set(bridge["spray_palette"])))
            self.assertGreaterEqual(len(bridge["texture_palette"]), len(bridge["spray_palette"]))
            self.assertIn("mapping", bridge)

    def test_cli_generate_brushes_writes_review_artifacts(self):
        with TemporaryDirectory() as tmp:
            pack = Path(tmp) / "pack"
            generate_pack(pack)

            subprocess.run(
                [
                    ".venv/bin/python",
                    "-m",
                    "glyph_lab.cli",
                    "generate-brushes",
                    "--pack",
                    str(pack),
                ],
                check=True,
                cwd="/Users/kogaryu/font",
            )

            self.assertTrue((pack / "brush_candidates.json").exists())
            self.assertTrue((pack / "brush_candidate_scores.json").exists())
            self.assertTrue((pack / "brush_accepted_candidates.json").exists())
            self.assertTrue((pack / "brush_rejected_candidates.json").exists())
            self.assertTrue((pack / "brush_review_contact_sheet.png").exists())
            self.assertTrue((pack / "ascii_texture_palette.txt").exists())
            self.assertTrue((pack / "ascii_spray_palette.txt").exists())
            mapping = json.loads((pack / "ascii_brush_mapping.json").read_text(encoding="utf-8"))
            self.assertIn("texture_palette", mapping)


if __name__ == "__main__":
    unittest.main()
