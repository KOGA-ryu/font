import unittest

from glyph_lab.layers import default_layer_order, layer_sort_key, output_layer_order


class LayerTests(unittest.TestCase):
    def test_default_layer_order_is_deterministic(self):
        self.assertEqual(
            default_layer_order(),
            [
                "background",
                "mass",
                "base_fill",
                "shadow",
                "highlight",
                "edge",
                "detail",
                "ornament",
                "measurement",
            ],
        )
        self.assertEqual(sorted(["detail", "base_fill", "edge"], key=layer_sort_key), ["base_fill", "edge", "detail"])
        self.assertNotIn("background", output_layer_order())


if __name__ == "__main__":
    unittest.main()
