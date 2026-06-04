import unittest

from glyph_lab.scale_fit import fit_to_grid


class ScaleFitTests(unittest.TestCase):
    def test_scale_fit_returns_padding_for_object_smaller_than_target(self):
        fit = fit_to_grid(
            {"occupied_bbox_cells": [0, 0, 9, 11]},
            target_width=32,
            target_height=32,
            padding_cells=2,
        )

        self.assertEqual(fit["occupied_width"], 10)
        self.assertEqual(fit["occupied_height"], 12)
        self.assertGreater(fit["padding_left"], 0)
        self.assertGreater(fit["padding_top"], 0)

    def test_scale_fit_warns_when_object_exceeds_target_after_padding(self):
        fit = fit_to_grid(
            {"occupied_bbox_cells": [0, 0, 31, 31]},
            target_width=32,
            target_height=32,
            padding_cells=2,
        )

        self.assertEqual(fit["warning"], "object_too_large")


if __name__ == "__main__":
    unittest.main()
