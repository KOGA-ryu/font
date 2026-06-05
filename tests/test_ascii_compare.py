from pathlib import Path
from tempfile import TemporaryDirectory
import json
import subprocess
import unittest

from glyph_lab.ascii_compare import compare_ascii_fallbacks, fallback_comparison


class AsciiCompareTests(unittest.TestCase):
    def test_fallback_comparison_reports_reduction_and_fixed_chars(self):
        report = fallback_comparison(
            manifest_with_fallbacks(["A", "A", "B", "C"]),
            manifest_with_fallbacks(["C"]),
        )

        self.assertEqual(report["before_fallback_total"], 4)
        self.assertEqual(report["after_fallback_total"], 1)
        self.assertEqual(report["fallback_reduction"], 3)
        self.assertEqual(report["fallback_reduction_ratio"], 0.75)
        self.assertEqual([item["char"] for item in report["fixed_chars"]], ["A", "B"])
        self.assertEqual(report["top_remaining_fallbacks"], [{"char": "C", "count": 1}])

    def test_compare_writes_report_and_next_promotion_request(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            before = root / "before.json"
            after = root / "after.json"
            mapping = root / "mapping.json"
            accepted = root / "accepted.json"
            out = root / "out"
            before.write_text(json.dumps(manifest_with_fallbacks(["A", "B", "B"])), encoding="utf-8")
            after.write_text(json.dumps(manifest_with_fallbacks(["B"])), encoding="utf-8")
            mapping.write_text(
                json.dumps({"mapping": {"B": {"glyph_id": "candidate.B", "token": "", "ascii_fallback": "-"}}}),
                encoding="utf-8",
            )
            accepted.write_text(json.dumps({"accepted_candidates": [{"id": "candidate.B"}]}), encoding="utf-8")

            report = compare_ascii_fallbacks(before, after, out, mapping_path=mapping, accepted_path=accepted)

            self.assertTrue((out / "fallback_compare.json").exists())
            self.assertTrue((out / "next_promote_candidates.json").exists())
            self.assertEqual(report["next_promotion_request"]["promote_count"], 1)
            request = json.loads((out / "next_promote_candidates.json").read_text(encoding="utf-8"))
            self.assertEqual(request["promote"][0]["candidate_id"], "candidate.B")

    def test_cli_compare_ascii_fallbacks_writes_report(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            before = root / "before.json"
            after = root / "after.json"
            out = root / "out"
            before.write_text(json.dumps(manifest_with_fallbacks(["A", "A"])), encoding="utf-8")
            after.write_text(json.dumps(manifest_with_fallbacks([])), encoding="utf-8")

            subprocess.run(
                [
                    ".venv/bin/python",
                    "-m",
                    "glyph_lab.cli",
                    "compare-ascii-fallbacks",
                    "--before",
                    str(before),
                    "--after",
                    str(after),
                    "--out",
                    str(out),
                ],
                check=True,
                cwd="/Users/kogaryu/font",
            )

            report = json.loads((out / "fallback_compare.json").read_text(encoding="utf-8"))
            self.assertEqual(report["after_fallback_total"], 0)


def manifest_with_fallbacks(chars):
    return {
        "ascii_bridge": {
            "warnings": [
                {"type": "bridge-fallback", "char": char}
                for char in chars
            ]
        }
    }


if __name__ == "__main__":
    unittest.main()
