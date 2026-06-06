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
            self.assertIn("skipped_bridge_candidates", bridge)

    def test_brush_candidates_include_damage_detail_packages(self):
        candidates = generate_brush_candidates()
        families = {candidate["brush_family"] for candidate in candidates}
        scratch = next(candidate for candidate in candidates if candidate["brush_family"] == "scratch")
        chip = next(candidate for candidate in candidates if candidate["brush_family"] == "chip")

        self.assertIn("scratch", families)
        self.assertIn("chip", families)
        self.assertEqual(scratch["family"], "damage")
        self.assertEqual(scratch["brush_engine"], "incised-mark")
        self.assertEqual(chip["family"], "damage")
        self.assertEqual(chip["brush_engine"], "edge-damage")

    def test_brush_candidates_include_tone_hatch_package(self):
        candidates = generate_brush_candidates()
        tone = next(candidate for candidate in candidates if candidate["brush_family"] == "tone_hatch")

        self.assertEqual(tone["family"], "texture")
        self.assertEqual(tone["role"], "detail")
        self.assertEqual(tone["brush_engine"], "tone-hatch")
        self.assertIn("pattern", tone["brush_params"])

    def test_brush_candidates_include_dot_field_package(self):
        candidates = generate_brush_candidates()
        dot = next(candidate for candidate in candidates if candidate["brush_family"] == "dot_field")

        self.assertEqual(dot["family"], "texture")
        self.assertEqual(dot["role"], "detail")
        self.assertEqual(dot["brush_engine"], "dot-field")
        self.assertIn("pattern", dot["brush_params"])

    def test_brush_candidates_include_dot_density_package(self):
        candidates = generate_brush_candidates()
        dot = next(candidate for candidate in candidates if candidate["brush_family"] == "dot_density")

        self.assertEqual(dot["family"], "dot_density")
        self.assertEqual(dot["role"], "detail")
        self.assertEqual(dot["brush_engine"], "dot-density")
        self.assertIn("density", dot["brush_params"])

    def test_brush_candidates_include_charcoal_drag_package(self):
        candidates = generate_brush_candidates()
        drag = next(candidate for candidate in candidates if candidate["brush_family"] == "charcoal_drag")

        self.assertEqual(drag["family"], "charcoal")
        self.assertEqual(drag["role"], "detail")
        self.assertEqual(drag["brush_engine"], "charcoal-drag")
        self.assertIn("pressure", drag["brush_params"])

    def test_brush_candidates_include_edge_wear_package(self):
        candidates = generate_brush_candidates()
        wear = next(candidate for candidate in candidates if candidate["brush_family"] == "edge_wear")

        self.assertEqual(wear["family"], "damage")
        self.assertEqual(wear["role"], "detail")
        self.assertEqual(wear["brush_engine"], "edge-wear")
        self.assertIn("wear", wear["brush_params"])

    def test_brush_candidates_include_value_patch_package(self):
        candidates = generate_brush_candidates()
        value = next(candidate for candidate in candidates if candidate["brush_family"] == "value_patch")

        self.assertEqual(value["family"], "texture")
        self.assertEqual(value["role"], "detail")
        self.assertEqual(value["brush_engine"], "value-patch")
        self.assertIn("pattern", value["brush_params"])

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

    def test_brush_bridge_prioritizes_dot_density_keys(self):
        with TemporaryDirectory() as tmp:
            pack = Path(tmp) / "pack"
            generate_pack(pack)

            result = write_brush_review(pack)
            bridge_mapping = result["ascii_bridge"]["mapping"]
            dot_keys = [key for key, value in bridge_mapping.items() if value.get("brush_family") == "dot_density"]

            self.assertGreaterEqual(len(dot_keys), 3)
            self.assertTrue(any(key in result["ascii_bridge"]["spray_palette"] for key in dot_keys))


if __name__ == "__main__":
    unittest.main()
