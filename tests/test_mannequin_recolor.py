from pathlib import Path
from tempfile import TemporaryDirectory
import json
import subprocess
import unittest

from PIL import Image

from glyph_lab.mannequin_recolor import recolor_mannequin_from_reference


class MannequinRecolorTests(unittest.TestCase):
    def test_recolor_mannequin_writes_copy_recolor_and_manifest(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            mannequin = _write_mannequin(root)
            style = _write_style_recipe(root)

            manifest = recolor_mannequin_from_reference(mannequin, style, root / "recolored")

            self.assertEqual(manifest["schema"], "glyph_lab.mannequin_recolor.v0")
            self.assertTrue((root / "recolored" / "mannequin_source_copy.png").exists())
            self.assertTrue((root / "recolored" / "mannequin_reference_recolored.png").exists())
            self.assertTrue((root / "recolored" / "reference_palette_swatches.png").exists())
            self.assertTrue((root / "recolored" / "mannequin_recolor_contact_sheet.png").exists())
            self.assertTrue((root / "recolored" / "mannequin_recolor_manifest.json").exists())

    def test_recolor_preserves_part_material_mapping(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            mannequin = _write_mannequin(root)
            style = _write_style_recipe(root)

            manifest = recolor_mannequin_from_reference(mannequin, style, root / "recolored")

            materials = {part["part"]: part["material"] for part in manifest["parts"]}
            self.assertEqual(materials["head"], "skin")
            self.assertEqual(materials["torso"], "blue")
            self.assertEqual(materials["foot_left"], "brown")

    def test_recolor_uses_reference_palette_and_keeps_outline_dark(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            mannequin = _write_mannequin(root)
            style = _write_style_recipe(root)

            recolor_mannequin_from_reference(mannequin, style, root / "recolored", outline_threshold=40)
            image = Image.open(root / "recolored" / "mannequin_reference_recolored.png").convert("RGBA")

            self.assertEqual(image.getpixel((1, 2))[:3], (0, 0, 0))
            self.assertIn(image.getpixel((5, 2))[:3], {(32, 48, 80), (48, 80, 130)})
            self.assertIn(image.getpixel((2, 2))[:3], {(220, 160, 100), (238, 190, 130)})

    def test_cli_recolor_mannequin_writes_manifest(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            mannequin = _write_mannequin(root)
            style = _write_style_recipe(root)
            out = root / "cli_recolored"

            subprocess.run(
                [
                    ".venv/bin/python",
                    "-m",
                    "glyph_lab.cli",
                    "recolor-mannequin-from-reference",
                    "--mannequin",
                    str(mannequin),
                    "--style-recipe",
                    str(style),
                    "--out",
                    str(out),
                ],
                check=True,
                cwd="/Users/kogaryu/font",
            )

            payload = json.loads((out / "mannequin_recolor_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["schema"], "glyph_lab.mannequin_recolor.v0")


def _write_mannequin(root: Path) -> Path:
    cutouts = root / "cutouts"
    cutouts.mkdir()
    _write_cutout(cutouts / "head_cutout.png", (8, 8), (1, 1, 3, 3), [(25, 22, 18), (180, 160, 120), (235, 220, 190)])
    _write_cutout(cutouts / "torso_cutout.png", (8, 8), (4, 1, 6, 3), [(25, 22, 18), (130, 125, 120), (230, 220, 210)])
    _write_cutout(cutouts / "foot_left_cutout.png", (8, 8), (1, 5, 3, 6), [(25, 22, 18), (140, 120, 100), (230, 210, 190)])
    recipe = {
        "schema": "glyph_lab.mannequin.v0",
        "grid": {"width": 8, "height": 8},
        "parts": [
            {"name": "head", "draw_order": 0, "cutout": str(cutouts / "head_cutout.png"), "bbox": [1, 1, 3, 3]},
            {"name": "torso", "draw_order": 1, "cutout": str(cutouts / "torso_cutout.png"), "bbox": [4, 1, 6, 3]},
            {
                "name": "foot_left",
                "draw_order": 2,
                "cutout": str(cutouts / "foot_left_cutout.png"),
                "bbox": [1, 5, 3, 6],
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
    colors: list[tuple[int, int, int]],
) -> None:
    image = Image.new("RGBA", size, (255, 255, 255, 0))
    x0, y0, x1, y1 = bbox
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            image.putpixel((x, y), (*colors[(x - x0) % len(colors)], 255))
    image.save(path)


def _write_style_recipe(root: Path) -> Path:
    style = {
        "schema": "glyph_lab.reference_style_recipe.v0",
        "layers": [
            {"name": "outline", "palette": ["#000000"]},
            {"name": "dark", "palette": ["#060504", "#171b23", "#2b2622"]},
            {"name": "brown", "palette": ["#3c2716", "#4f321b", "#5d3d22"]},
            {"name": "blue", "palette": ["#203050", "#305082"]},
            {"name": "skin", "palette": ["#dca064", "#eebe82"]},
            {"name": "gray", "palette": ["#3a3e42", "#a7a7a7"]},
        ],
    }
    path = root / "reference_style_recipe.json"
    path.write_text(json.dumps(style), encoding="utf-8")
    return path


if __name__ == "__main__":
    unittest.main()
