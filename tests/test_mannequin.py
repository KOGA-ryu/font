from pathlib import Path
from tempfile import TemporaryDirectory
import json
import subprocess
import unittest

from PIL import Image

from glyph_lab.humanoid_regions import classify_humanoid_regions
from glyph_lab.mannequin import build_mannequin_recipe


class MannequinTests(unittest.TestCase):
    def test_build_mannequin_recipe_from_humanoid_regions(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "region_map.png"
            regions_dir = root / "regions"
            out = root / "mannequin"
            _write_region_map(source)
            classify_humanoid_regions(source, regions_dir, foreground_mode="background", scale=1)

            recipe = build_mannequin_recipe(regions_dir / "humanoid_regions.json", out, pose="idle_front")

            self.assertTrue((out / "mannequin_recipe.json").exists())
            self.assertEqual(recipe["schema"], "glyph_lab.mannequin.v0")
            self.assertEqual(recipe["pose"], "idle_front")
            names = {part["name"] for part in recipe["parts"]}
            self.assertIn("head", names)
            self.assertIn("torso", names)
            self.assertIn("upper_arm_left", names)
            self.assertEqual(recipe["skeleton"]["root"], "pelvis")
            self.assertIn("neck", recipe["skeleton"]["joints"])
            self.assertIn(["shoulder_left", "elbow_left"], recipe["skeleton"]["edges"])
            self.assertIn(["knee_right", "ankle_right"], recipe["skeleton"]["edges"])

    def test_mannequin_parts_preserve_masks_bboxes_pivots_and_parents(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "region_map.png"
            regions_dir = root / "regions"
            _write_region_map(source)
            classify_humanoid_regions(source, regions_dir, foreground_mode="background", scale=1)

            recipe = build_mannequin_recipe(regions_dir / "humanoid_regions.json", root / "mannequin.json")

            torso = next(part for part in recipe["parts"] if part["name"] == "torso")
            head = next(part for part in recipe["parts"] if part["name"] == "head")
            self.assertEqual(torso["parent"], "pelvis")
            self.assertEqual(head["parent"], "neck")
            self.assertTrue(torso["mask"].endswith("torso_mask.png"))
            self.assertEqual(len(torso["bbox"]), 4)
            self.assertEqual(len(torso["pivot"]), 2)

    def test_mannequin_skeleton_uses_anatomical_joint_centers_not_parent_pivots(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "region_map.png"
            regions_dir = root / "regions"
            _write_region_map(source)
            classify_humanoid_regions(source, regions_dir, foreground_mode="background", scale=1)

            recipe = build_mannequin_recipe(regions_dir / "humanoid_regions.json", root / "mannequin.json")
            joints = recipe["skeleton"]["joints"]
            lower_arm_left = next(part for part in recipe["parts"] if part["name"] == "lower_arm_left")
            upper_arm_left = next(part for part in recipe["parts"] if part["name"] == "upper_arm_left")
            upper_leg_right = next(part for part in recipe["parts"] if part["name"] == "upper_leg_right")

            self.assertNotEqual(joints["elbow_left"], lower_arm_left["pivot"])
            self.assertGreater(joints["elbow_left"][0], upper_arm_left["bbox"][0])
            self.assertLess(joints["elbow_left"][0], upper_arm_left["bbox"][2])
            self.assertGreater(joints["hip_right"][1], upper_leg_right["bbox"][1])
            self.assertLess(joints["hip_right"][1], upper_leg_right["bbox"][3])

    def test_cli_build_mannequin_writes_recipe(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "region_map.png"
            regions_dir = root / "regions"
            out = root / "mannequin"
            _write_region_map(source)
            classify_humanoid_regions(source, regions_dir, foreground_mode="background", scale=1)

            subprocess.run(
                [
                    ".venv/bin/python",
                    "-m",
                    "glyph_lab.cli",
                    "build-mannequin",
                    "--regions",
                    str(regions_dir / "humanoid_regions.json"),
                    "--out",
                    str(out),
                    "--pose",
                    "idle_front",
                ],
                check=True,
                cwd="/Users/kogaryu/font",
            )

            payload = json.loads((out / "mannequin_recipe.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["schema"], "glyph_lab.mannequin.v0")


def _write_region_map(path: Path) -> None:
    image = Image.new("RGBA", (40, 80), (255, 255, 255, 255))
    _fill_rect(image, 14, 4, 26, 4, (5, 5, 5))
    _fill_rect(image, 6, 50, 6, 70, (5, 5, 5))
    _fill_rect(image, 34, 50, 34, 70, (5, 5, 5))
    _fill_rect(image, 15, 5, 25, 17, (238, 188, 80))
    _fill_rect(image, 18, 20, 22, 23, (32, 75, 155))
    _fill_rect(image, 14, 24, 26, 38, (75, 105, 170))
    _fill_rect(image, 15, 39, 25, 46, (210, 60, 45))
    _fill_rect(image, 8, 24, 13, 33, (230, 120, 160))
    _fill_rect(image, 7, 34, 12, 40, (218, 131, 73))
    _fill_rect(image, 6, 44, 12, 50, (96, 180, 78))
    _fill_rect(image, 27, 24, 32, 33, (96, 180, 78))
    _fill_rect(image, 28, 34, 33, 40, (169, 194, 84))
    _fill_rect(image, 29, 44, 34, 50, (90, 190, 190))
    _fill_rect(image, 13, 48, 18, 57, (220, 174, 40))
    _fill_rect(image, 12, 58, 17, 66, (169, 194, 84))
    _fill_rect(image, 9, 67, 18, 74, (96, 180, 78))
    _fill_rect(image, 22, 48, 27, 57, (218, 131, 73))
    _fill_rect(image, 23, 58, 28, 66, (210, 60, 45))
    _fill_rect(image, 22, 67, 31, 74, (160, 75, 230))
    image.save(path)


def _fill_rect(image: Image.Image, x0: int, y0: int, x1: int, y1: int, rgb: tuple[int, int, int]) -> None:
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            image.putpixel((x, y), (*rgb, 255))


if __name__ == "__main__":
    unittest.main()
