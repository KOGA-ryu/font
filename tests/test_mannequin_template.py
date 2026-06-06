from pathlib import Path
from tempfile import TemporaryDirectory
import json
import subprocess
import unittest

from glyph_lab.humanoid_regions import classify_humanoid_regions
from glyph_lab.mannequin import build_mannequin_recipe
from glyph_lab.mannequin_proof import render_mannequin_proof
from glyph_lab.mannequin_template import generate_front_mannequin_template, generate_mannequin_template


class MannequinTemplateTests(unittest.TestCase):
    def test_generate_front_mannequin_template_writes_preview_region_map_and_manifest(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)

            manifest = generate_front_mannequin_template(root / "template", width=64, height=96, scale=1)

            self.assertEqual(manifest["schema"], "glyph_lab.mannequin_template.v0")
            self.assertEqual(len(manifest["parts"]), 16)
            self.assertTrue((root / "template" / "front_mannequin_template.png").exists())
            self.assertTrue((root / "template" / "front_mannequin_region_map.png").exists())
            self.assertTrue((root / "template" / "mannequin_template_manifest.json").exists())
            names = {part["name"] for part in manifest["parts"]}
            self.assertIn("head", names)
            self.assertIn("upper_arm_left", names)
            self.assertIn("foot_right", names)

    def test_generate_side_mannequin_template_writes_side_specific_outputs(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)

            manifest = generate_mannequin_template(root / "template", width=64, height=96, scale=1, view="side")

            self.assertEqual(manifest["schema"], "glyph_lab.mannequin_template.v0")
            self.assertEqual(manifest["view"], "side")
            self.assertEqual(manifest["template"], "side_humanoid_mannequin")
            self.assertEqual(len(manifest["parts"]), 16)
            self.assertTrue((root / "template" / "side_mannequin_template.png").exists())
            self.assertTrue((root / "template" / "side_mannequin_region_map.png").exists())

    def test_generate_mannequin_template_rejects_unknown_view(self):
        with TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "unknown mannequin template view"):
                generate_mannequin_template(Path(tmp) / "template", view="three_quarter")

    def test_generated_region_map_builds_full_mannequin_proof(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            template = generate_front_mannequin_template(root / "template", width=128, height=192, scale=1)

            regions = classify_humanoid_regions(
                template["outputs"]["region_map"],
                root / "regions",
                foreground_mode="background",
                scale=1,
            )
            recipe = build_mannequin_recipe(root / "regions" / "humanoid_regions.json", root / "mannequin")
            proof = render_mannequin_proof(root / "mannequin" / "mannequin_recipe.json", root / "proof", scale=1)

            self.assertEqual(regions["width"], 128)
            self.assertEqual(len(recipe["parts"]), 16)
            self.assertEqual(proof["part_count"], 16)
            self.assertFalse(proof["warnings"])
            self.assertTrue((root / "proof" / "mannequin_contact_sheet.png").exists())

    def test_cli_generate_mannequin_template_writes_manifest(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = root / "template"

            subprocess.run(
                [
                    ".venv/bin/python",
                    "-m",
                    "glyph_lab.cli",
                    "generate-mannequin-template",
                    "--out",
                    str(out),
                    "--width",
                    "64",
                    "--height",
                    "96",
                    "--scale",
                    "1",
                    "--view",
                    "side",
                ],
                check=True,
                cwd="/Users/kogaryu/font",
            )

            payload = json.loads((out / "mannequin_template_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["schema"], "glyph_lab.mannequin_template.v0")
            self.assertEqual(payload["view"], "side")
            self.assertTrue((out / "side_mannequin_region_map.png").exists())


if __name__ == "__main__":
    unittest.main()
