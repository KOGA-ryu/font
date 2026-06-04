import unittest

from glyph_lab.anchors import detect_anchor_points


class AnchorTests(unittest.TestCase):
    def test_band_rows_create_anchor_points(self):
        anchors = detect_anchor_points(profile_fixture(), {"major_band_rows": [4, 12]})

        self.assertIn("band_row", {anchor["source"] for anchor in anchors})
        self.assertTrue(any(anchor["y"] == 4 for anchor in anchors))

    def test_groove_start_and_end_rows_create_anchor_points(self):
        anchors = detect_anchor_points(
            profile_fixture(),
            {
                "grooves": [
                    {
                        "x_cell": 9,
                        "y_start": 3,
                        "y_end": 20,
                        "length": 18,
                        "confidence": 0.71,
                    }
                ]
            },
        )

        sources = {anchor["source"] for anchor in anchors}
        self.assertIn("groove_start", sources)
        self.assertIn("groove_end", sources)


def profile_fixture():
    return {
        "grid_size": [32, 32],
        "occupied_bbox_cells": [8, 2, 23, 29],
        "centerline_x_estimate": 15.5,
        "width_profile_by_row": [0, 0] + [16] * 28 + [0, 0],
        "bulge_rows": [],
        "neck_rows": [],
    }


if __name__ == "__main__":
    unittest.main()
