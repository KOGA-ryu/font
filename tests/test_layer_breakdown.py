from pathlib import Path
from tempfile import TemporaryDirectory
import json
import subprocess
import unittest

from PIL import Image, ImageDraw

from glyph_lab.atlas import generate_pack
from glyph_lab.layer_breakdown import write_layer_breakdown
from glyph_lab.linework_analyzer import analyze_linework_image


class LayerBreakdownTests(unittest.TestCase):
    def test_layer_breakdown_writes_png_and_json(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            pack = root / "pack"
            image = root / "line.png"
            motion = root / "motion"
            out = root / "breakdown"
            generate_pack(pack)
            _write_test_image(image)
            analyze_linework_image(image, pack, motion, grid_size=8)

            report = write_layer_breakdown(image, pack, out, motion_out_dir=motion, grid_size=8)

            self.assertTrue((out / "layer_breakdown.png").exists())
            self.assertTrue((out / "layer_breakdown.json").exists())
            self.assertEqual(report["counts"]["constraint_warning_count"], 0)
            self.assertGreater(report["counts"]["linework_cell_count"], 0)
            self.assertIn("pressure_cell_count", report["counts"])
            self.assertEqual([panel["name"] for panel in report["panels"]][0], "original")

    def test_layer_breakdown_runs_motion_analyzer_when_missing(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            pack = root / "pack"
            image = root / "line.png"
            out = root / "breakdown"
            generate_pack(pack)
            _write_test_image(image)

            report = write_layer_breakdown(image, pack, out, grid_size=8)

            self.assertTrue((out / "motion" / "motion_selection_report.json").exists())
            self.assertGreater(report["counts"]["linework_cell_count"], 0)

    def test_cli_layer_breakdown_writes_outputs(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            pack = root / "pack"
            image = root / "line.png"
            out = root / "breakdown_cli"
            generate_pack(pack)
            _write_test_image(image)

            subprocess.run(
                [
                    ".venv/bin/python",
                    "-m",
                    "glyph_lab.cli",
                    "layer-breakdown",
                    "--pack",
                    str(pack),
                    "--image",
                    str(image),
                    "--out",
                    str(out),
                    "--grid-size",
                    "8",
                ],
                check=True,
                cwd="/Users/kogaryu/font",
            )

            self.assertTrue((out / "layer_breakdown.png").exists())
            payload = json.loads((out / "layer_breakdown.json").read_text(encoding="utf-8"))
            self.assertIn("motion_profile_counts", payload)


def _write_test_image(path: Path) -> None:
    image = Image.new("RGB", (64, 64), "white")
    draw = ImageDraw.Draw(image)
    draw.line((8, 32, 56, 32), fill="black", width=4)
    draw.line((32, 16, 32, 48), fill="black", width=2)
    image.save(path)


if __name__ == "__main__":
    unittest.main()
