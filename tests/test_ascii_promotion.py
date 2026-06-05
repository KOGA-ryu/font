from pathlib import Path
from tempfile import TemporaryDirectory
import json
import subprocess
import unittest

from glyph_lab.ascii_promotion import promotion_request_from_ascii_manifest, write_ascii_promotion_request
from glyph_lab.atlas import generate_pack
from glyph_lab.linework_candidates import write_linework_review
from glyph_lab.promotion import promote_candidates


class AsciiPromotionTests(unittest.TestCase):
    def test_fallback_warnings_create_sorted_promotion_request(self):
        request = promotion_request_from_ascii_manifest(
            manifest_fixture(),
            mapping_fixture(),
            [{"id": "candidate.E"}, {"id": "candidate.A"}],
        )

        self.assertEqual([item["candidate_id"] for item in request["promote"]], ["candidate.E", "candidate.A"])
        self.assertEqual([item["token"] for item in request["promote"]], ["E", "A"])

    def test_suggestion_skips_unaccepted_candidates(self):
        request = promotion_request_from_ascii_manifest(manifest_fixture(), mapping_fixture(), [{"id": "candidate.A"}])

        self.assertEqual([item["candidate_id"] for item in request["promote"]], ["candidate.A"])
        self.assertEqual(request["metadata"]["skipped"][0]["reason"], "candidate-not-accepted")

    def test_write_ascii_promotion_request_writes_json(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = root / "manifest.json"
            mapping = root / "mapping.json"
            accepted = root / "accepted.json"
            out = root / "promote.json"
            manifest.write_text(json.dumps(manifest_fixture()), encoding="utf-8")
            mapping.write_text(json.dumps(mapping_fixture()), encoding="utf-8")
            accepted.write_text(json.dumps({"accepted_candidates": [{"id": "candidate.E"}]}), encoding="utf-8")

            write_ascii_promotion_request(manifest, mapping, accepted, out)

            self.assertTrue(out.exists())
            data = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(data["promote"][0]["candidate_id"], "candidate.E")

    def test_linework_accepted_file_can_be_promoted_by_dry_run(self):
        with TemporaryDirectory() as tmp:
            pack = Path(tmp) / "pack"
            generate_pack(pack)
            write_linework_review(pack)
            accepted = json.loads((pack / "linework_accepted_candidates.json").read_text(encoding="utf-8"))[
                "accepted_candidates"
            ]
            candidate = accepted[0]
            request = pack / "linework_promote_candidates.json"
            request.write_text(
                json.dumps({"promote": [{"candidate_id": candidate["id"], "token": "A"}]}, indent=2) + "\n",
                encoding="utf-8",
            )

            report = promote_candidates(pack, request, accepted_path=pack / "linework_accepted_candidates.json")

            self.assertEqual(report["promoted_count"], 1)
            promoted = json.loads((pack / "glyphs.promoted.json").read_text(encoding="utf-8"))["glyphs"][-1]
            self.assertEqual(promoted["promoted_from"], "linework_accepted_candidates.json")
            self.assertIn("angle_degrees", promoted)
            self.assertIn("connector_sides", promoted)

    def test_cli_suggest_ascii_promotions_writes_request(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = root / "manifest.json"
            mapping = root / "mapping.json"
            accepted = root / "accepted.json"
            out = root / "promote.json"
            manifest.write_text(json.dumps(manifest_fixture()), encoding="utf-8")
            mapping.write_text(json.dumps(mapping_fixture()), encoding="utf-8")
            accepted.write_text(json.dumps({"accepted_candidates": [{"id": "candidate.E"}]}), encoding="utf-8")

            subprocess.run(
                [
                    ".venv/bin/python",
                    "-m",
                    "glyph_lab.cli",
                    "suggest-ascii-promotions",
                    "--manifest",
                    str(manifest),
                    "--mapping",
                    str(mapping),
                    "--accepted",
                    str(accepted),
                    "--out",
                    str(out),
                ],
                check=True,
                cwd="/Users/kogaryu/font",
            )

            self.assertTrue(out.exists())


def manifest_fixture():
    return {
        "ascii_bridge": {
            "warnings": [
                {"type": "bridge-fallback", "char": "A"},
                {"type": "bridge-fallback", "char": "E"},
                {"type": "bridge-fallback", "char": "E"},
                {"type": "unmapped-ascii-char", "char": "?"},
            ]
        }
    }


def mapping_fixture():
    return {
        "mapping": {
            "A": {"glyph_id": "candidate.A", "token": "", "ascii_fallback": "-"},
            "E": {"glyph_id": "candidate.E", "token": "", "ascii_fallback": "-"},
        }
    }


if __name__ == "__main__":
    unittest.main()
