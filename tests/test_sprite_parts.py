from pathlib import Path
from tempfile import TemporaryDirectory
import json
import subprocess
import unittest

from PIL import Image

from glyph_lab.sprite_parts import classify_sprite_parts


class SpritePartTests(unittest.TestCase):
    def test_classifies_humanoid_color_parts(self):
        with TemporaryDirectory() as tmp:
            source = Path(tmp) / "sprite.png"
            out = Path(tmp) / "parts"
            _write_humanoid_sprite(source)

            manifest = classify_sprite_parts(
                source,
                out,
                grid_width=16,
                grid_height=16,
                foreground_mode="none",
                min_cell_coverage=0.05,
                scale=1,
            )

            counts = {layer["part"]: layer["cells"] for layer in manifest["layers"]}
            self.assertGreater(counts["outline"], 0)
            self.assertGreater(counts["hair"], 0)
            self.assertGreater(counts["skin"], 0)
            self.assertGreater(counts["clothing"], 0)
            self.assertGreater(counts["leather"], 0)
            self.assertGreater(counts["metal"], 0)
            self.assertGreater(counts["gold"], 0)

    def test_brown_splits_into_hair_above_and_leather_below(self):
        with TemporaryDirectory() as tmp:
            source = Path(tmp) / "sprite.png"
            out = Path(tmp) / "parts"
            _write_humanoid_sprite(source)

            manifest = classify_sprite_parts(
                source,
                out,
                grid_width=16,
                grid_height=16,
                foreground_mode="none",
                min_cell_coverage=0.05,
                scale=1,
            )

            layers = {layer["part"]: layer for layer in manifest["layers"]}
            hair_bbox = layers["hair"]["components"][0]["bbox"]
            leather_bbox = layers["leather"]["components"][0]["bbox"]
            self.assertLess(hair_bbox[1], leather_bbox[1])
            self.assertTrue((out / "masks/hair_mask.png").exists())
            self.assertTrue((out / "colorized/leather_color.png").exists())

    def test_cli_classify_sprite_parts_writes_report_and_contact_sheet(self):
        with TemporaryDirectory() as tmp:
            source = Path(tmp) / "sprite.png"
            out = Path(tmp) / "parts"
            _write_humanoid_sprite(source)

            subprocess.run(
                [
                    ".venv/bin/python",
                    "-m",
                    "glyph_lab.cli",
                    "classify-sprite-parts",
                    "--image",
                    str(source),
                    "--out",
                    str(out),
                    "--grid-size",
                    "16",
                    "--foreground-mode",
                    "none",
                    "--min-cell-coverage",
                    "0.05",
                    "--scale",
                    "1",
                ],
                check=True,
                cwd="/Users/kogaryu/font",
            )

            manifest = json.loads((out / "sprite_part_layers.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["parts"][0], "outline")
            self.assertTrue((out / "sprite_part_contact_sheet.png").exists())
            self.assertTrue((out / "composites/stacked_sprite_parts.png").exists())


def _write_humanoid_sprite(path: Path) -> None:
    image = Image.new("RGBA", (16, 16), (255, 255, 255, 255))
    # Black outline.
    for x in range(4, 12):
        image.putpixel((x, 1), (5, 5, 5, 255))
        image.putpixel((x, 14), (5, 5, 5, 255))
    for y in range(1, 15):
        image.putpixel((3, y), (5, 5, 5, 255))
        image.putpixel((12, y), (5, 5, 5, 255))
    # Hair, face, shirt, boots/gloves, sword, belt.
    _fill_rect(image, 5, 2, 10, 4, (72, 42, 18))
    _fill_rect(image, 6, 5, 9, 7, (231, 169, 94))
    _fill_rect(image, 5, 8, 10, 10, (32, 75, 155))
    _fill_rect(image, 5, 11, 10, 13, (69, 38, 18))
    _fill_rect(image, 2, 9, 2, 12, (92, 100, 105))
    _fill_rect(image, 7, 10, 8, 10, (220, 174, 40))
    image.save(path)


def _fill_rect(image: Image.Image, x0: int, y0: int, x1: int, y1: int, rgb: tuple[int, int, int]) -> None:
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            image.putpixel((x, y), (*rgb, 255))


if __name__ == "__main__":
    unittest.main()
