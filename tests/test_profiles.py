from pathlib import Path
from tempfile import TemporaryDirectory
import subprocess
import json
import unittest

from glyph_lab.profiles import measure_profile


class ProfileTests(unittest.TestCase):
    def test_rectangle_likely_shape_is_rectangle(self):
        measurement = measure_profile(rectangle_mask(16, 16, 4, 11, 2, 13))

        self.assertEqual(measurement["likely_shape"], "rectangle")

    def test_circle_or_ellipse_has_wider_middle_than_top_bottom(self):
        measurement = measure_profile(ellipse_mask(24, 24, 12, 12, 7, 10))

        self.assertGreater(measurement["middle_width"], measurement["top_width"])
        self.assertGreater(measurement["middle_width"], measurement["bottom_width"])
        self.assertEqual(measurement["likely_shape"], "circle_or_ellipse")

    def test_taper_column_top_width_is_less_than_bottom_width(self):
        measurement = measure_profile(taper_mask(24, 24))

        self.assertLess(measurement["top_width"], measurement["bottom_width"])

    def test_taper_ratio_is_less_than_one_for_taper_column(self):
        measurement = measure_profile(taper_mask(24, 24))

        self.assertLess(measurement["taper_ratio"], 1.0)
        self.assertEqual(measurement["likely_shape"], "taper_column")

    def test_centered_rectangle_has_low_symmetry_error(self):
        measurement = measure_profile(rectangle_mask(16, 16, 4, 11, 2, 13))

        self.assertLess(measurement["symmetry_error"], 0.1)

    def test_off_center_rectangle_has_higher_symmetry_error(self):
        centered = measure_profile(rectangle_mask(16, 16, 4, 11, 2, 13))
        off_center = measure_profile(rectangle_mask(16, 16, 1, 8, 2, 13))

        self.assertGreater(off_center["symmetry_error"], centered["symmetry_error"])

    def test_profile_measurements_json_is_written_by_cli(self):
        with TemporaryDirectory() as tmp:
            out = Path(tmp) / "out_profile"

            subprocess.run(
                [
                    ".venv/bin/python",
                    "-m",
                    "glyph_lab.cli",
                    "measure-profile",
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

            data = json.loads((out / "profile_measurements.json").read_text(encoding="utf-8"))
            self.assertIn("crop_box", data)
            self.assertIn("width_profile_by_row", data)
            self.assertTrue((out / "profile_overlay_grid.txt").exists())


def rectangle_mask(width: int, height: int, left: int, right: int, top: int, bottom: int):
    return [[left <= x <= right and top <= y <= bottom for x in range(width)] for y in range(height)]


def ellipse_mask(width: int, height: int, cx: float, cy: float, rx: float, ry: float):
    return [
        [((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1.0 for x in range(width)]
        for y in range(height)
    ]


def taper_mask(width: int, height: int):
    rows = []
    for y in range(height):
        row_width = 4 + int((y / (height - 1)) * 10)
        left = (width - row_width) // 2
        rows.append([left <= x < left + row_width for x in range(width)])
    return rows


if __name__ == "__main__":
    unittest.main()
