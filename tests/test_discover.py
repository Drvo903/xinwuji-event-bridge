import unittest

from discover import PAGE_SIZE, pagination_complete


class PaginationTests(unittest.TestCase):
    def test_zero_total_is_unknown_and_does_not_end_scan(self):
        rows = [{} for _ in range(PAGE_SIZE)]
        self.assertFalse(pagination_complete(rows, PAGE_SIZE, 0))
        self.assertFalse(pagination_complete(rows, PAGE_SIZE, None))

    def test_positive_total_ends_when_catalog_is_covered(self):
        rows = [{} for _ in range(PAGE_SIZE)]
        self.assertTrue(pagination_complete(rows, 24, 24))
        self.assertFalse(pagination_complete(rows, 12, 24))

    def test_short_page_is_end_of_catalog(self):
        self.assertTrue(pagination_complete([{}], 1, 0))


if __name__ == "__main__":
    unittest.main()
