from pathlib import Path
from tempfile import TemporaryDirectory
import json
import subprocess
import unittest

from glyph_lab.measurement_pass import (
    build_layer_evidence_from_probe_outputs,
    final_measurements_from_layer_evidence,
)


class MeasurementPassTests(unittest.TestCase):
    def test_final_measurement_records_include_provenance_fields(self):
        records = final_measurements_from_layer_evidence(sample_evidence())

        for record in records:
            self.assertIn("value", record)
            self.assertIn("unit", record)
            self.assertIn("source_layers", record)
            self.assertIn("method", record)
            self.assertIn("confidence", record)

    def test_missing_rhythm_input_lowers_groove_measurement_confidence(self):
        evidence = build_layer_evidence_from_probe_outputs(profile=profile_measurements(), layered=layered_grid())

        groove = record_by_name(final_measurements_from_layer_evidence(evidence), "groove_count")

        self.assertLessEqual(groove["confidence"], 0.1)
        self.assertIn("Missing rhythm input", groove["notes"])

    def test_shadow_depth_hint_returns_relative_unit_and_confidence(self):
        shadow = record_by_name(final_measurements_from_layer_evidence(sample_evidence()), "shadow_depth_hint")

        self.assertEqual(shadow["unit"], "relative")
        self.assertGreaterEqual(shadow["confidence"], 0.0)
        self.assertLessEqual(shadow["confidence"], 1.0)
        self.assertIn("Relative hint", shadow["notes"])

    def test_curve_presence_hint_uses_profile_bulge_and_neck_rows(self):
        curve = record_by_name(final_measurements_from_layer_evidence(sample_evidence()), "curve_presence_hint")

        self.assertTrue(curve["value"])
        self.assertEqual(curve["metadata"]["source_rows"], [4, 5, 12])

    def test_cli_measure_from_art_passes_writes_outputs(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            probe = root / "probe.json"
            profile = root / "profile.json"
            rhythm = root / "rhythm.json"
            layered = root / "layered.json"
            out = root / "out_measure_art"
            probe.write_text(json.dumps(probe_measurements()), encoding="utf-8")
            profile.write_text(json.dumps(profile_measurements()), encoding="utf-8")
            rhythm.write_text(json.dumps(rhythm_measurements()), encoding="utf-8")
            layered.write_text(json.dumps(layered_grid()), encoding="utf-8")

            subprocess.run(
                [
                    ".venv/bin/python",
                    "-m",
                    "glyph_lab.cli",
                    "measure-from-art-passes",
                    "--probe",
                    str(probe),
                    "--profile",
                    str(profile),
                    "--rhythm",
                    str(rhythm),
                    "--layered",
                    str(layered),
                    "--out",
                    str(out),
                ],
                check=True,
                cwd="/Users/kogaryu/font",
            )

            self.assertTrue((out / "final_measurements.json").exists())
            self.assertTrue((out / "art_pass_summary.json").exists())


def sample_evidence():
    return build_layer_evidence_from_probe_outputs(
        probe=probe_measurements(),
        profile=profile_measurements(),
        rhythm=rhythm_measurements(),
        layered=layered_grid(),
    )


def record_by_name(records, name):
    return next(record for record in records if record["name"] == name)


def layered_grid():
    return {
        "grid_width": 4,
        "grid_height": 4,
        "layers": [
            {"name": "mass", "grid": ["AAAA", "AAAA", "AAAA", "AAAA"]},
            {"name": "base_fill", "grid": ["bbbb", "bbbb", "bbbb", "bbbb"]},
            {"name": "shadow", "grid": ["    ", " ss ", " ss ", "    "]},
            {"name": "highlight", "grid": ["hhhh", "    ", "    ", "    "]},
            {"name": "edge", "grid": ["|  |", "|  |", "|  |", "|  |"]},
        ],
    }


def profile_measurements():
    return {
        "grid_size": [4, 4],
        "occupied_bbox_cells": [0, 0, 3, 3],
        "centerline_x_estimate": 1.5,
        "total_height_cells": 4,
        "max_width_cells": 4,
        "taper_ratio": 0.75,
        "likely_shape": "taper_column",
        "bulge_rows": [4, 5],
        "neck_rows": [12],
    }


def probe_measurements():
    return {
        "grid_width": 4,
        "grid_height": 4,
        "occupied_bbox_cells": [0, 0, 3, 3],
        "centerline_x_estimate": 1.5,
    }


def rhythm_measurements():
    return {
        "grid_size": [4, 4],
        "groove_count": 2,
        "average_groove_spacing": 2.0,
        "band_count": 1,
        "average_band_spacing": 0,
    }


if __name__ == "__main__":
    unittest.main()
