from pathlib import Path
from tempfile import TemporaryDirectory
import json
import subprocess
import unittest

from PIL import Image

from glyph_lab.atlas import generate_pack
from glyph_lab.layer_recipe import render_layer_recipe


class LayerRecipeTests(unittest.TestCase):
    def test_render_layer_recipe_writes_layers_composite_and_manifest(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            pack = root / "pack"
            generate_pack(pack)
            ascii_path = root / "grid.txt"
            source = root / "source.png"
            recipe = root / "recipe.json"
            out = root / "out"
            ascii_path.write_text("#\n", encoding="utf-8")
            write_local_color_source(source)
            recipe.write_text(json.dumps(recipe_payload(pack, ascii_path, source), indent=2), encoding="utf-8")

            manifest = render_layer_recipe(recipe, out)

            self.assertTrue((out / "layers/black_t40.png").exists())
            self.assertTrue((out / "layers/blue_recolor.png").exists())
            self.assertTrue((out / "composites/final.png").exists())
            self.assertTrue((out / "manifest.json").exists())
            self.assertEqual(manifest["composites"][0]["name"], "final")
            with Image.open(out / "composites/final.png") as image:
                self.assertEqual(set(pixels(image)), {(30, 70, 150, 255)})

    def test_cli_render_layer_recipe_writes_outputs(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            pack = root / "pack"
            generate_pack(pack)
            ascii_path = root / "grid.txt"
            source = root / "source.png"
            recipe = root / "recipe.json"
            out = root / "out"
            ascii_path.write_text("#\n", encoding="utf-8")
            write_local_color_source(source)
            recipe.write_text(json.dumps(recipe_payload(pack, ascii_path, source), indent=2), encoding="utf-8")

            subprocess.run(
                [
                    ".venv/bin/python",
                    "-m",
                    "glyph_lab.cli",
                    "render-layer-recipe",
                    "--recipe",
                    str(recipe),
                    "--out",
                    str(out),
                ],
                cwd="/Users/kogaryu/font",
                check=True,
            )

            self.assertTrue((out / "composites/final.png").exists())
            self.assertTrue((out / "manifest.json").exists())


def recipe_payload(pack: Path, ascii_path: Path, source: Path) -> dict:
    return {
        "defaults": {
            "ascii": str(ascii_path),
            "glyphs": str(pack / "glyphs.json"),
            "atlas": str(pack / "atlas.png"),
            "gate_image": str(source),
            "gate_mode": "alpha",
            "gate_threshold": 1,
            "gate_dilate": 0,
            "gate_fill_token": "#",
            "scale": 1,
        },
        "layers": [
            {
                "name": "black_t40",
                "ink_mode": "solid",
                "ink_color": "#000000",
            },
            {
                "name": "blue_recolor",
                "ink_mode": "sampled-local",
                "ink_sample_radius": 2,
                "ink_ignore_luminance": 20,
            },
        ],
        "composites": [{"name": "final", "base": "black_t40", "overlays": ["blue_recolor"]}],
    }


def write_local_color_source(path: Path) -> None:
    image = Image.new("RGBA", (5, 5), (30, 70, 150, 255))
    image.putpixel((2, 2), (0, 0, 0, 255))
    image.save(path)


def pixels(image: Image.Image) -> list[tuple[int, int, int, int]]:
    rgba = image.convert("RGBA")
    data = rgba.tobytes()
    return [tuple(data[index : index + 4]) for index in range(0, len(data), 4)]


if __name__ == "__main__":
    unittest.main()
