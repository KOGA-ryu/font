from pathlib import Path
from tempfile import TemporaryDirectory
import json
import subprocess
import unittest

from PIL import Image

from glyph_lab.atlas import generate_pack
from glyph_lab.color_family_layers import classify_color_family, parse_families, render_color_family_layers


class ColorFamilyLayerTests(unittest.TestCase):
    def test_parse_families_accepts_auto_or_explicit_list(self):
        self.assertIn("blue", parse_families("auto"))
        self.assertEqual(parse_families("dark,blue,skin"), ["dark", "blue", "skin"])
        with self.assertRaisesRegex(ValueError, "unknown color families"):
            parse_families("cloak")

    def test_classify_color_family_uses_generic_color_properties(self):
        background = (255, 255, 255)
        self.assertEqual(classify_color_family((5, 5, 5), background_rgb=background), "dark")
        self.assertEqual(classify_color_family((69, 38, 18), background_rgb=background), "brown")
        self.assertEqual(classify_color_family((210, 60, 45), background_rgb=background), "red")
        self.assertEqual(classify_color_family((218, 131, 73), background_rgb=background), "orange")
        self.assertEqual(classify_color_family((169, 194, 84), background_rgb=background), "lime")
        self.assertEqual(classify_color_family((96, 180, 78), background_rgb=background), "green")
        self.assertEqual(classify_color_family((90, 190, 190), background_rgb=background), "cyan")
        self.assertEqual(classify_color_family((32, 75, 155), background_rgb=background), "blue")
        self.assertEqual(classify_color_family((160, 75, 230), background_rgb=background), "violet")
        self.assertEqual(classify_color_family((230, 120, 160), background_rgb=background), "pink")
        self.assertEqual(classify_color_family((231, 169, 94), background_rgb=background), "skin")
        self.assertEqual(classify_color_family((92, 100, 105), background_rgb=background), "gray")
        self.assertEqual(classify_color_family((220, 174, 40), background_rgb=background), "gold")
        self.assertEqual(classify_color_family((225, 225, 210), background_rgb=background), "highlight")
        self.assertIsNone(classify_color_family((255, 255, 255), background_rgb=background))
        self.assertIsNone(classify_color_family((2, 2, 2), background_rgb=(0, 0, 0)))

    def test_render_color_family_layers_writes_generic_layers(self):
        with TemporaryDirectory() as tmp:
            pack = Path(tmp) / "pack"
            generate_pack(pack)
            source = Path(tmp) / "colors.png"
            out = Path(tmp) / "families"
            _write_color_strip(source)

            manifest = render_color_family_layers(
                source,
                pack / "glyphs.json",
                pack / "atlas.png",
                out,
                grid_width=14,
                grid_height=3,
                scale=1,
            )

            counts = {layer["family"]: layer["cells"] for layer in manifest["layers"]}
            for family in (
                "dark",
                "brown",
                "red",
                "orange",
                "gold",
                "lime",
                "green",
                "cyan",
                "blue",
                "violet",
                "pink",
                "skin",
                "gray",
                "highlight",
            ):
                self.assertGreaterEqual(counts[family], 1)
                self.assertTrue((out / f"masks/{family}_mask.png").exists())
                self.assertTrue((out / f"black/{family}_black.png").exists())
                self.assertTrue((out / f"colorized/{family}_color.png").exists())
            self.assertTrue((out / "composites/stacked_color_families.png").exists())
            self.assertTrue((out / "color_family_layers_contact_sheet.png").exists())
            self.assertTrue((out / "masks/foreground_mask.png").exists())
            self.assertEqual(manifest["rule"].count("object labels"), 1)

    def test_alpha_foreground_blocks_transparent_dark_color_cells(self):
        with TemporaryDirectory() as tmp:
            pack = Path(tmp) / "pack"
            generate_pack(pack)
            source = Path(tmp) / "colors.png"
            out = Path(tmp) / "families"
            image = Image.new("RGBA", (8, 4), (0, 0, 0, 0))
            for y in range(4):
                for x in range(4):
                    image.putpixel((x, y), (5, 5, 5, 255))
            image.save(source)

            manifest = render_color_family_layers(
                source,
                pack / "glyphs.json",
                pack / "atlas.png",
                out,
                grid_width=2,
                grid_height=1,
                scale=1,
            )

            counts = {layer["family"]: layer["cells"] for layer in manifest["layers"]}
            self.assertEqual(manifest["foreground"]["mode"], "alpha")
            self.assertEqual(manifest["foreground"]["kept_cells"], 1)
            self.assertEqual(counts["dark"], 1)

    def test_cli_render_color_family_layers_writes_outputs(self):
        with TemporaryDirectory() as tmp:
            pack = Path(tmp) / "pack"
            generate_pack(pack)
            source = Path(tmp) / "colors.png"
            out = Path(tmp) / "families"
            _write_color_strip(source)

            subprocess.run(
                [
                    ".venv/bin/python",
                    "-m",
                    "glyph_lab.cli",
                    "render-color-family-layers",
                    "--pack",
                    str(pack),
                    "--image",
                    str(source),
                    "--out",
                    str(out),
                    "--width",
                    "14",
                    "--height",
                    "3",
                    "--scale",
                    "1",
                ],
                check=True,
                cwd="/Users/kogaryu/font",
            )

            manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["families"][0], "dark")
            self.assertTrue((out / "color_family_layers_contact_sheet.png").exists())


def _write_color_strip(path: Path) -> None:
    image = Image.new("RGBA", (150, 30), (255, 255, 255, 255))
    colors = [
        (5, 5, 5),
        (69, 38, 18),
        (210, 60, 45),
        (218, 131, 73),
        (220, 174, 40),
        (169, 194, 84),
        (96, 180, 78),
        (90, 190, 190),
        (32, 75, 155),
        (160, 75, 230),
        (230, 120, 160),
        (231, 169, 94),
        (92, 100, 105),
        (225, 225, 210),
    ]
    for index, rgb in enumerate(colors, start=1):
        for y in range(10, 20):
            for x in range(index * 10, index * 10 + 10):
                image.putpixel((x, y), (*rgb, 255))
    image.save(path)


if __name__ == "__main__":
    unittest.main()
