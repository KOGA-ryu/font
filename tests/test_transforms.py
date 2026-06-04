import unittest

from glyph_lab.atlas import stamp_for_index
from glyph_lab.transforms import (
    bitmask_to_stamp,
    flip_horizontal,
    rotate_90,
    rotate_180,
    shift,
    stamp_to_bitmask,
)


class TransformTests(unittest.TestCase):
    def test_rotate_90_horizontal_edge_becomes_vertical_edge(self):
        rotated = rotate_90(stamp_for_index(14))

        self.assertEqual(stamp_to_bitmask(rotated), stamp_to_bitmask(stamp_for_index(15)))

    def test_rotate_180_twice_returns_original(self):
        original = stamp_for_index(30)
        transformed = rotate_180(rotate_180(original))

        self.assertEqual(stamp_to_bitmask(transformed), stamp_to_bitmask(original))

    def test_flip_horizontal_twice_returns_original(self):
        original = stamp_for_index(16)
        transformed = flip_horizontal(flip_horizontal(original))

        self.assertEqual(stamp_to_bitmask(transformed), stamp_to_bitmask(original))

    def test_shift_right_then_left_can_clip(self):
        original = stamp_for_index(29)
        transformed = shift(shift(original, 3, 0), -3, 0)

        self.assertNotEqual(stamp_to_bitmask(transformed), stamp_to_bitmask(original))

    def test_stamp_bitmask_roundtrip(self):
        original = stamp_for_index(30)
        bitmask = stamp_to_bitmask(original)
        roundtrip = bitmask_to_stamp(bitmask)

        self.assertEqual(stamp_to_bitmask(roundtrip), bitmask)


if __name__ == "__main__":
    unittest.main()
