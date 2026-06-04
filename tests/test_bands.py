from pathlib import Path
import unittest

from glyph_lab.grooves import measure_rhythm_image, rhythm_overlay_grid
from glyph_lab.image_probe import auto_crop_non_background, load_luminance, mass_mask, sample_luminance_grid


class BandTests(unittest.TestCase):
    def test_banded_block_detects_at_least_four_bands(self):
        measurements = measure_rhythm_image("examples/probe_banded_block.png", temp_out(), grid_size=32)

        self.assertGreaterEqual(measurements["band_count"], 4)

    def test_banded_block_likely_moulding_stack(self):
        measurements = measure_rhythm_image("examples/probe_banded_block.png", temp_out(), grid_size=32)

        self.assertTrue(measurements["likely_moulding_stack"])

    def test_overlay_grid_contains_band_markers_for_banded_example(self):
        measurements = measure_rhythm_image("examples/probe_banded_block.png", temp_out(), grid_size=32)
        image = load_luminance("examples/probe_banded_block.png")
        grid = sample_luminance_grid(image, auto_crop_non_background(image), 32, 32)
        overlay = rhythm_overlay_grid(mass_mask(grid), measurements["grooves"], measurements["bands"])

        self.assertIn("=", overlay)


def temp_out():
    path = Path("/tmp/glyph_lab_test_bands")
    path.mkdir(parents=True, exist_ok=True)
    return path


if __name__ == "__main__":
    unittest.main()
