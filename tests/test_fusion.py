import unittest

from glyph_lab.fusion import fuse_measurements


class FusionTests(unittest.TestCase):
    def test_missing_rhythm_data_still_fuses_profile_data(self):
        fused = fuse_measurements(profile_rectangle())

        self.assertEqual(fused["likely_shape"], "rectangle")
        self.assertEqual(fused["groove_count"], 0)
        self.assertIn("profile", fused["measurement_sources"])
        self.assertIn("rectangle_like", fused["feature_flags"])

    def test_fused_features_include_expected_flags(self):
        fused = fuse_measurements(profile_fluted(), rhythm_fluted())

        self.assertIn("tall", fused["feature_flags"])
        self.assertIn("tapered", fused["feature_flags"])
        self.assertIn("repeated_vertical_grooves", fused["feature_flags"])


def profile_rectangle():
    return {
        "grid_size": [32, 32],
        "crop_box": [20, 20, 84, 84],
        "occupied_bbox_cells": [2, 2, 29, 29],
        "total_height_cells": 28,
        "max_width_cells": 28,
        "taper_ratio": 1.0,
        "symmetry_error": 0.0,
        "likely_shape": "rectangle",
    }


def profile_fluted():
    return {
        "grid_size": [32, 32],
        "crop_box": [30, 16, 99, 113],
        "occupied_bbox_cells": [1, 0, 30, 31],
        "total_height_cells": 32,
        "max_width_cells": 30,
        "taper_ratio": 0.6,
        "symmetry_error": 0.0312,
        "likely_shape": "taper_column",
    }


def rhythm_fluted():
    return {
        "grid_size": [32, 32],
        "groove_count": 8,
        "average_groove_spacing": 2.57,
        "groove_spacing_variance": 0.2449,
        "rhythm_confidence": 1.0,
        "likely_repeated_grooves": True,
        "band_count": 2,
        "average_band_spacing": 28,
        "band_spacing_variance": 0,
        "likely_moulding_stack": False,
    }


if __name__ == "__main__":
    unittest.main()
