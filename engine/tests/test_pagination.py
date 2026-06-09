"""Unit tests for the uniform list pagination + sorting helpers."""

import unittest

from sunday import pagination as P


class TestPaginate(unittest.TestCase):
    def test_window(self):
        r = P.paginate(list(range(120)), 2, 50)
        self.assertEqual(r["items"][0], 50)
        self.assertEqual(r["items"][-1], 99)
        self.assertEqual(r["total"], 120)
        self.assertTrue(r["has_more"])

    def test_last_page(self):
        r = P.paginate(list(range(120)), 3, 50)
        self.assertEqual(len(r["items"]), 20)
        self.assertFalse(r["has_more"])

    def test_clamp_page_and_size(self):
        r = P.paginate(list(range(10)), 0, 9999)
        self.assertEqual(r["page"], 1)
        self.assertEqual(r["page_size"], P.MAX_PAGE_SIZE)

    def test_empty(self):
        r = P.paginate([], 1, 50)
        self.assertEqual(r["total"], 0)
        self.assertFalse(r["has_more"])
        self.assertEqual(r["items"], [])


class TestSort(unittest.TestCase):
    def test_desc_none_sinks(self):
        rows = [{"v": None}, {"v": 5}, {"v": 9}]
        self.assertEqual([r["v"] for r in P.sort_by(rows, "v", "desc")], [9, 5, None])

    def test_asc_none_sinks(self):
        rows = [{"v": None}, {"v": 5}, {"v": 9}]
        self.assertEqual([r["v"] for r in P.sort_by(rows, "v", "asc")], [5, 9, None])

    def test_no_key_is_identity(self):
        rows = [{"v": 3}, {"v": 1}]
        self.assertEqual(P.sort_by(rows, None), rows)


if __name__ == "__main__":
    unittest.main()
