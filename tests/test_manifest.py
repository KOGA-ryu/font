from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest

from glyph_lab.atlas import generate_pack
from glyph_lab.compiler import compile_grid


class ManifestTests(unittest.TestCase):
    def test_manifest_records_outputs_and_layers(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            pack = root / "pack"
            generate_pack(pack)
            grid = root / "grid.txt"
            grid.write_text("#|\nSx\n", encoding="utf-8")

            compile_grid(pack / "atlas.png", pack / "glyphs.json", grid, root / "out")
            manifest = json.loads((root / "out" / "manifest.json").read_text(encoding="utf-8"))

            self.assertEqual(manifest["grid_width"], 2)
            self.assertEqual(manifest["grid_height"], 2)
            self.assertEqual(manifest["output_size"], {"width": 8, "height": 8})
            self.assertEqual(manifest["glyph_counts"]["#"], 1)
            self.assertIn("edge", manifest["used_layers"])
            self.assertTrue((root / "out" / "layers" / "base_fill.png").exists())
            self.assertTrue((root / "out" / "layers" / "edge.png").exists())
            self.assertTrue((root / "out" / "layers" / "shadow.png").exists())
            self.assertTrue((root / "out" / "layers" / "detail.png").exists())


if __name__ == "__main__":
    unittest.main()
