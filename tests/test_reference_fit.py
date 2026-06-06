from pathlib import Path
from tempfile import TemporaryDirectory
import json
import subprocess
import unittest

from PIL import Image

from glyph_lab.reference_fit import fit_reference_to_mannequin


class ReferenceFitTests(unittest.TestCase):
    def test_fit_reference_to_mannequin_writes_outputs_and_manifest(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            reference = root / "reference.png"
            mannequin = _write_mannequin(root)
            _write_reference(reference)

            manifest = fit_reference_to_mannequin(reference, mannequin, root / "fit", foreground_mode="background")

            self.assertEqual(manifest["schema"], "glyph_lab.reference_fit.v0")
            self.assertEqual(manifest["fit"]["anchor"], "bottom_center")
            self.assertTrue((root / "fit" / "reference_cutout.png").exists())
            self.assertTrue((root / "fit" / "fitted_reference.png").exists())
            self.assertTrue((root / "fit" / "fit_overlay.png").exists())
            self.assertTrue((root / "fit" / "reference_fit_contact_sheet.png").exists())
            self.assertTrue((root / "fit" / "reference_fit_manifest.json").exists())

    def test_fit_reference_to_mannequin_scales_to_target_bbox(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            reference = root / "reference.png"
            mannequin = _write_mannequin(root)
            _write_reference(reference)

            manifest = fit_reference_to_mannequin(reference, mannequin, root / "fit", foreground_mode="background")

            self.assertEqual(manifest["target_bbox"], [8, 8, 23, 35])
            self.assertEqual(manifest["reference_bbox"], [4, 2, 19, 29])
            self.assertEqual(manifest["fit"]["scaled_size"], [16, 28])
            self.assertEqual(manifest["fit"]["paste_position"], [8, 8])

    def test_cli_fit_reference_to_mannequin_writes_manifest(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            reference = root / "reference.png"
            mannequin = _write_mannequin(root)
            _write_reference(reference)
            out = root / "cli_fit"

            subprocess.run(
                [
                    ".venv/bin/python",
                    "-m",
                    "glyph_lab.cli",
                    "fit-reference-to-mannequin",
                    "--reference",
                    str(reference),
                    "--mannequin",
                    str(mannequin),
                    "--out",
                    str(out),
                    "--foreground-mode",
                    "background",
                ],
                check=True,
                cwd="/Users/kogaryu/font",
            )

            payload = json.loads((out / "reference_fit_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["schema"], "glyph_lab.reference_fit.v0")


def _write_mannequin(root: Path) -> Path:
    cutouts = root / "cutouts"
    cutouts.mkdir()
    cutout = Image.new("RGBA", (32, 40), (255, 255, 255, 0))
    for y in range(8, 36):
        for x in range(8, 24):
            cutout.putpixel((x, y), (220, 210, 190, 255))
    cutout.save(cutouts / "body_cutout.png")
    recipe = {
        "schema": "glyph_lab.mannequin.v0",
        "grid": {"width": 32, "height": 40},
        "parts": [
            {
                "name": "body",
                "draw_order": 0,
                "cutout": str(cutouts / "body_cutout.png"),
                "bbox": [8, 8, 23, 35],
            }
        ],
    }
    path = root / "mannequin_recipe.json"
    path.write_text(json.dumps(recipe), encoding="utf-8")
    return path


def _write_reference(path: Path) -> None:
    image = Image.new("RGBA", (24, 32), (255, 255, 255, 255))
    for y in range(2, 30):
        for x in range(4, 20):
            image.putpixel((x, y), (40, 70, 150, 255))
    image.save(path)


if __name__ == "__main__":
    unittest.main()
