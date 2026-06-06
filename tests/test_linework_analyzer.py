from pathlib import Path
from tempfile import TemporaryDirectory
import json
import subprocess
import unittest

from PIL import Image, ImageDraw

from glyph_lab.atlas import generate_pack
from glyph_lab.linework_analyzer import (
    analyze_linework_grid,
    analyze_linework_image,
    evidence_to_layered_grid,
    pressure_evidence_from_linework,
)


class LineworkAnalyzerTests(unittest.TestCase):
    def test_horizontal_line_declares_steady_pull(self):
        grid = white_grid()
        grid[2] = [20, 20, 20, 20, 20]

        evidence = analyze_linework_grid(grid)

        profiles = {cell["motion_profile"] for cell in evidence["linework_cells"]}
        self.assertIn("steady_pull", profiles)
        self.assertGreater(evidence["linework_cell_count"], 0)

    def test_diagonal_line_declares_angled_pull(self):
        grid = white_grid()
        for index in range(5):
            grid[4 - index][index] = 20

        evidence = analyze_linework_grid(grid)

        profiles = {cell["motion_profile"] for cell in evidence["linework_cells"]}
        self.assertIn("angled_pull", profiles)

    def test_turn_declares_direction_change(self):
        grid = white_grid()
        for x in range(3):
            grid[2][x] = 20
        for y in range(2, 5):
            grid[y][2] = 20

        evidence = analyze_linework_grid(grid)

        profiles = {cell["motion_profile"] for cell in evidence["linework_cells"]}
        self.assertIn("direction_change", profiles)

    def test_layered_grid_contains_cell_metadata(self):
        evidence = {
            "grid_width": 2,
            "grid_height": 1,
            "linework_cells": [
                {
                    "x": 0,
                    "y": 0,
                    "motion_profile": "steady_pull",
                    "stroke_topology": "pass_through_segment",
                    "linework_package": "linework.stroke",
                    "angle_degrees": 0.0,
                    "pressure_curve": "thin",
                    "release_style": "clean_exit",
                }
            ],
        }

        layered, report = evidence_to_layered_grid(evidence, [{"id": "line", "token": "-", "linework_kind": "line"}])

        self.assertEqual(layered["layers"][0]["name"], "linework")
        self.assertEqual(layered["layers"][1]["name"], "linework_pressure")
        self.assertEqual(layered["layers"][0]["cell_metadata"][0]["motion_profile"], "steady_pull")
        self.assertEqual(report["linework_cell_count"], 1)
        self.assertEqual(report["pressure_cell_count"], 0)

    def test_pressure_evidence_marks_heavy_and_stressed_cells(self):
        evidence = {
            "grid_width": 2,
            "grid_height": 1,
            "linework_cells": [
                {
                    "x": 0,
                    "y": 0,
                    "motion_profile": "direction_change",
                    "angle_degrees": 0.0,
                    "pressure_curve": "heavy",
                    "stress_points": ["corner"],
                    "neighbor_count": 5,
                    "confidence": 0.9,
                },
                {
                    "x": 1,
                    "y": 0,
                    "motion_profile": "steady_pull",
                    "angle_degrees": 0.0,
                    "pressure_curve": "medium",
                    "stress_points": [],
                    "neighbor_count": 2,
                    "confidence": 0.8,
                },
            ],
        }

        pressure = pressure_evidence_from_linework(evidence)

        self.assertEqual(pressure["pressure_cell_count"], 1)
        self.assertEqual(pressure["pressure_cells"][0]["layer"], "linework_pressure")
        self.assertEqual(pressure["pressure_cells"][0]["motion_profile"], "pressed_pull")
        self.assertEqual(pressure["pressure_cells"][0]["pressure_intensity"], "heavy")

    def test_analyze_linework_image_writes_outputs(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            pack = root / "pack"
            out = root / "out"
            image = root / "line.png"
            generate_pack(pack)
            _write_test_image(image)

            result = analyze_linework_image(image, pack, out, grid_size=8)

            self.assertTrue((out / "linework_evidence.json").exists())
            self.assertTrue((out / "linework_pressure_evidence.json").exists())
            self.assertTrue((out / "generated_motion_layered_grid.json").exists())
            self.assertTrue((out / "motion_selection_report.json").exists())
            self.assertTrue((out / "proof_128.png").exists())
            self.assertIn("linework_motion", result["manifest"])
            self.assertIn("pressure_cell_count", result["manifest"]["linework_motion"])

    def test_cli_analyze_linework_image_writes_outputs(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            pack = root / "pack"
            out = root / "out_cli"
            image = root / "line.png"
            generate_pack(pack)
            _write_test_image(image)

            subprocess.run(
                [
                    ".venv/bin/python",
                    "-m",
                    "glyph_lab.cli",
                    "analyze-linework-image",
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

            self.assertTrue((out / "linework_evidence.json").exists())
            self.assertTrue((out / "linework_pressure_evidence.json").exists())
            self.assertTrue((out / "proof_128.png").exists())


def white_grid():
    return [[255 for _x in range(5)] for _y in range(5)]


def _write_test_image(path: Path) -> None:
    image = Image.new("RGB", (64, 64), "white")
    draw = ImageDraw.Draw(image)
    draw.line((8, 32, 56, 32), fill="black", width=4)
    image.save(path)


if __name__ == "__main__":
    unittest.main()
