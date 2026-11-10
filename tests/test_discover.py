import unittest
from datetime import date

from discover import PAGE_SIZE, date_candidates, pagination_complete


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


class DateExtractionTests(unittest.TestCase):
    def test_ticket_full_date_formats(self):
        goods = {"data": [{"activity_time": "2026年11月14日 - 2026年11月15日"}]}
        self.assertEqual(date_candidates(goods), [date(2026, 11, 14), date(2026, 11, 15)])

    def test_chinese_month_day_range_in_project_text(self):
        self.assertEqual(
            date_candidates({}, "活动时间：10月31日—11月1日", reference=date(2026, 11, 10), event_year=2026),
            [date(2026, 10, 31), date(2026, 11, 1)],
        )

    def test_dot_range_in_project_text(self):
        self.assertEqual(
            date_candidates({}, "展期 11.21-11.22", reference=date(2026, 11, 10), event_year=2026),
            [date(2026, 11, 21), date(2026, 11, 22)],
        )

    def test_cross_year_range(self):
        self.assertEqual(
            date_candidates({}, "12月31日-1月2日", reference=date(2026, 11, 10), event_year=2026),
            [date(2026, 12, 31), date(2027, 1, 2)],
        )


if __name__ == "__main__":
    unittest.main()
