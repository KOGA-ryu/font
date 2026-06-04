from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest

from glyph_lab.atlas import generate_pack, stamp_for_index
from glyph_lab.generate_candidates import write_primitive_review
from glyph_lab.measure import measure_stamp
from glyph_lab.promotion import promote_candidates
from glyph_lab.transforms import stamp_to_bitmask


class PromotionTests(unittest.TestCase):
    def test_candidate_not_in_accepted_list_is_rejected(self):
        with prepared_pack() as pack:
            request = write_request(pack, [{"candidate_id": "missing"}])

            report = promote_candidates(pack, request)

            self.assertEqual(report["rejected_count"], 1)
            self.assertEqual(report["rejected_candidate_ids"][0]["reason"], "candidate-not-in-accepted-list")

    def test_duplicate_token_is_rejected(self):
        with prepared_pack() as pack:
            candidate_id = first_accepted_id(pack)
            request = write_request(pack, [{"candidate_id": candidate_id, "token": "#"}])

            report = promote_candidates(pack, request)

            self.assertEqual(report["rejected_candidate_ids"][0]["reason"], "token-already-exists")

    def test_omitted_token_gets_deterministic_next_available_token(self):
        with prepared_pack() as pack:
            candidate_id = first_accepted_id(pack)
            request = write_request(pack, [{"candidate_id": candidate_id}])

            report = promote_candidates(pack, request)

            self.assertEqual(report["token_assignments"][candidate_id], "A")

    def test_promotion_preserves_primitive_lineage_metadata(self):
        with prepared_pack() as pack:
            candidate_id = first_accepted_id(pack)
            request = write_request(pack, [{"candidate_id": candidate_id, "notes": "promote test"}])

            promote_candidates(pack, request)
            promoted = promoted_records(pack)[-1]

            self.assertTrue(promoted["generated"])
            self.assertEqual(promoted["source"], "primitive")
            self.assertIn("primitive_family", promoted)
            self.assertIn("primitive_params", promoted)
            self.assertEqual(promoted["source_candidate_id"], candidate_id)
            self.assertEqual(promoted["promoted_from"], "primitive_accepted_candidates.json")
            self.assertEqual(promoted["promoted_at_version"], "glyph_lab_v0")

    def test_dry_run_writes_promoted_file_without_mutating_glyphs(self):
        with prepared_pack() as pack:
            before = (pack / "glyphs.json").read_text(encoding="utf-8")
            candidate_id = first_accepted_id(pack)
            request = write_request(pack, [{"candidate_id": candidate_id}])

            promote_candidates(pack, request)

            self.assertTrue((pack / "glyphs.promoted.json").exists())
            self.assertEqual((pack / "glyphs.json").read_text(encoding="utf-8"), before)

    def test_apply_mutates_glyphs_and_writes_backup(self):
        with prepared_pack() as pack:
            candidate_id = first_accepted_id(pack)
            request = write_request(pack, [{"candidate_id": candidate_id}])

            report = promote_candidates(pack, request, apply=True)

            self.assertTrue(Path(report["backup_path"]).exists())
            self.assertEqual(len(load_records(pack / "glyphs.json")), 33)

    def test_duplicate_canonical_id_is_rejected_unless_forced(self):
        with prepared_pack() as pack:
            accepted_path = pack / "primitive_accepted_candidates.json"
            data = json.loads(accepted_path.read_text(encoding="utf-8"))
            duplicate = active_duplicate_candidate()
            data["accepted_candidates"].append(duplicate)
            accepted_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

            request = write_request(pack, [{"candidate_id": duplicate["id"]}])
            rejected = promote_candidates(pack, request)
            self.assertEqual(rejected["rejected_candidate_ids"][0]["reason"], "duplicate-canonical-id")

            forced_request = write_request(pack, [{"candidate_id": duplicate["id"], "force_duplicate": True}])
            forced = promote_candidates(pack, forced_request)
            self.assertEqual(forced["promoted_count"], 1)

    def test_promotion_report_records_promoted_and_rejected_entries(self):
        with prepared_pack() as pack:
            candidate_id = first_accepted_id(pack)
            request = write_request(pack, [{"candidate_id": candidate_id}, {"candidate_id": "missing"}])

            report = promote_candidates(pack, request)

            self.assertEqual(report["promoted_count"], 1)
            self.assertEqual(report["rejected_count"], 1)
            self.assertIn(candidate_id, report["promoted_candidate_ids"])
            self.assertEqual(report["rejected_candidate_ids"][0]["candidate_id"], "missing")


def prepared_pack():
    temp = TemporaryDirectory()
    pack = Path(temp.name) / "pack"
    generate_pack(pack)
    write_primitive_review(pack)

    class Context:
        def __enter__(self):
            return pack

        def __exit__(self, *_args):
            temp.cleanup()

    return Context()


def write_request(pack: Path, items: list[dict]) -> Path:
    path = pack / "promote_candidates.json"
    path.write_text(json.dumps({"promote": items}, indent=2) + "\n", encoding="utf-8")
    return path


def first_accepted_id(pack: Path) -> str:
    return json.loads((pack / "primitive_accepted_candidates.json").read_text(encoding="utf-8"))[
        "accepted_candidates"
    ][0]["id"]


def promoted_records(pack: Path) -> list[dict]:
    return load_records(pack / "glyphs.promoted.json")


def load_records(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))["glyphs"]


def active_duplicate_candidate() -> dict:
    features = measure_stamp(stamp_for_index(14))
    features["bitmask"] = stamp_to_bitmask(stamp_for_index(14))
    return {
        "id": "test.duplicate.horizontal_edge",
        "token": "",
        "index": 9000,
        "role": "edge",
        "family": "horizontal",
        "layer": "edge",
        "palette_role": "ink",
        "cell_size": 4,
        "features": features,
        "constraints": {},
        "generated": True,
        "source": "primitive",
        "primitive_family": "line",
        "primitive_params": {"orientation": "horizontal", "thickness": 2},
        "usefulness_score": 1.0,
        "rejection_reason": None,
        "review_tags": ["candidate"],
        "equivalence_group": "rotations",
        "canonical_id": 3855,
    }


if __name__ == "__main__":
    unittest.main()
