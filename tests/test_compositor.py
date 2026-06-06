from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest

from PIL import Image

from glyph_lab.atlas import PALETTE, generate_pack
from glyph_lab.compiler import compile_grid
from glyph_lab.compositor import compile_layered_grid
from glyph_lab.layers import output_layer_order
from glyph_lab.validate import GridValidationError


class CompositorTests(unittest.TestCase):
    def test_layered_input_rejects_mismatched_grid_sizes(self):
        with prepared_pack() as pack:
            path = write_layered(pack, 2, 2, [{"name": "base_fill", "grid": ["##", "#"]}])

            with self.assertRaisesRegex(GridValidationError, "row 2 has width 1, expected 2"):
                compile_layered_grid(pack / "atlas.png", pack / "glyphs.json", path, pack / "out")

    def test_unknown_token_includes_layer_row_column(self):
        with prepared_pack() as pack:
            path = write_layered(pack, 2, 1, [{"name": "edge", "grid": [" ?"]}])

            with self.assertRaisesRegex(GridValidationError, "layer 'edge'.*row 1, column 2"):
                compile_layered_grid(pack / "atlas.png", pack / "glyphs.json", path, pack / "out")

    def test_layer_png_is_generated_for_each_standard_output_layer(self):
        with prepared_pack() as pack:
            path = write_layered(pack, 1, 1, [{"name": "base_fill", "grid": ["#"]}])

            compile_layered_grid(pack / "atlas.png", pack / "glyphs.json", path, pack / "out")

            for layer in output_layer_order():
                self.assertTrue((pack / "out" / "layers" / f"{layer}.png").exists())

    def test_composited_proof_respects_layer_order(self):
        with prepared_pack() as pack:
            path = write_layered(
                pack,
                1,
                1,
                [
                    {"name": "base_fill", "grid": ["#"]},
                    {"name": "edge", "grid": ["|"]},
                ],
            )

            compile_layered_grid(pack / "atlas.png", pack / "glyphs.json", path, pack / "out")

            with Image.open(pack / "out" / "proof_128.png") as image:
                self.assertEqual(image.convert("RGBA").getpixel((1, 0)), PALETTE["ink"])

    def test_edge_layer_draws_over_base_fill(self):
        with prepared_pack() as pack:
            path = write_layered(
                pack,
                1,
                1,
                [
                    {"name": "base_fill", "grid": ["#"]},
                    {"name": "edge", "grid": ["-"]},
                ],
            )

            compile_layered_grid(pack / "atlas.png", pack / "glyphs.json", path, pack / "out")

            with Image.open(pack / "out" / "proof_128.png") as image:
                self.assertEqual(image.convert("RGBA").getpixel((0, 1)), PALETTE["ink"])
                self.assertEqual(image.convert("RGBA").getpixel((0, 0)), PALETTE["stone_mid"])

    def test_space_on_upper_layer_does_not_erase_lower_layer(self):
        with prepared_pack() as pack:
            path = write_layered(
                pack,
                1,
                1,
                [
                    {"name": "base_fill", "grid": ["#"]},
                    {"name": "edge", "grid": [" "]},
                ],
            )

            compile_layered_grid(pack / "atlas.png", pack / "glyphs.json", path, pack / "out")

            with Image.open(pack / "out" / "proof_128.png") as image:
                self.assertEqual(image.convert("RGBA").getpixel((0, 0)), PALETTE["stone_mid"])

    def test_manifest_records_per_layer_glyph_counts(self):
        with prepared_pack() as pack:
            path = write_layered(
                pack,
                2,
                1,
                [
                    {"name": "base_fill", "grid": ["##"]},
                    {"name": "detail", "grid": ["x "]},
                ],
            )

            manifest = compile_layered_grid(pack / "atlas.png", pack / "glyphs.json", path, pack / "out")

            self.assertEqual(manifest["input_mode"], "layered")
            self.assertEqual(manifest["per_layer_glyph_counts"]["base_fill"]["#"], 2)
            self.assertEqual(manifest["per_layer_glyph_counts"]["detail"]["x"], 1)
            self.assertEqual(manifest["glyph_counts"]["#"], 2)

    def test_constraint_warning_is_recorded_for_disallowed_layer(self):
        with prepared_pack() as pack:
            path = write_layered(pack, 1, 1, [{"name": "edge", "grid": ["#"]}])

            manifest = compile_layered_grid(pack / "atlas.png", pack / "glyphs.json", path, pack / "out")

            self.assertEqual(len(manifest["constraint_warnings"]), 1)
            self.assertEqual(manifest["constraint_warnings"][0]["layer"], "edge")
            self.assertEqual(manifest["constraint_warnings"][0]["token"], "#")

    def test_linework_layer_accepts_edge_glyphs_without_warning(self):
        with prepared_pack() as pack:
            path = write_layered(pack, 1, 1, [{"name": "linework", "grid": ["-"]}])

            manifest = compile_layered_grid(pack / "atlas.png", pack / "glyphs.json", path, pack / "out")

            self.assertEqual(manifest["constraint_warnings"], [])
            self.assertTrue((pack / "out" / "layers" / "linework.png").exists())

    def test_linework_pressure_layer_accepts_edge_glyphs_without_warning(self):
        with prepared_pack() as pack:
            path = write_layered(pack, 1, 1, [{"name": "linework_pressure", "grid": ["-"]}])

            manifest = compile_layered_grid(pack / "atlas.png", pack / "glyphs.json", path, pack / "out")

            self.assertEqual(manifest["constraint_warnings"], [])
            self.assertTrue((pack / "out" / "layers" / "linework_pressure.png").exists())

    def test_old_flat_compile_still_works(self):
        with prepared_pack() as pack:
            grid = pack / "flat.txt"
            grid.write_text("##\n##\n", encoding="utf-8")

            manifest = compile_grid(pack / "atlas.png", pack / "glyphs.json", grid, pack / "flat_out")

            self.assertEqual(manifest["output_size"], {"width": 8, "height": 8})
            self.assertTrue((pack / "flat_out" / "proof_128.png").exists())


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


def write_layered(pack: Path, width: int, height: int, layers: list[dict]) -> Path:
    path = pack / "layered.json"
    path.write_text(
        json.dumps({"grid_width": width, "grid_height": height, "layers": layers}, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


if __name__ == "__main__":
    unittest.main()
