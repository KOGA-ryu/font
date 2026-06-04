from pathlib import Path
from tempfile import TemporaryDirectory
import json
import subprocess
import unittest

from glyph_lab.profiles import measure_profile
from glyph_lab.scaffold import build_scaffold, detect_support_lines, measure_scaffold_image


class ScaffoldTests(unittest.TestCase):
    def test_centered_taper_column_detects_vertical_primary_support_line(self):
        mask = taper_column_mask()
        profile = measure_profile(mask)
        scaffold = build_scaffold(mask, profile, rhythm_fixture())

        self.assertEqual(scaffold["primary_support_line"]["kind"], "vertical")
        self.assertEqual(scaffold["primary_support_line"]["id"], "support.vertical_centerline")

    def test_support_line_confidence_is_positive(self):
        mask = taper_column_mask()
        profile = measure_profile(mask)
        scaffold = build_scaffold(mask, profile, rhythm_fixture())

        self.assertGreater(scaffold["primary_support_line"]["confidence"], 0)

    def test_bottom_baseline_candidate_exists_for_rectangle_block(self):
        mask = rectangle_mask()
        profile = measure_profile(mask)
        candidates = detect_support_lines(mask, profile, {})

        self.assertIn("support.bottom_baseline", {line["id"] for line in candidates})

    def test_attached_horizontal_band_lines_reference_primary_support_line(self):
        mask = taper_column_mask()
        profile = measure_profile(mask)
        scaffold = build_scaffold(mask, profile, rhythm_fixture())

        band_lines = [line for line in scaffold["attached_lines"] if line["kind"] == "horizontal"]
        self.assertTrue(band_lines)
        self.assertTrue(
            all(line["parent_support"] == scaffold["primary_support_line"]["id"] for line in band_lines)
        )

    def test_angle_degrees_for_vertical_support_is_approximately_90(self):
        mask = taper_column_mask()
        profile = measure_profile(mask)
        scaffold = build_scaffold(mask, profile, rhythm_fixture())

        self.assertAlmostEqual(scaffold["primary_support_line"]["angle_degrees"], 90.0)

    def test_measure_scaffold_image_writes_support_graph(self):
        with TemporaryDirectory() as tmp:
            result = measure_scaffold_image(
                "examples/probe_taper_column.png",
                tmp,
                grid_size=32,
                write_overlay_png=False,
            )

            self.assertEqual(result["primary_support_line"]["kind"], "vertical")
            self.assertTrue((Path(tmp) / "scaffold_measurements.json").exists())
            self.assertTrue((Path(tmp) / "scaffold_overlay_grid.txt").exists())

    def test_cli_writes_scaffold_measurements_and_overlay_grid(self):
        with TemporaryDirectory() as tmp:
            out = Path(tmp) / "out_scaffold"

            subprocess.run(
                [
                    ".venv/bin/python",
                    "-m",
                    "glyph_lab.cli",
                    "measure-scaffold",
                    "--image",
                    "examples/probe_taper_column.png",
                    "--out",
                    str(out),
                    "--grid-size",
                    "32",
                ],
                check=True,
                cwd="/Users/kogaryu/font",
            )

            measurements = json.loads((out / "scaffold_measurements.json").read_text(encoding="utf-8"))
            self.assertTrue((out / "scaffold_overlay_grid.txt").exists())
            self.assertIn("primary_support_line", measurements)
            self.assertIn("angle_measurements", measurements)
            self.assertIn("scale_fit", measurements)


def taper_column_mask():
    rows = []
    for y in range(32):
        if y < 2 or y > 29:
            rows.append([False] * 32)
            continue
        width = 10 + round((y - 2) * 10 / 27)
        left = 16 - width // 2
        right = left + width
        rows.append([left <= x < right for x in range(32)])
    return rows


def rectangle_mask():
    return [[6 <= x <= 25 and 4 <= y <= 27 for x in range(32)] for y in range(32)]


def rhythm_fixture():
    return {
        "bands": [
            {"y_cell": 5, "x_start": 8, "x_end": 23, "thickness": 1, "confidence": 0.8},
            {"y_cell": 27, "x_start": 5, "x_end": 26, "thickness": 1, "confidence": 0.82},
        ],
        "major_band_rows": [5, 27],
        "grooves": [
            {"x_cell": 12, "y_start": 6, "y_end": 26, "length": 21, "confidence": 0.74},
            {"x_cell": 19, "y_start": 6, "y_end": 26, "length": 21, "confidence": 0.74},
        ],
    }


if __name__ == "__main__":
    unittest.main()
