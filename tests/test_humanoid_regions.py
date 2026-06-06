from pathlib import Path
from tempfile import TemporaryDirectory
import json
import subprocess
import unittest

from PIL import Image

from glyph_lab.humanoid_regions import classify_humanoid_regions


class HumanoidRegionTests(unittest.TestCase):
    def test_classifies_region_map_into_body_object_lanes(self):
        with TemporaryDirectory() as tmp:
            source = Path(tmp) / "region_map.png"
            out = Path(tmp) / "regions"
            _write_region_map(source)

            manifest = classify_humanoid_regions(
                source,
                out,
                foreground_mode="background",
                scale=1,
            )

            counts = {layer["lane"]: layer["pixels"] for layer in manifest["layers"]}
            for lane in (
                "outline",
                "head",
                "neck",
                "torso",
                "pelvis",
                "upper_arm_left",
                "lower_arm_left",
                "hand_left",
                "upper_arm_right",
                "lower_arm_right",
                "hand_right",
                "upper_leg_left",
                "lower_leg_left",
                "foot_left",
                "upper_leg_right",
                "lower_leg_right",
                "foot_right",
            ):
                self.assertGreater(counts[lane], 0, lane)

    def test_writes_masks_cutouts_and_manifest(self):
        with TemporaryDirectory() as tmp:
            source = Path(tmp) / "region_map.png"
            out = Path(tmp) / "regions"
            _write_region_map(source)

            manifest = classify_humanoid_regions(
                source,
                out,
                foreground_mode="background",
                scale=1,
            )

            self.assertTrue((out / "humanoid_regions.json").exists())
            self.assertTrue((out / "humanoid_region_contact_sheet.png").exists())
            self.assertTrue((out / "masks/head_mask.png").exists())
            self.assertTrue((out / "cutouts/torso_cutout.png").exists())
            self.assertTrue((out / "cutouts/torso_cropped.png").exists())
            self.assertTrue((out / "groups/arm_left_cutout.png").exists())
            self.assertTrue((out / "groups/arm_left_cropped.png").exists())
            self.assertTrue((out / "groups/body_core_cutout.png").exists())
            self.assertGreater(next(group["pixels"] for group in manifest["groups"] if group["group"] == "arms"), 0)
            self.assertIn("centerline", manifest["rule"])

            with Image.open(out / "cutouts/torso_cropped.png") as cropped:
                self.assertLess(cropped.width, manifest["width"])
                self.assertLess(cropped.height, manifest["height"])
            torso_layer = next(layer for layer in manifest["layers"] if layer["lane"] == "torso")
            self.assertIn("cropped_cutout", torso_layer)

    def test_cli_classify_humanoid_regions_writes_outputs(self):
        with TemporaryDirectory() as tmp:
            source = Path(tmp) / "region_map.png"
            out = Path(tmp) / "regions"
            _write_region_map(source)

            subprocess.run(
                [
                    ".venv/bin/python",
                    "-m",
                    "glyph_lab.cli",
                    "classify-humanoid-regions",
                    "--image",
                    str(source),
                    "--out",
                    str(out),
                    "--foreground-mode",
                    "background",
                    "--scale",
                    "1",
                ],
                check=True,
                cwd="/Users/kogaryu/font",
            )

            manifest = json.loads((out / "humanoid_regions.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["lanes"][0], "outline")
            self.assertTrue((out / "humanoid_region_contact_sheet.png").exists())


def _write_region_map(path: Path) -> None:
    image = Image.new("RGBA", (40, 80), (255, 255, 255, 255))
    # A few outline anchors.
    _fill_rect(image, 14, 4, 26, 4, (5, 5, 5))
    _fill_rect(image, 6, 50, 6, 70, (5, 5, 5))
    _fill_rect(image, 34, 50, 34, 70, (5, 5, 5))
    # Body regions.
    _fill_rect(image, 15, 5, 25, 17, (238, 188, 80))
    _fill_rect(image, 18, 20, 22, 23, (32, 75, 155))
    _fill_rect(image, 14, 24, 26, 38, (75, 105, 170))
    _fill_rect(image, 15, 39, 25, 46, (210, 60, 45))
    # Image-left arm.
    _fill_rect(image, 8, 24, 13, 33, (230, 120, 160))
    _fill_rect(image, 7, 34, 12, 40, (218, 131, 73))
    _fill_rect(image, 6, 44, 12, 50, (96, 180, 78))
    # Image-right arm.
    _fill_rect(image, 27, 24, 32, 33, (96, 180, 78))
    _fill_rect(image, 28, 34, 33, 40, (169, 194, 84))
    _fill_rect(image, 29, 44, 34, 50, (90, 190, 190))
    # Legs and feet.
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
