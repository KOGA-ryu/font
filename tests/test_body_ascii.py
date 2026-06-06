from pathlib import Path
from tempfile import TemporaryDirectory
import json
import subprocess
import unittest

from PIL import Image

from glyph_lab.body_ascii import render_body_ascii_proof


PACK = Path("/Users/kogaryu/font/packs/stone_architecture_4x4")


class BodyAsciiTests(unittest.TestCase):
    def test_render_body_ascii_proof_writes_ascii_palette_and_glyph_proof(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            recipe = _write_body_recipe(root)

            manifest = render_body_ascii_proof(
                recipe,
                root / "body_ascii",
                glyphs_path=PACK / "glyphs.promoted.json",
                atlas_path=PACK / "atlas.promoted.png",
                mapping_path=PACK / "ascii_brush_mapping.json",
                shade_ramp_path=PACK / "ascii_shade_palette.txt",
                grid_width=16,
                grid_height=24,
                palette_size=4,
                palette_theme="maroon",
                scale=1,
            )

            self.assertEqual(manifest["schema"], "glyph_lab.body_ascii_proof.v0")
            self.assertEqual(manifest["palette_theme"], "maroon")
            self.assertGreater(manifest["occupied_cells"], 0)
            self.assertTrue((root / "body_ascii" / "body_ascii.txt").exists())
            self.assertTrue((root / "body_ascii" / "body_ink_source.png").exists())
            self.assertTrue((root / "body_ascii" / "body_palette.json").exists())
            self.assertTrue((root / "body_ascii" / "body_ascii_glyph_proof.png").exists())
            self.assertTrue((root / "body_ascii" / "body_ascii_solid_proof.png").exists())
            self.assertTrue((root / "body_ascii" / "body_ascii_contact_sheet.png").exists())
            self.assertIn("solid_render_result", manifest)
            self.assertGreater(manifest["solid_render_result"]["gate"]["filled_cells"], 0)
            palette = json.loads((root / "body_ascii" / "body_palette.json").read_text(encoding="utf-8"))
            self.assertEqual(palette["palette_theme"], "maroon")
            self.assertLessEqual(len(palette["palette"]), 4)

    def test_body_ascii_grid_uses_spaces_outside_body(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            recipe = _write_body_recipe(root)

            render_body_ascii_proof(
                recipe,
                root / "body_ascii",
                glyphs_path=PACK / "glyphs.promoted.json",
                atlas_path=PACK / "atlas.promoted.png",
                mapping_path=PACK / "ascii_brush_mapping.json",
                grid_width=16,
                grid_height=24,
                palette_size=4,
                scale=1,
            )

            rows = (root / "body_ascii" / "body_ascii.txt").read_text(encoding="utf-8").splitlines()
            self.assertTrue(rows[0].strip() == "")
            self.assertTrue(any(row.strip() for row in rows))

    def test_cli_render_body_ascii_proof_writes_manifest(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            recipe = _write_body_recipe(root)
            out = root / "cli_body_ascii"

            subprocess.run(
                [
                    ".venv/bin/python",
                    "-m",
                    "glyph_lab.cli",
                    "render-body-ascii-proof",
                    "--pack",
                    str(PACK),
                    "--mannequin",
                    str(recipe),
                    "--out",
                    str(out),
                    "--grid-width",
                    "16",
                    "--grid-height",
                    "24",
                    "--palette-size",
                    "4",
                    "--palette-theme",
                    "maroon",
                    "--scale",
                    "1",
                ],
                check=True,
                cwd="/Users/kogaryu/font",
            )

            payload = json.loads((out / "body_ascii_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["schema"], "glyph_lab.body_ascii_proof.v0")
            self.assertEqual(payload["palette_theme"], "maroon")
            self.assertTrue((out / "body_ascii_glyph_proof.png").exists())
            self.assertTrue((out / "body_ascii_solid_proof.png").exists())


def _write_body_recipe(root: Path) -> Path:
    cutouts = root / "cutouts"
    cutouts.mkdir()
    _write_cutout(cutouts / "torso_cutout.png", (32, 48), (10, 8, 22, 28), (224, 206, 176), shade_axis="x")
    _write_cutout(cutouts / "pelvis_cutout.png", (32, 48), (11, 29, 21, 36), (206, 184, 154), shade_axis="y")
    recipe = {
        "schema": "glyph_lab.mannequin.v0",
        "grid": {"width": 32, "height": 48},
        "parts": [
            {
                "name": "torso",
                "draw_order": 0,
                "cutout": str(cutouts / "torso_cutout.png"),
                "bbox": [10, 8, 22, 28],
            },
            {
                "name": "pelvis",
                "draw_order": 1,
                "cutout": str(cutouts / "pelvis_cutout.png"),
                "bbox": [11, 29, 21, 36],
            },
        ],
    }
    path = root / "mannequin_recipe.json"
    path.write_text(json.dumps(recipe), encoding="utf-8")
    return path


def _write_cutout(
    path: Path,
    size: tuple[int, int],
    bbox: tuple[int, int, int, int],
    rgb: tuple[int, int, int],
    *,
    shade_axis: str,
) -> None:
    image = Image.new("RGBA", size, (255, 255, 255, 0))
    x0, y0, x1, y1 = bbox
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            shade = (x - x0) * 4 if shade_axis == "x" else (y - y0) * 5
            image.putpixel((x, y), (max(0, rgb[0] - shade), max(0, rgb[1] - shade), max(0, rgb[2] - shade), 255))
    image.save(path)


if __name__ == "__main__":
    unittest.main()
