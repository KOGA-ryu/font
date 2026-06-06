from pathlib import Path
from tempfile import TemporaryDirectory
import json
import subprocess
import unittest

from PIL import Image

from glyph_lab.attachments import build_attachment_recipe
from glyph_lab.sprite_parts import classify_sprite_parts


class AttachmentTests(unittest.TestCase):
    def test_build_attachment_recipe_from_sprite_parts(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "sprite.png"
            parts_dir = root / "parts"
            out = root / "attachments"
            _write_sprite_parts_source(source)
            classify_sprite_parts(source, parts_dir, grid_width=24, grid_height=32, foreground_mode="background", scale=1)

            recipe = build_attachment_recipe(parts_dir / "sprite_part_layers.json", out)

            self.assertTrue((out / "attachment_recipe.json").exists())
            self.assertEqual(recipe["schema"], "glyph_lab.attachments.v0")
            names = {attachment["name"] for attachment in recipe["attachments"]}
            self.assertIn("hair", names)
            self.assertIn("clothing", names)
            self.assertIn("leather", names)
            self.assertNotIn("skin", names)
            hair = next(attachment for attachment in recipe["attachments"] if attachment["name"] == "hair")
            self.assertEqual(hair["attach_to"], "head_socket")
            self.assertTrue(hair["mask"].endswith("hair_mask.png"))

    def test_attachment_recipe_records_anchor_and_pose_warp(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "sprite.png"
            parts_dir = root / "parts"
            _write_sprite_parts_source(source)
            classify_sprite_parts(source, parts_dir, grid_width=24, grid_height=32, foreground_mode="background", scale=1)

            recipe = build_attachment_recipe(parts_dir / "sprite_part_layers.json", root / "attachment_recipe.json")

            clothing = next(attachment for attachment in recipe["attachments"] if attachment["name"] == "clothing")
            self.assertEqual(clothing["parent_part"], "torso")
            self.assertEqual(len(clothing["anchor"]), 2)
            self.assertIn("bend", clothing["allowed_pose_warp"])

    def test_cli_build_attachments_writes_recipe(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "sprite.png"
            parts_dir = root / "parts"
            out = root / "attachments"
            _write_sprite_parts_source(source)
            classify_sprite_parts(source, parts_dir, grid_width=24, grid_height=32, foreground_mode="background", scale=1)

            subprocess.run(
                [
                    ".venv/bin/python",
                    "-m",
                    "glyph_lab.cli",
                    "build-attachments",
                    "--parts",
                    str(parts_dir / "sprite_part_layers.json"),
                    "--out",
                    str(out),
                ],
                check=True,
                cwd="/Users/kogaryu/font",
            )

            payload = json.loads((out / "attachment_recipe.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["schema"], "glyph_lab.attachments.v0")


def _write_sprite_parts_source(path: Path) -> None:
    image = Image.new("RGBA", (48, 64), (255, 255, 255, 255))
    _fill_rect(image, 16, 5, 32, 14, (75, 42, 20))
    _fill_rect(image, 18, 12, 30, 21, (231, 169, 94))
    _fill_rect(image, 15, 22, 33, 38, (32, 75, 155))
    _fill_rect(image, 16, 39, 32, 44, (69, 38, 18))
    _fill_rect(image, 17, 45, 22, 58, (74, 82, 90))
    _fill_rect(image, 26, 45, 31, 58, (74, 82, 90))
    _fill_rect(image, 12, 22, 14, 34, (5, 5, 5))
    image.save(path)


def _fill_rect(image: Image.Image, x0: int, y0: int, x1: int, y1: int, rgb: tuple[int, int, int]) -> None:
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            image.putpixel((x, y), (*rgb, 255))


if __name__ == "__main__":
    unittest.main()
