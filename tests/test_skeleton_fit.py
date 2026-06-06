from pathlib import Path
from tempfile import TemporaryDirectory
import json
import subprocess
import unittest

from PIL import Image

from glyph_lab.skeleton_fit import fit_skeleton


class SkeletonFitTests(unittest.TestCase):
    def test_fit_skeleton_scores_joints_against_expected_masks(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            recipe = _write_skeleton_recipe(root)

            report = fit_skeleton(recipe, root / "fit", scale=1)

            self.assertEqual(report["schema"], "glyph_lab.skeleton_fit.v0")
            self.assertEqual(report["joint_count"], 5)
            self.assertEqual(report["bone_count"], 4)
            self.assertTrue(report["joints"]["elbow_left"]["inside_expected_mask"])
            self.assertEqual(report["joints"]["elbow_left"]["source_parts_used"], ["upper_arm_left", "lower_arm_left"])
            self.assertGreaterEqual(report["joints"]["elbow_left"]["confidence"], 0.9)
            self.assertGreater(report["confidence"], 0.5)

    def test_fit_skeleton_writes_overlay_contact_sheet_and_json(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            recipe = _write_skeleton_recipe(root)

            report = fit_skeleton(recipe, root / "fit", scale=1)

            self.assertTrue((root / "fit" / "skeleton_fit.json").exists())
            self.assertTrue((root / "fit" / "skeleton_fit_overlay.png").exists())
            self.assertTrue((root / "fit" / "skeleton_fit_contact_sheet.png").exists())
            self.assertIn("overlay", report["outputs"])

    def test_cli_fit_skeleton_writes_report(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            recipe = _write_skeleton_recipe(root)
            out = root / "cli_fit"

            subprocess.run(
                [
                    ".venv/bin/python",
                    "-m",
                    "glyph_lab.cli",
                    "fit-skeleton",
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

            payload = json.loads((out / "skeleton_fit.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["schema"], "glyph_lab.skeleton_fit.v0")
            self.assertEqual(payload["bone_count"], 4)


def _write_skeleton_recipe(root: Path) -> Path:
    masks = root / "masks"
    cutouts = root / "cutouts"
    masks.mkdir()
    cutouts.mkdir()
    parts = {
        "torso": [12, 8, 20, 18],
        "upper_arm_left": [7, 10, 11, 20],
        "lower_arm_left": [6, 20, 10, 30],
        "hand_left": [5, 29, 10, 34],
    }
    for name, bbox in parts.items():
        _write_mask(masks / f"{name}_mask.png", (32, 40), bbox)
        _write_cutout(cutouts / f"{name}_cutout.png", (32, 40), bbox)
    recipe = {
        "schema": "glyph_lab.mannequin.v0",
        "grid": {"width": 32, "height": 40},
        "parts": [
            {
                "name": name,
                "draw_order": index,
                "mask": str(masks / f"{name}_mask.png"),
                "cutout": str(cutouts / f"{name}_cutout.png"),
                "bbox": bbox,
                "pivot": [bbox[0], bbox[1]],
            }
            for index, (name, bbox) in enumerate(parts.items())
        ],
        "skeleton": {
            "joints": {
                "chest": [16, 11],
                "shoulder_left": [9, 11],
                "elbow_left": [8, 20],
                "wrist_left": [8, 30],
                "hand_left": [8, 32],
            },
            "edges": [
                ["chest", "shoulder_left"],
                ["shoulder_left", "elbow_left"],
                ["elbow_left", "wrist_left"],
                ["wrist_left", "hand_left"],
            ],
        },
    }
    path = root / "mannequin_recipe.json"
    path.write_text(json.dumps(recipe), encoding="utf-8")
    return path


def _write_mask(path: Path, size: tuple[int, int], bbox: list[int]) -> None:
    image = Image.new("L", size, 0)
    x0, y0, x1, y1 = bbox
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            image.putpixel((x, y), 255)
    image.save(path)


def _write_cutout(path: Path, size: tuple[int, int], bbox: list[int]) -> None:
    image = Image.new("RGBA", size, (255, 255, 255, 0))
    x0, y0, x1, y1 = bbox
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            image.putpixel((x, y), (220, 205, 180, 255))
    image.save(path)


if __name__ == "__main__":
    unittest.main()
