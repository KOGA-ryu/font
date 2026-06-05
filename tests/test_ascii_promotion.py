from pathlib import Path
from tempfile import TemporaryDirectory
import json
import subprocess
import unittest

from glyph_lab.ascii_promotion import promotion_request_from_ascii_manifest, write_ascii_promotion_request
from glyph_lab.atlas import generate_pack
from glyph_lab.brush_candidates import write_brush_review
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

    def test_suggestion_skips_tokens_already_used_by_base_glyphs(self):
        request = promotion_request_from_ascii_manifest(
            manifest_fixture(),
            mapping_fixture(),
            [{"id": "candidate.E"}, {"id": "candidate.A"}],
            used_tokens={"E"},
        )

        self.assertEqual([item["candidate_id"] for item in request["promote"]], ["candidate.A"])
        self.assertEqual(request["metadata"]["skipped"][0]["reason"], "token-already-used")

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

    def test_promote_candidates_can_use_promoted_glyphs_as_base(self):
        with TemporaryDirectory() as tmp:
            pack = Path(tmp) / "pack"
            generate_pack(pack)
            write_linework_review(pack)
            linework_candidate = json.loads(
                (pack / "linework_accepted_candidates.json").read_text(encoding="utf-8")
            )["accepted_candidates"][0]
            linework_request = pack / "linework_promote_candidates.json"
            linework_request.write_text(
                json.dumps({"promote": [{"candidate_id": linework_candidate["id"], "token": "A"}]}, indent=2)
                + "\n",
                encoding="utf-8",
            )
            promote_candidates(pack, linework_request, accepted_path=pack / "linework_accepted_candidates.json")

            write_brush_review(pack)
            brush_candidate = json.loads((pack / "brush_accepted_candidates.json").read_text(encoding="utf-8"))[
                "accepted_candidates"
            ][0]
            brush_request = pack / "brush_promote_candidates.json"
            brush_request.write_text(
                json.dumps({"promote": [{"candidate_id": brush_candidate["id"], "token": "B"}]}, indent=2) + "\n",
                encoding="utf-8",
            )

            report = promote_candidates(
                pack,
                brush_request,
                accepted_path=pack / "brush_accepted_candidates.json",
                base_glyphs_path=pack / "glyphs.promoted.json",
            )

            promoted = json.loads((pack / "glyphs.promoted.json").read_text(encoding="utf-8"))["glyphs"]
            self.assertEqual(report["promoted_count"], 1)
            self.assertEqual(report["base_glyphs_path"], str(pack / "glyphs.promoted.json"))
            self.assertIn("A", {record["token"] for record in promoted})
            self.assertIn("B", {record["token"] for record in promoted})
            brush_record = promoted[-1]
            self.assertEqual(brush_record["promoted_from"], "brush_accepted_candidates.json")
            self.assertIn("brush_family", brush_record)
            self.assertIn("brush_engine", brush_record)
            self.assertIn("density_class", brush_record)

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
