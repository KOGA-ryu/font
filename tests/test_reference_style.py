from pathlib import Path
from tempfile import TemporaryDirectory
import json
import subprocess
import unittest

from PIL import Image

from glyph_lab.reference_style import build_reference_style_recipe, reduce_palette


class ReferenceStyleTests(unittest.TestCase):
    def test_reference_style_recipe_writes_interpreted_layers(self):
        with TemporaryDirectory() as tmp:
            source = Path(tmp) / "reference.png"
            out = Path(tmp) / "style"
            _write_reference_source(source)

            recipe = build_reference_style_recipe(
                source,
                out,
                grid_width=4,
                grid_height=2,
                families="blue,skin",
                palette_size=1,
                outline_threshold=40,
            )

            self.assertTrue((out / "reference_style_recipe.json").exists())
            self.assertEqual(recipe["style_intent"], "reference_interpreter_not_replica")
            names = {layer["name"] for layer in recipe["layers"]}
            self.assertIn("outline", names)
            self.assertIn("blue", names)
            self.assertIn("skin", names)

    def test_reference_style_recipe_reduces_each_layer_palette(self):
        with TemporaryDirectory() as tmp:
            source = Path(tmp) / "reference.png"
            out = Path(tmp) / "recipe.json"
            _write_reference_source(source)

            recipe = build_reference_style_recipe(
                source,
                out,
                grid_width=4,
                grid_height=2,
                families="blue,skin",
                palette_size=1,
                outline_threshold=40,
            )

            by_name = {layer["name"]: layer for layer in recipe["layers"]}
            self.assertEqual(len(by_name["blue"]["palette"]), 1)
            self.assertEqual(len(by_name["skin"]["palette"]), 1)
            self.assertTrue(by_name["blue"]["palette"][0].startswith("#"))
            self.assertEqual(by_name["outline"]["palette"], ["#000000"])

    def test_reduce_palette_is_deterministic_and_bounded(self):
        colors = [
            (20, 60, 140),
            (22, 65, 150),
            (120, 72, 32),
            (130, 80, 40),
            (220, 180, 120),
        ]

        first = reduce_palette(colors, 2)
        second = reduce_palette(list(reversed(colors)), 2)

        self.assertEqual(first, second)
        self.assertLessEqual(len(first), 2)

    def test_cli_reference_style_recipe_writes_json(self):
        with TemporaryDirectory() as tmp:
            source = Path(tmp) / "reference.png"
            out = Path(tmp) / "style"
            _write_reference_source(source)

            subprocess.run(
                [
                    ".venv/bin/python",
                    "-m",
                    "glyph_lab.cli",
                    "reference-style-recipe",
                    "--image",
                    str(source),
                    "--out",
                    str(out),
                    "--grid-size",
                    "4",
                    "--families",
                    "blue,skin",
                    "--palette-size",
                    "1",
                    "--outline-threshold",
                    "40",
                ],
                check=True,
                cwd="/Users/kogaryu/font",
            )

            payload = json.loads((out / "reference_style_recipe.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["schema"], "glyph_lab.reference_style_recipe.v0")
            self.assertTrue(payload["layers"])


def _write_reference_source(path: Path) -> None:
    image = Image.new("RGBA", (8, 4), (255, 255, 255, 255))
    for y in range(4):
        for x in range(2):
            image.putpixel((x, y), (5, 5, 8, 255))
        for x in range(2, 5):
            color = (30, 70, 150, 255) if (x + y) % 2 == 0 else (42, 86, 174, 255)
            image.putpixel((x, y), color)
        for x in range(5, 8):
            color = (231, 169, 94, 255) if (x + y) % 2 == 0 else (206, 137, 70, 255)
            image.putpixel((x, y), color)
    image.save(path)


if __name__ == "__main__":
    unittest.main()
