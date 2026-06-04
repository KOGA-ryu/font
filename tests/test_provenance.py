import unittest

from glyph_lab.provenance import measurement_record


class ProvenanceTests(unittest.TestCase):
    def test_measurement_record_includes_required_provenance_fields(self):
        record = measurement_record(
            name="object_width_cells",
            value=12,
            unit="cells",
            source_layers=["linework"],
            source_measurements=["profile.max_width_cells"],
            method="read width from profile",
            confidence=0.75,
            notes="cell-space estimate",
        )

        self.assertEqual(record["value"], 12)
        self.assertEqual(record["unit"], "cells")
        self.assertEqual(record["source_layers"], ["linework"])
        self.assertEqual(record["source_measurements"], ["profile.max_width_cells"])
        self.assertEqual(record["method"], "read width from profile")
        self.assertEqual(record["confidence"], 0.75)
        self.assertIn("notes", record)

    def test_measurement_record_rejects_invalid_confidence(self):
        with self.assertRaisesRegex(ValueError, "between 0.0 and 1.0"):
            measurement_record(
                name="bad",
                value=None,
                unit="cells",
                source_layers=[],
                source_measurements=[],
                method="invalid",
                confidence=1.1,
            )


if __name__ == "__main__":
    unittest.main()
