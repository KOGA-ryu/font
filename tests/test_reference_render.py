from pathlib import Path
from tempfile import TemporaryDirectory
import json
import subprocess
import unittest

from PIL import Image

from glyph_lab.atlas import generate_pack
from glyph_lab.reference_render import render_reference_style
from glyph_lab.reference_style import build_reference_style_recipe


class ReferenceRenderTests(unittest.TestCase):
    def test_render_reference_style_writes_layers_masks_final_and_manifest(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            pack = root / "pack"
            source = root / "source.png"
            recipe_dir = root / "recipe"
            out = root / "render"
            generate_pack(pack)
            _write_reference_source(source)
            build_reference_style_recipe(
                source,
                recipe_dir,
                grid_width=4,
                grid_height=2,
                families="blue,skin",
                palette_size=1,
                outline_threshold=40,
            )

            manifest = render_reference_style(
                recipe_dir / "reference_style_recipe.json",
                out,
                pack / "glyphs.json",
                pack / "atlas.png",
                scale=1,
            )

            self.assertTrue((out / "final.png").exists())
            self.assertTrue((out / "render_manifest.json").exists())
            self.assertTrue((out / "layers/outline.png").exists())
            self.assertTrue((out / "masks/outline_mask.png").exists())
            self.assertIn("outline", manifest["composite_order"])
            self.assertEqual(manifest["layers"][0]["palette"], ["#000000"])

    def test_render_reference_style_composites_outline_last(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            pack = root / "pack"
            source = root / "source.png"
            recipe_dir = root / "recipe"
            out = root / "render"
            generate_pack(pack)
            _write_reference_source(source)
            recipe = build_reference_style_recipe(
                source,
                recipe_dir,
                grid_width=4,
                grid_height=2,
                families="blue,skin",
                palette_size=1,
                outline_threshold=40,
            )
            recipe["layers"] = [layer for layer in recipe["layers"] if layer["name"] in {"outline", "blue"}]
            recipe_path = recipe_dir / "reference_style_recipe.json"
            recipe_path.write_text(json.dumps(recipe, indent=2) + "\n", encoding="utf-8")

            manifest = render_reference_style(recipe_path, out, pack / "glyphs.json", pack / "atlas.png", scale=1)

            self.assertEqual(manifest["composite_order"][-1], "outline")
            with Image.open(out / "final.png") as image:
                self.assertEqual(image.convert("RGBA").getpixel((0, 0)), (0, 0, 0, 255))

    def test_cli_render_reference_style_writes_final(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            pack = root / "pack"
            source = root / "source.png"
            recipe_dir = root / "recipe"
            out = root / "render"
            generate_pack(pack)
            _write_reference_source(source)
            build_reference_style_recipe(
                source,
                recipe_dir,
                grid_width=4,
                grid_height=2,
                families="blue,skin",
                palette_size=1,
                outline_threshold=40,
            )

            subprocess.run(
                [
                    ".venv/bin/python",
                    "-m",
                    "glyph_lab.cli",
                    "render-reference-style",
                    "--pack",
                    str(pack),
                    "--recipe",
                    str(recipe_dir / "reference_style_recipe.json"),
                    "--out",
                    str(out),
                    "--scale",
                    "1",
                ],
                check=True,
                cwd="/Users/kogaryu/font",
            )

            self.assertTrue((out / "final.png").exists())
            self.assertTrue((out / "render_manifest.json").exists())


def _write_reference_source(path: Path) -> None:
    image = Image.new("RGBA", (8, 4), (255, 255, 255, 255))
    for y in range(4):
        for x in range(2):
            image.putpixel((x, y), (5, 5, 8, 255))
        for x in range(2, 5):
            image.putpixel((x, y), (30, 70, 150, 255))
        for x in range(5, 8):
            image.putpixel((x, y), (231, 169, 94, 255))
    image.save(path)


if __name__ == "__main__":
    unittest.main()
