from pathlib import Path
from tempfile import TemporaryDirectory
import json
import subprocess
import unittest

from glyph_lab.atlas import generate_pack
from glyph_lab.linework_candidates import write_linework_review
from glyph_lab.linework_primitives import linework_metadata
from glyph_lab.motion_taxonomy import MOTION_METADATA_FIELDS, linework_motion_coverage


class MotionTaxonomyTests(unittest.TestCase):
    def test_line_metadata_includes_motion_fields(self):
        metadata = linework_metadata(
            {
                "kind": "line",
                "params": {"direction": "horizontal", "offset": "middle"},
            }
        )

        for field in MOTION_METADATA_FIELDS:
            self.assertIn(field, metadata)
        self.assertEqual(metadata["motion_profile"], "steady_pull")
        self.assertEqual(metadata["pressure_curve"], "thin")
        self.assertEqual(metadata["release_style"], "clean_exit")

    def test_broken_line_motion_records_dry_break(self):
        metadata = linework_metadata(
            {
                "kind": "line",
                "params": {"direction": "vertical", "offset": "center", "broken": True},
            }
        )

        self.assertEqual(metadata["motion_profile"], "interrupted_pull")
        self.assertEqual(metadata["release_style"], "dry_break")
        self.assertEqual(metadata["rhythm_role"], "single_with_gap")

    def test_hatch_motion_records_repeated_motion(self):
        metadata = linework_metadata(
            {
                "kind": "hatch",
                "params": {"kind": "cross", "density": "dense"},
            }
        )

        self.assertEqual(metadata["motion_profile"], "repeated_motion")
        self.assertEqual(metadata["rhythm_role"], "repeat_dense")
        self.assertIn("repeat_accent", metadata["stress_points"])

    def test_motion_coverage_reports_missing_profiles(self):
        report = linework_motion_coverage(
            [
                {
                    "id": "line.1",
                    "linework_package": "linework.stroke",
                    "motion_profile": "steady_pull",
                    **{
                        field: "x"
                        for field in MOTION_METADATA_FIELDS
                        if field not in {"motion_profile", "stress_points"}
                    },
                    "stress_points": [],
                }
            ]
        )

        self.assertEqual(report["linework_record_count"], 1)
        self.assertIn("linework.stroke", report["missing_expected_motion_profiles"])
        self.assertEqual(report["records_missing_motion_fields"], {})

    def test_cli_linework_coverage_writes_report(self):
        with TemporaryDirectory() as tmp:
            pack = Path(tmp) / "pack"
            generate_pack(pack)
            write_linework_review(pack)
            out = pack / "linework_motion_coverage.json"

            subprocess.run(
                [
                    ".venv/bin/python",
                    "-m",
                    "glyph_lab.cli",
                    "linework-coverage",
                    "--glyphs",
                    str(pack / "linework_accepted_candidates.json"),
                    "--out",
                    str(out),
                ],
                check=True,
                cwd="/Users/kogaryu/font",
            )

            report = json.loads(out.read_text(encoding="utf-8"))
            self.assertGreater(report["linework_record_count"], 0)
            self.assertIn("package_motion_matrix", report)


if __name__ == "__main__":
    unittest.main()
