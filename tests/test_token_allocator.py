import unittest

from glyph_lab.token_allocator import allocate_token, token_pool


class TokenAllocatorTests(unittest.TestCase):
    def test_allocator_skips_used_tokens(self):
        self.assertEqual(allocate_token({"A", "B"}), "C")

    def test_allocator_never_returns_space(self):
        token = allocate_token(set())

        self.assertNotEqual(token, " ")
        self.assertNotIn(" ", token_pool())


if __name__ == "__main__":
    unittest.main()
