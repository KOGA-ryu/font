from pathlib import Path
from tempfile import TemporaryDirectory
import json
import subprocess
import unittest

from PIL import Image

from glyph_lab.grooves import measure_rhythm_image, rhythm_overlay_grid
from glyph_lab.image_probe import edge_map, mass_mask, sample_luminance_grid


class GrooveTests(unittest.TestCase):
    def test_fluted_column_detects_at_least_six_grooves(self):
        measurements = measure_rhythm_image("examples/probe_fluted_column.png", temp_out(), grid_size=32)

        self.assertGreaterEqual(measurements["groove_count"], 6)

    def test_fluted_column_likely_repeated_grooves(self):
        measurements = measure_rhythm_image("examples/probe_fluted_column.png", temp_out(), grid_size=32)

        self.assertTrue(measurements["likely_repeated_grooves"])

    def test_groove_spacing_variance_is_finite_and_non_negative(self):
        measurements = measure_rhythm_image("examples/probe_fluted_column.png", temp_out(), grid_size=32)

        self.assertIsNotNone(measurements["groove_spacing_variance"])
        self.assertGreaterEqual(measurements["groove_spacing_variance"], 0)

    def test_blank_image_detects_no_grooves_or_bands(self):
        with TemporaryDirectory() as tmp:
            image_path = Path(tmp) / "blank.png"
            Image.new("RGB", (64, 64), (255, 255, 255)).save(image_path)
            measurements = measure_rhythm_image(image_path, Path(tmp) / "out", grid_size=32)

            self.assertEqual(measurements["groove_count"], 0)
            self.assertEqual(measurements["band_count"], 0)

    def test_overlay_grid_contains_groove_markers_for_fluted_example(self):
        measurements = measure_rhythm_image("examples/probe_fluted_column.png", temp_out(), grid_size=32)
        grid = image_grid("examples/probe_fluted_column.png")
        mask = mass_mask(grid)
        overlay = rhythm_overlay_grid(mask, measurements["grooves"], measurements["bands"])

        self.assertIn("|", overlay)

    def test_rhythm_measurements_json_is_written_by_cli(self):
        with TemporaryDirectory() as tmp:
            out = Path(tmp) / "out_rhythm"
            subprocess.run(
                [
                    ".venv/bin/python",
                    "-m",
                    "glyph_lab.cli",
                    "measure-rhythm",
                    "--image",
                    "examples/probe_fluted_column.png",
                    "--out",
                    str(out),
                    "--grid-size",
                    "32",
                ],
                check=True,
                cwd="/Users/kogaryu/font",
            )

            data = json.loads((out / "rhythm_measurements.json").read_text(encoding="utf-8"))
            self.assertIn("groove_count", data)
            self.assertTrue((out / "rhythm_overlay_grid.txt").exists())


def image_grid(path):
    from glyph_lab.image_probe import auto_crop_non_background, load_luminance

    image = load_luminance(path)
    return sample_luminance_grid(image, auto_crop_non_background(image), 32, 32)


def temp_out():
    path = Path("/tmp/glyph_lab_test_rhythm")
    path.mkdir(parents=True, exist_ok=True)
    return path


if __name__ == "__main__":
    unittest.main()
