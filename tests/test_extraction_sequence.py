from pathlib import Path
from tempfile import TemporaryDirectory
import json
import subprocess
import unittest

from PIL import Image

from glyph_lab.atlas import generate_pack
from glyph_lab.extraction_sequence import render_extraction_sequence


class ExtractionSequenceTests(unittest.TestCase):
    def test_render_extraction_sequence_writes_child_passes_and_report(self):
        with TemporaryDirectory() as tmp:
            pack = Path(tmp) / "pack"
            generate_pack(pack)
            source = Path(tmp) / "source.png"
            out = Path(tmp) / "sequence"
            _write_sequence_source(source)

            report = render_extraction_sequence(
                source,
                pack,
                out,
                thresholds=[24, 64],
                grid_width=4,
                grid_height=4,
                foreground_mode="none",
                scale=1,
            )

            self.assertTrue((out / "threshold_layers/manifest.json").exists())
            self.assertTrue((out / "color_families/manifest.json").exists())
            self.assertTrue((out / "sequence_report.json").exists())
            self.assertTrue((out / "sequence_contact_sheet.png").exists())
            self.assertEqual(report["threshold_layers"]["layers"][0]["threshold"], 24)
            self.assertIn("color_families", report)

    def test_sequence_report_records_foreground_and_color_counts(self):
        with TemporaryDirectory() as tmp:
            pack = Path(tmp) / "pack"
            generate_pack(pack)
            source = Path(tmp) / "source.png"
            out = Path(tmp) / "sequence"
            image = Image.new("RGBA", (8, 8), (0, 0, 0, 0))
            for y in range(4):
                for x in range(4):
                    image.putpixel((x, y), (20, 30, 160, 255))
            image.save(source)

            report = render_extraction_sequence(
                source,
                pack,
                out,
                thresholds=[40],
                grid_width=2,
                grid_height=2,
                scale=1,
            )

            color_counts = {layer["family"]: layer["cells"] for layer in report["color_families"]["layers"]}
            self.assertEqual(report["threshold_layers"]["foreground"]["mode"], "alpha")
            self.assertEqual(report["threshold_layers"]["foreground"]["kept_cells"], 1)
            self.assertGreaterEqual(color_counts["blue"], 1)

    def test_cli_render_extraction_sequence_writes_report(self):
        with TemporaryDirectory() as tmp:
            pack = Path(tmp) / "pack"
            generate_pack(pack)
            source = Path(tmp) / "source.png"
            out = Path(tmp) / "sequence"
            _write_sequence_source(source)

            subprocess.run(
                [
                    ".venv/bin/python",
                    "-m",
                    "glyph_lab.cli",
                    "render-extraction-sequence",
                    "--pack",
                    str(pack),
                    "--image",
                    str(source),
                    "--out",
                    str(out),
                    "--thresholds",
                    "24,64",
                    "--width",
                    "4",
                    "--height",
                    "4",
                    "--foreground-mode",
                    "none",
                    "--scale",
                    "1",
                ],
                check=True,
                cwd="/Users/kogaryu/font",
            )

            report = json.loads((out / "sequence_report.json").read_text(encoding="utf-8"))
            self.assertTrue((out / "sequence_contact_sheet.png").exists())
            self.assertEqual(report["grid_width"], 4)
            self.assertTrue((out / "threshold_layers/threshold_color_layers_contact_sheet.png").exists())
            self.assertTrue((out / "color_families/color_family_layers_contact_sheet.png").exists())


def _write_sequence_source(path: Path) -> None:
    image = Image.new("RGBA", (16, 16), (255, 255, 255, 255))
    for y in range(2, 14):
        for x in range(2, 8):
            image.putpixel((x, y), (15, 15, 20, 255))
        for x in range(8, 14):
            image.putpixel((x, y), (40, 80, 180, 255))
    image.save(path)


if __name__ == "__main__":
    unittest.main()
