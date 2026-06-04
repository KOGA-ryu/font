import unittest

from glyph_lab.contours import extract_contours


class ContourTests(unittest.TestCase):
    def test_rectangle_mask_has_constant_width_profile(self):
        mask = rectangle_mask(8, 8, 2, 5, 1, 6)

        contours = extract_contours(mask)

        self.assertEqual(contours["width_profile_by_row"][1:7], [4, 4, 4, 4, 4, 4])

    def test_boundary_extraction_marks_perimeter_cells(self):
        mask = rectangle_mask(6, 6, 1, 4, 1, 4)

        contours = extract_contours(mask)
        boundary = {tuple(cell) for cell in contours["boundary_cells"]}

        self.assertIn((1, 1), boundary)
        self.assertIn((4, 4), boundary)
        self.assertIn((2, 2), {(x, y) for y, row in enumerate(mask) for x, value in enumerate(row) if value})
        self.assertNotIn((2, 2), boundary)


def rectangle_mask(width: int, height: int, left: int, right: int, top: int, bottom: int):
    return [[left <= x <= right and top <= y <= bottom for x in range(width)] for y in range(height)]


if __name__ == "__main__":
    unittest.main()
