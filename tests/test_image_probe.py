from pathlib import Path
from tempfile import TemporaryDirectory
import subprocess
import unittest

from PIL import Image, ImageDraw

from glyph_lab.atlas import generate_pack
from glyph_lab.image_probe import auto_crop_non_background, probe_image
from glyph_lab.image_to_layers import ProbeGlyphLookupError, maps_to_layered_grid, probe_image_to_layers, required_probe_tokens
from glyph_lab.schema import load_glyphs


class ImageProbeTests(unittest.TestCase):
    def test_auto_crop_finds_black_rectangle_on_white_background(self):
        image = Image.new("L", (20, 20), 255)
        draw = ImageDraw.Draw(image)
        draw.rectangle((5, 6, 14, 15), fill=0)

        self.assertEqual(auto_crop_non_background(image), (5, 6, 15, 16))

    def test_probe_of_simple_rectangle_creates_occupied_mass_cells(self):
        with simple_image() as image_path:
            probe = probe_image(image_path, 32, 32)

            self.assertGreater(probe["occupied_cell_count"], 0)

    def test_occupied_bbox_cells_matches_approximate_rectangle_bounds(self):
        with simple_image() as image_path:
            bbox = probe_image(image_path, 32, 32)["occupied_bbox_cells"]

            self.assertLessEqual(bbox[0], 2)
            self.assertLessEqual(bbox[1], 2)
            self.assertGreaterEqual(bbox[2], 29)
            self.assertGreaterEqual(bbox[3], 29)

    def test_edge_map_creates_cells_around_rectangle_boundary(self):
        with simple_image() as image_path:
            probe = probe_image(image_path, 32, 32)

            self.assertGreater(probe["edge_cell_count"], 0)

    def test_generated_layered_json_has_standard_layer_names(self):
        with prepared_pack() as pack, simple_image() as image_path:
            probe = probe_image(image_path, 32, 32)
            tokens = required_probe_tokens(load_glyphs(pack / "glyphs.json"))
            layered = maps_to_layered_grid(probe, tokens)

            self.assertEqual(
                [layer["name"] for layer in layered["layers"]],
                ["mass", "base_fill", "shadow", "highlight", "edge"],
            )

    def test_probe_measurements_json_includes_crop_box_and_occupied_count(self):
        with prepared_pack() as pack, simple_image() as image_path:
            out = pack / "out_probe"

            probe_image_to_layers(image_path, pack, out, grid_size=32)

            text = (out / "probe_measurements.json").read_text(encoding="utf-8")
            self.assertIn("crop_box", text)
            self.assertIn("occupied_cell_count", text)

    def test_missing_required_glyph_role_fails_clearly(self):
        glyphs = [glyph for glyph in load_glyphs("packs/stone_architecture_4x4/glyphs.json") if glyph.role != "highlight"]

        with self.assertRaisesRegex(ProbeGlyphLookupError, "missing required glyph"):
            required_probe_tokens(glyphs)

    def test_cli_probe_image_writes_layered_grid_and_proof(self):
        with prepared_pack() as pack, simple_image() as image_path:
            out = pack / "out_probe"

            subprocess.run(
                [
                    ".venv/bin/python",
                    "-m",
                    "glyph_lab.cli",
                    "probe-image",
                    "--pack",
                    str(pack),
                    "--image",
                    str(image_path),
                    "--out",
                    str(out),
                    "--grid-size",
                    "32",
                ],
                check=True,
                cwd="/Users/kogaryu/font",
            )

            self.assertTrue((out / "generated_layered_grid.json").exists())
            self.assertTrue((out / "proof_128.png").exists())


def prepared_pack():
    temp = TemporaryDirectory()
    pack = Path(temp.name) / "pack"
    generate_pack(pack)

    class Context:
        def __enter__(self):
            return pack

        def __exit__(self, *_args):
            temp.cleanup()

    return Context()


def simple_image():
    temp = TemporaryDirectory()
    path = Path(temp.name) / "rect.png"
    image = Image.new("RGB", (64, 64), (255, 255, 255))
    draw = ImageDraw.Draw(image)
    draw.rectangle((16, 12, 47, 51), fill=(40, 40, 40))
    image.save(path)

    class Context:
        def __enter__(self):
            return path

        def __exit__(self, *_args):
            temp.cleanup()

    return Context()


if __name__ == "__main__":
    unittest.main()
