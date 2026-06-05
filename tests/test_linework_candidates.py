from pathlib import Path
from tempfile import TemporaryDirectory
import json
import subprocess
import unittest

from glyph_lab.atlas import generate_pack
from glyph_lab.linework_candidates import generate_linework_candidates, write_linework_review


class LineworkCandidateTests(unittest.TestCase):
    def test_linework_candidate_metadata_includes_geometry_fields(self):
        candidate = generate_linework_candidates()[0]

        self.assertTrue(candidate["generated"])
        self.assertEqual(candidate["source"], "geometry")
        self.assertEqual(candidate["primitive_family"], "linework")
        self.assertIn("angle_degrees", candidate)
        self.assertIn("connector_sides", candidate)
        self.assertIn("linework_package", candidate)
        self.assertIn("stroke_topology", candidate)
        self.assertIn("stroke_ports", candidate)
        self.assertIn("weight_profile", candidate)
        self.assertIn("cap_style", candidate)
        self.assertIn("join_style", candidate)
        self.assertIn("break_rhythm", candidate)
        self.assertIn("roughness", candidate)
        self.assertIn("continuity", candidate)
        self.assertIn("ascii_fallback", candidate)

    def test_linework_review_produces_accepted_and_rejected_candidates(self):
        with TemporaryDirectory() as tmp:
            pack = Path(tmp) / "pack"
            generate_pack(pack)

            result = write_linework_review(pack)

            self.assertGreaterEqual(len(result["accepted_candidates"]), 1)
            self.assertGreaterEqual(len(result["rejected_candidates"]), 1)

    def test_ascii_bridge_exports_unique_palettes_and_mapping(self):
        with TemporaryDirectory() as tmp:
            pack = Path(tmp) / "pack"
            generate_pack(pack)

            result = write_linework_review(pack)
            bridge = result["ascii_bridge"]

            self.assertEqual(len(bridge["linework_palette"]), len(set(bridge["linework_palette"])))
            self.assertGreaterEqual(len(bridge["shade_palette"]), 2)
            self.assertIn("mapping", bridge)
            self.assertEqual(bridge["mapping"]["│"]["token"], "|")
            self.assertEqual(bridge["mapping"]["─"]["token"], "-")

    def test_cli_generate_linework_writes_review_artifacts(self):
        with TemporaryDirectory() as tmp:
            pack = Path(tmp) / "pack"
            generate_pack(pack)

            subprocess.run(
                [
                    ".venv/bin/python",
                    "-m",
                    "glyph_lab.cli",
                    "generate-linework",
                    "--pack",
                    str(pack),
                ],
                check=True,
                cwd="/Users/kogaryu/font",
            )

            self.assertTrue((pack / "linework_candidates.json").exists())
            self.assertTrue((pack / "linework_candidate_scores.json").exists())
            self.assertTrue((pack / "linework_accepted_candidates.json").exists())
            self.assertTrue((pack / "linework_rejected_candidates.json").exists())
            self.assertTrue((pack / "linework_review_contact_sheet.png").exists())
            self.assertTrue((pack / "ascii_linework_palette.txt").exists())
            self.assertTrue((pack / "ascii_shade_palette.txt").exists())
            mapping = json.loads((pack / "ascii_glyph_mapping.json").read_text(encoding="utf-8"))
            self.assertIn("linework_palette", mapping)


if __name__ == "__main__":
    unittest.main()
