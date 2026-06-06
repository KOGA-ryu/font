from pathlib import Path
from tempfile import TemporaryDirectory
import json
import subprocess
import unittest

from PIL import Image

from glyph_lab.mannequin_proof import render_mannequin_proof


class MannequinProofTests(unittest.TestCase):
    def test_render_mannequin_proof_writes_visual_outputs_and_manifest(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            recipe = _write_mannequin_recipe(root)

            manifest = render_mannequin_proof(recipe, root / "proof", scale=1)

            self.assertEqual(manifest["schema"], "glyph_lab.mannequin_proof.v0")
            self.assertEqual(manifest["part_count"], 3)
            self.assertEqual(manifest["draw_order"], ["pelvis", "torso", "head"])
            self.assertEqual(manifest["skeleton"]["joint_count"], 3)
            self.assertEqual(manifest["skeleton"]["edge_count"], 2)
            self.assertTrue((root / "proof" / "mannequin_silhouette.png").exists())
            self.assertTrue((root / "proof" / "mannequin_shaded_parts.png").exists())
            self.assertTrue((root / "proof" / "mannequin_parts_overlay.png").exists())
            self.assertTrue((root / "proof" / "mannequin_skeleton_overlay.png").exists())
            self.assertTrue((root / "proof" / "mannequin_contact_sheet.png").exists())
            self.assertTrue((root / "proof" / "proof_manifest.json").exists())
            self.assertIn("torso", manifest["shading_summary"])
            self.assertGreater(manifest["shading_summary"]["torso"]["luminance_range"], 0)

    def test_cli_render_mannequin_proof_writes_manifest(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            recipe = _write_mannequin_recipe(root)
            out = root / "cli_proof"

            subprocess.run(
                [
                    ".venv/bin/python",
                    "-m",
                    "glyph_lab.cli",
                    "render-mannequin-proof",
                    "--mannequin",
                    str(recipe),
                    "--out",
                    str(out),
                    "--scale",
                    "1",
                ],
                check=True,
                cwd="/Users/kogaryu/font",
            )

            payload = json.loads((out / "proof_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["schema"], "glyph_lab.mannequin_proof.v0")
            self.assertEqual(payload["skeleton"]["edge_count"], 2)
            self.assertIn("shaded_parts", payload["outputs"])
            self.assertTrue((out / "mannequin_contact_sheet.png").exists())


def _write_mannequin_recipe(root: Path) -> Path:
    masks = root / "masks"
    cutouts = root / "cutouts"
    masks.mkdir()
    cutouts.mkdir()
    _write_mask(masks / "pelvis_mask.png", (32, 48), (11, 26, 21, 34))
    _write_mask(masks / "torso_mask.png", (32, 48), (10, 14, 22, 25))
    _write_mask(masks / "head_mask.png", (32, 48), (12, 4, 20, 13))
    _write_cutout(cutouts / "pelvis_cutout.png", (32, 48), (11, 26, 21, 34), (180, 165, 140))
    _write_cutout(cutouts / "torso_cutout.png", (32, 48), (10, 14, 22, 25), (210, 194, 160))
    _write_cutout(cutouts / "head_cutout.png", (32, 48), (12, 4, 20, 13), (225, 211, 180))
    recipe = {
        "schema": "glyph_lab.mannequin.v0",
        "pose": "unit_pose",
        "grid": {"width": 32, "height": 48},
        "skeleton": {
            "joints": {
                "neck": [16, 13],
                "chest": [16, 18],
                "pelvis": [16, 29],
            },
            "edges": [["neck", "chest"], ["chest", "pelvis"]],
        },
        "parts": [
            {
                "name": "head",
                "parent": "torso",
                "draw_order": 2,
                "mask": str(masks / "head_mask.png"),
                "cutout": str(cutouts / "head_cutout.png"),
                "bbox": [12, 4, 20, 13],
                "pivot": [16, 13],
            },
            {
                "name": "torso",
                "parent": "pelvis",
                "draw_order": 1,
                "mask": str(masks / "torso_mask.png"),
                "cutout": str(cutouts / "torso_cutout.png"),
                "bbox": [10, 14, 22, 25],
                "pivot": [16, 14],
            },
            {
                "name": "pelvis",
                "parent": None,
                "draw_order": 0,
                "mask": str(masks / "pelvis_mask.png"),
                "cutout": str(cutouts / "pelvis_cutout.png"),
                "bbox": [11, 26, 21, 34],
                "pivot": [16, 26],
            },
        ],
    }
    recipe_path = root / "mannequin_recipe.json"
    recipe_path.write_text(json.dumps(recipe), encoding="utf-8")
    return recipe_path


def _write_mask(path: Path, size: tuple[int, int], bbox: tuple[int, int, int, int]) -> None:
    image = Image.new("L", size, 0)
    x0, y0, x1, y1 = bbox
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            image.putpixel((x, y), 255)
    image.save(path)


def _write_cutout(path: Path, size: tuple[int, int], bbox: tuple[int, int, int, int], rgb: tuple[int, int, int]) -> None:
    image = Image.new("RGBA", size, (255, 255, 255, 0))
    x0, y0, x1, y1 = bbox
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            shade = (x - x0 + y - y0) * 3
            image.putpixel((x, y), (min(255, rgb[0] + shade), min(255, rgb[1] + shade), min(255, rgb[2] + shade), 255))
    image.save(path)


if __name__ == "__main__":
    unittest.main()
