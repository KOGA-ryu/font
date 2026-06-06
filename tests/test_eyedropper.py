from pathlib import Path
from tempfile import TemporaryDirectory
import json
import subprocess
import unittest

from PIL import Image

from glyph_lab.eyedropper import (
    grid_samples,
    parse_grid_size,
    parse_point,
    sample_color,
    write_eyedropper_json,
)


class EyedropperTests(unittest.TestCase):
    def test_sample_color_returns_rgba_hex_and_luminance(self):
        with TemporaryDirectory() as tmp:
            image_path = Path(tmp) / "sample.png"
            write_sample_image(image_path)

            sample = sample_color(image_path, 1, 0, label="red")

            self.assertEqual(sample["label"], "red")
            self.assertEqual(sample["rgba"], [255, 0, 0, 255])
            self.assertEqual(sample["hex"], "#ff0000")
            self.assertEqual(sample["luminance"], 76)

    def test_sample_color_rejects_out_of_bounds_point(self):
        with TemporaryDirectory() as tmp:
            image_path = Path(tmp) / "sample.png"
            write_sample_image(image_path)

            with self.assertRaisesRegex(ValueError, "outside image bounds"):
                sample_color(image_path, 99, 0)

    def test_grid_samples_use_cell_centers(self):
        with TemporaryDirectory() as tmp:
            image_path = Path(tmp) / "sample.png"
            write_sample_image(image_path)

            samples = grid_samples(image_path, 2, 2)

            self.assertEqual(len(samples), 4)
            self.assertEqual(samples[0]["grid_x"], 0)
            self.assertEqual(samples[0]["grid_y"], 0)
            self.assertIn("hex", samples[0])

    def test_write_eyedropper_json_merges_into_base_json(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            image_path = root / "sample.png"
            base_json = root / "base.json"
            out = root / "out.json"
            write_sample_image(image_path)
            base_json.write_text(json.dumps({"existing": True}), encoding="utf-8")

            payload = write_eyedropper_json(
                image_path,
                out,
                points=[(1, 0, "red")],
                base_json_path=base_json,
                json_key="palette_samples",
            )

            self.assertTrue(payload["existing"])
            self.assertEqual(payload["palette_samples"]["samples"][0]["label"], "red")
            written = json.loads(out.read_text(encoding="utf-8"))
            self.assertIn("palette_samples", written)

    def test_parse_point_accepts_label_and_coordinates(self):
        self.assertEqual(parse_point("skin:12,34"), (12, 34, "skin"))
        self.assertEqual(parse_point("12,34"), (12, 34, None))

    def test_parse_grid_size_accepts_x_or_comma(self):
        self.assertEqual(parse_grid_size("4x8"), (4, 8))
        self.assertEqual(parse_grid_size("4X8"), (4, 8))
        self.assertEqual(parse_grid_size("4,8"), (4, 8))

    def test_cli_eyedropper_sample_writes_json(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            image_path = root / "sample.png"
            out = root / "samples.json"
            write_sample_image(image_path)

            subprocess.run(
                [
                    ".venv/bin/python",
                    "-m",
                    "glyph_lab.cli",
                    "eyedropper-sample",
                    "--image",
                    str(image_path),
                    "--point",
                    "red:1,0",
                    "--grid-size",
                    "2x2",
                    "--out",
                    str(out),
                ],
                check=True,
                cwd="/Users/kogaryu/font",
            )

            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload["eyedropper_samples"]["samples"][0]["label"], "red")
            self.assertEqual(len(payload["eyedropper_samples"]["samples"]), 5)


def write_sample_image(path: Path) -> None:
    image = Image.new("RGBA", (4, 4), (0, 0, 0, 255))
    pixels = image.load()
    pixels[1, 0] = (255, 0, 0, 255)
    pixels[3, 3] = (0, 0, 255, 128)
    image.save(path)


if __name__ == "__main__":
    unittest.main()
