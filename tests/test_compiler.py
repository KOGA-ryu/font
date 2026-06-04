from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from PIL import Image

from glyph_lab.atlas import generate_pack
from glyph_lab.compiler import compile_grid
from glyph_lab.validate import GridValidationError


class CompilerTests(unittest.TestCase):
    def test_unknown_token_reports_row_and_column(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            pack = root / "pack"
            generate_pack(pack)
            grid = root / "grid.txt"
            grid.write_text("#?\n##\n", encoding="utf-8")

            with self.assertRaisesRegex(GridValidationError, "row 1, column 2"):
                compile_grid(pack / "atlas.png", pack / "glyphs.json", grid, root / "out")

    def test_2x2_grid_expands_to_8x8(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            pack = root / "pack"
            generate_pack(pack)
            grid = root / "grid.txt"
            grid.write_text("##\n##\n", encoding="utf-8")

            compile_grid(pack / "atlas.png", pack / "glyphs.json", grid, root / "out")

            with Image.open(root / "out" / "proof_128.png") as image:
                self.assertEqual(image.size, (8, 8))

    def test_32x32_grid_expands_to_128x128(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            pack = root / "pack"
            generate_pack(pack)
            grid = root / "grid.txt"
            grid.write_text(("\n".join(["#" * 32 for _ in range(32)])) + "\n", encoding="utf-8")

            compile_grid(pack / "atlas.png", pack / "glyphs.json", grid, root / "out")

            with Image.open(root / "out" / "proof_128.png") as image:
                self.assertEqual(image.size, (128, 128))


if __name__ == "__main__":
    unittest.main()
