from pathlib import Path
from tempfile import TemporaryDirectory
import json
import subprocess
import unittest

from PIL import Image

from glyph_lab.atlas import generate_pack
from glyph_lab.threshold_layers import parse_thresholds, render_threshold_color_layers


class ThresholdLayerTests(unittest.TestCase):
    def test_parse_thresholds_requires_sorted_unique_values(self):
        self.assertEqual(parse_thresholds("16,24,40"), [16, 24, 40])
        with self.assertRaisesRegex(ValueError, "unique and sorted"):
            parse_thresholds("24,16")
        with self.assertRaisesRegex(ValueError, "between 0 and 255"):
            parse_thresholds("16,300")

    def test_delta_layers_keep_threshold_bands_separate(self):
        with TemporaryDirectory() as tmp:
            pack = Path(tmp) / "pack"
            generate_pack(pack)
            source = Path(tmp) / "source.png"
            out = Path(tmp) / "threshold_layers"
            image = Image.new("RGBA", (8, 4), (255, 255, 255, 255))
            for y in range(4):
                for x in range(4):
                    image.putpixel((x, y), (24, 0, 0, 255))
                for x in range(4, 8):
                    image.putpixel((x, y), (0, 0, 180, 255))
            image.save(source)

            manifest = render_threshold_color_layers(
                source,
                pack / "glyphs.json",
                pack / "atlas.png",
                out,
                thresholds=[16, 40],
                grid_width=2,
                grid_height=1,
                foreground_mode="none",
                scale=1,
            )

            self.assertEqual([layer["delta_cells"] for layer in manifest["layers"]], [1, 1])
            self.assertEqual(manifest["layers"][0]["luminance_range"], [0, 15])
            self.assertEqual(manifest["layers"][1]["luminance_range"], [16, 39])
            with Image.open(out / "colorized/t16_delta_color.png") as t16:
                self.assertEqual(t16.getpixel((0, 0)), (24, 0, 0, 255))
                self.assertEqual(t16.getpixel((4, 0))[3], 0)
            with Image.open(out / "colorized/t40_delta_color.png") as t40:
                self.assertEqual(t40.getpixel((0, 0))[3], 0)
                self.assertEqual(t40.getpixel((4, 0)), (0, 0, 180, 255))

    def test_render_threshold_color_layers_writes_artifacts(self):
        with TemporaryDirectory() as tmp:
            pack = Path(tmp) / "pack"
            generate_pack(pack)
            source = Path(tmp) / "source.png"
            out = Path(tmp) / "threshold_layers"
            Image.new("RGBA", (4, 4), (20, 10, 10, 255)).save(source)

            render_threshold_color_layers(
                source,
                pack / "glyphs.json",
                pack / "atlas.png",
                out,
                thresholds=[32],
                grid_width=1,
                grid_height=1,
                foreground_mode="none",
                scale=1,
            )

            self.assertTrue((out / "masks/t32_cumulative_mask.png").exists())
            self.assertTrue((out / "masks/t32_delta_mask.png").exists())
            self.assertTrue((out / "black/t32_delta_black.png").exists())
            self.assertTrue((out / "colorized/t32_delta_color.png").exists())
            self.assertTrue((out / "composites/stacked_delta_color.png").exists())
            self.assertTrue((out / "threshold_color_layers_contact_sheet.png").exists())
            manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["ink_mode"], "threshold-sampled-delta")
            self.assertTrue((out / "masks/foreground_mask.png").exists())

    def test_alpha_foreground_blocks_transparent_dark_background(self):
        with TemporaryDirectory() as tmp:
            pack = Path(tmp) / "pack"
            generate_pack(pack)
            source = Path(tmp) / "source.png"
            out = Path(tmp) / "threshold_layers"
            image = Image.new("RGBA", (8, 4), (0, 0, 0, 0))
            for y in range(4):
                for x in range(4):
                    image.putpixel((x, y), (10, 10, 10, 255))
            image.save(source)

            manifest = render_threshold_color_layers(
                source,
                pack / "glyphs.json",
                pack / "atlas.png",
                out,
                thresholds=[40],
                grid_width=2,
                grid_height=1,
                scale=1,
            )

            self.assertEqual(manifest["foreground"]["mode"], "alpha")
            self.assertEqual(manifest["foreground"]["kept_cells"], 1)
            self.assertEqual(manifest["layers"][0]["delta_cells"], 1)

    def test_cli_render_threshold_color_layers_writes_outputs(self):
        with TemporaryDirectory() as tmp:
            pack = Path(tmp) / "pack"
            generate_pack(pack)
            source = Path(tmp) / "source.png"
            out = Path(tmp) / "threshold_layers"
            Image.new("RGBA", (4, 4), (20, 10, 10, 255)).save(source)

            subprocess.run(
                [
                    ".venv/bin/python",
                    "-m",
                    "glyph_lab.cli",
                    "render-threshold-color-layers",
                    "--pack",
                    str(pack),
                    "--image",
                    str(source),
                    "--out",
                    str(out),
                    "--thresholds",
                    "32",
                    "--width",
                    "1",
                    "--height",
                    "1",
                    "--scale",
                    "1",
                ],
                check=True,
                cwd="/Users/kogaryu/font",
            )

            self.assertTrue((out / "manifest.json").exists())
            self.assertTrue((out / "threshold_color_layers_contact_sheet.png").exists())


if __name__ == "__main__":
    unittest.main()
