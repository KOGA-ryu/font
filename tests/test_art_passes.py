import unittest

from glyph_lab.art_passes import ArtPass, LayerEvidence, default_art_passes, validate_art_passes


class ArtPassTests(unittest.TestCase):
    def test_default_art_passes_are_ordered_correctly(self):
        passes = default_art_passes()

        self.assertEqual([art_pass.order for art_pass in passes], list(range(8)))
        self.assertEqual(
            [art_pass.name for art_pass in passes],
            [
                "rough_measure",
                "linework",
                "value_gradient",
                "shadow",
                "highlight",
                "colour_material",
                "texture_detail",
                "measuring_glyphs",
            ],
        )

    def test_measuring_glyphs_comes_after_required_art_layers(self):
        by_name = {art_pass.name: art_pass for art_pass in default_art_passes()}

        self.assertGreater(by_name["measuring_glyphs"].order, by_name["linework"].order)
        self.assertGreater(by_name["measuring_glyphs"].order, by_name["value_gradient"].order)
        self.assertGreater(by_name["measuring_glyphs"].order, by_name["shadow"].order)

    def test_duplicate_pass_names_fail_validation(self):
        passes = default_art_passes()
        passes[1] = ArtPass(
            name="rough_measure",
            order=1,
            input_sources=[],
            output_layer="linework",
        )

        with self.assertRaisesRegex(ValueError, "names must be unique"):
            validate_art_passes(passes)

    def test_duplicate_pass_orders_fail_validation(self):
        passes = default_art_passes()
        passes[1] = ArtPass(
            name="linework",
            order=0,
            input_sources=[],
            output_layer="linework",
        )

        with self.assertRaisesRegex(ValueError, "orders must be unique"):
            validate_art_passes(passes)

    def test_layer_evidence_rejects_mismatched_layer_grid_sizes(self):
        with self.assertRaisesRegex(ValueError, "expected 4"):
            LayerEvidence(
                grid_width=4,
                grid_height=2,
                layers={"linework": ["1234", "123"]},
            )


if __name__ == "__main__":
    unittest.main()
