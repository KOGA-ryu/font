from pathlib import Path
from tempfile import TemporaryDirectory
import json
import subprocess
import unittest

from glyph_lab.fusion import fuse_measurements
from glyph_lab.object_hints import object_family_hints


class ObjectHintTests(unittest.TestCase):
    def test_fluted_column_measurements_produce_top_hint(self):
        hints = object_family_hints(fuse_measurements(profile_fluted(), rhythm_fluted()))

        self.assertEqual(hints["top_hint"]["family"], "fluted_column")

    def test_banded_block_measurements_produce_top_hint(self):
        hints = object_family_hints(fuse_measurements(profile_banded_block(), rhythm_banded_block()))

        self.assertEqual(hints["top_hint"]["family"], "banded_block")

    def test_plain_rectangle_produces_panel_or_simple_column(self):
        hints = object_family_hints(fuse_measurements(profile_rectangle(), {}))

        self.assertIn(hints["top_hint"]["family"], {"panel", "simple_column"})

    def test_confidence_includes_reasons_and_missing_evidence(self):
        top = object_family_hints(fuse_measurements(profile_fluted(), rhythm_fluted()))["top_hint"]

        self.assertGreater(top["confidence"], 0)
        self.assertIn("reasons", top)
        self.assertIn("missing_evidence", top)
        self.assertIn("measurement_sources", top)

    def test_unknown_fallback_for_weak_evidence(self):
        hints = object_family_hints(fuse_measurements({"likely_shape": "unknown"}, {}))

        self.assertEqual(hints["top_hint"]["family"], "unknown")

    def test_cli_writes_fused_features_and_object_hints(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            profile = root / "profile.json"
            rhythm = root / "rhythm.json"
            out = root / "out_hint"
            profile.write_text(json.dumps(profile_fluted()), encoding="utf-8")
            rhythm.write_text(json.dumps(rhythm_fluted()), encoding="utf-8")

            subprocess.run(
                [
                    ".venv/bin/python",
                    "-m",
                    "glyph_lab.cli",
                    "hint-object",
                    "--profile",
                    str(profile),
                    "--rhythm",
                    str(rhythm),
                    "--out",
                    str(out),
                ],
                check=True,
                cwd="/Users/kogaryu/font",
            )

            self.assertTrue((out / "fused_features.json").exists())
            self.assertTrue((out / "object_family_hints.json").exists())


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


def profile_banded_block():
    return {
        "grid_size": [32, 32],
        "crop_box": [28, 20, 100, 108],
        "occupied_bbox_cells": [1, 1, 30, 30],
        "total_height_cells": 32,
        "max_width_cells": 30,
        "taper_ratio": 1.0,
        "symmetry_error": 0.0,
        "likely_shape": "rectangle",
    }


def rhythm_banded_block():
    return {
        "grid_size": [32, 32],
        "groove_count": 2,
        "average_groove_spacing": 29,
        "groove_spacing_variance": 0,
        "rhythm_confidence": 1.0,
        "likely_repeated_grooves": False,
        "band_count": 6,
        "average_band_spacing": 4.8,
        "band_spacing_variance": 0.16,
        "likely_moulding_stack": True,
    }


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


if __name__ == "__main__":
    unittest.main()
