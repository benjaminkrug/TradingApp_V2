import unittest

from app.signals.scanner import STATIC_UNIVERSE, scan


class TestScanner(unittest.TestCase):
    def test_scan_returns_the_static_universe(self):
        self.assertEqual(scan(), STATIC_UNIVERSE)

    def test_returns_a_copy_not_the_original_list(self):
        result = scan()
        result.append("ZZZZ")
        self.assertNotIn("ZZZZ", STATIC_UNIVERSE)

    def test_no_duplicate_symbols(self):
        self.assertEqual(len(STATIC_UNIVERSE), len(set(STATIC_UNIVERSE)))

    def test_roughly_thirty_symbols_per_decisions_md(self):
        self.assertTrue(25 <= len(STATIC_UNIVERSE) <= 35)


if __name__ == "__main__":
    unittest.main()
