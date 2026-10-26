"""Unit tests for the Sprint 3 buying-patterns BQ."""

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path


FUNCTIONS_DIR = Path(__file__).resolve().parents[1] / "functions"
sys.path.insert(0, str(FUNCTIONS_DIR))

from analytics.buying_patterns import compute_buying_patterns  # noqa: E402


# Bogotá is UTC-5 all year, so noon there is 17:00 UTC. 2026-10-20 is a Tuesday.
NOW = datetime(2026, 10, 20, 17, 0, tzinfo=timezone.utc)


def utc(year, month, day, hour=17, minute=0):
    return datetime(year, month, day, hour, minute, tzinfo=timezone.utc)


def product(owner="u1", category="tech", brand="Sony", price=100.0,
            created=None, purchased_at=None, purchased=None):
    data = {"ownerId": owner, "categoryId": category, "brand": brand, "price": price}
    if created is not None:
        data["createdAt"] = created
    data["purchased"] = purchased if purchased is not None else purchased_at is not None
    if purchased_at is not None:
        data["purchasedAt"] = purchased_at
    return data


def compute(products, months_window=6, categories=None):
    return compute_buying_patterns(products, NOW, months_window, categories)


class WindowTest(unittest.TestCase):
    def test_only_purchases_inside_the_window_count(self):
        result = compute([
            product(purchased_at=utc(2026, 10, 1)),
            product(purchased_at=utc(2026, 5, 1)),
            product(purchased_at=utc(2026, 4, 30)),  # outside the 6-month window
        ])

        self.assertEqual(result["totalPurchases"], 2)
        self.assertEqual(result["monthsWindow"], 6)

    def test_a_longer_window_includes_older_purchases(self):
        result = compute([product(purchased_at=utc(2026, 4, 30))], months_window=12)

        self.assertEqual(result["totalPurchases"], 1)

    def test_rejects_unknown_windows(self):
        with self.assertRaises(ValueError):
            compute([], months_window=3)

    def test_undated_purchases_are_counted_apart(self):
        result = compute([product(purchased=True), product(purchased_at=utc(2026, 10, 1))])

        self.assertEqual(result["undatedPurchases"], 1)
        self.assertEqual(result["totalPurchases"], 1)


class ConversionTest(unittest.TestCase):
    def test_overall_and_per_category_conversion(self):
        result = compute(
            [
                product(category="tech", created=utc(2026, 9, 1), purchased_at=utc(2026, 9, 5)),
                product(category="tech", created=utc(2026, 9, 2)),
                product(category="beauty", created=utc(2026, 9, 3), purchased_at=utc(2026, 9, 4)),
                product(category="home", created=utc(2026, 9, 3)),
                product(category="home", created=utc(2026, 9, 4)),
                product(category="tech", created=utc(2025, 1, 1)),  # saved outside the window
            ],
            categories={"tech": "Technology"},
        )

        conversion = result["conversion"]
        self.assertEqual(conversion["savedInWindow"], 5)
        self.assertEqual(conversion["purchasedOfThose"], 2)
        self.assertEqual(conversion["rate"], 0.4)
        self.assertEqual(
            [(c["categoryId"], c["saved"], c["purchased"], c["rate"]) for c in conversion["byCategory"]],
            [("beauty", 1, 1, 1.0), ("tech", 2, 1, 0.5), ("home", 2, 0, 0.0)],
        )
        self.assertEqual(conversion["byCategory"][1]["categoryName"], "Technology")

    def test_rate_is_null_when_nothing_was_saved(self):
        result = compute([product(purchased_at=utc(2026, 10, 1))])

        self.assertEqual(result["conversion"]["savedInWindow"], 0)
        self.assertIsNone(result["conversion"]["rate"])


class TimeToPurchaseTest(unittest.TestCase):
    def test_buckets_median_and_skipped_negative_gaps(self):
        bought = utc(2026, 10, 10)
        result = compute([
            product(created=bought - timedelta(hours=5), purchased_at=bought),   # same day
            product(created=bought - timedelta(days=3), purchased_at=bought),    # 1-7
            product(created=bought - timedelta(days=10), purchased_at=bought),   # 8-30
            product(created=bought - timedelta(days=45), purchased_at=bought),   # over 30
            product(created=bought + timedelta(days=1), purchased_at=bought),    # negative
        ])

        time = result["timeToPurchase"]
        self.assertEqual(
            time["buckets"],
            {"sameDay": 1, "oneToSevenDays": 1, "eightToThirtyDays": 1, "overThirtyDays": 1},
        )
        self.assertEqual(time["skipped"], 1)
        self.assertEqual(time["measured"], 4)
        # Even count: median of 0.2, 3, 10, 45 days is (3 + 10) / 2.
        self.assertEqual(time["medianDays"], 6.5)

    def test_per_category_median(self):
        bought = utc(2026, 10, 10)
        result = compute([
            product(category="tech", created=bought - timedelta(days=2), purchased_at=bought),
            product(category="tech", created=bought - timedelta(days=4), purchased_at=bought),
        ])

        self.assertEqual(
            result["timeToPurchase"]["byCategory"],
            [{"categoryId": "tech", "categoryName": "tech", "medianDays": 3.0, "count": 2}],
        )


class WhenTheyBuyTest(unittest.TestCase):
    def test_weekday_and_time_of_day_use_bogota_time(self):
        # 03:00 UTC on Tuesday the 20th is 22:00 on Monday the 19th in Bogotá.
        result = compute([
            product(purchased_at=utc(2026, 10, 20, 3)),
            product(purchased_at=utc(2026, 10, 20, 14)),  # 09:00 Tuesday, morning
        ])

        when = result["whenTheyBuy"]
        weekdays = {item["weekday"]: item["purchases"] for item in when["byWeekday"]}
        times = {item["timeOfDay"]: item["purchases"] for item in when["byTimeOfDay"]}
        self.assertEqual(weekdays["Mon"], 1)
        self.assertEqual(weekdays["Tue"], 1)
        self.assertEqual(times, {"morning": 1, "afternoon": 0, "night": 1})

    def test_ties_list_every_peak(self):
        result = compute([
            product(purchased_at=utc(2026, 10, 19, 17)),  # Monday afternoon
            product(purchased_at=utc(2026, 10, 20, 14)),  # Tuesday morning
        ])

        when = result["whenTheyBuy"]
        self.assertEqual(when["peakWeekday"], ["Mon", "Tue"])
        self.assertEqual(when["peakTimeOfDay"], ["afternoon", "morning"])


class SpendingTest(unittest.TestCase):
    def test_prices_ignore_bad_values(self):
        bought = utc(2026, 10, 10)
        result = compute([
            product(price=100, purchased_at=bought),
            product(price=300, purchased_at=bought),
            product(price=-5, purchased_at=bought),
            product(price="expensive", purchased_at=bought),
        ])

        tech = result["spending"]["byCategory"][0]
        self.assertEqual(tech["purchases"], 4)
        self.assertEqual(tech["medianPrice"], 200.0)
        self.assertEqual(tech["averagePrice"], 200.0)

    def test_brands_group_case_insensitively(self):
        bought = utc(2026, 10, 10)
        result = compute([
            product(brand="Sony", purchased_at=bought),
            product(brand=" sony ", purchased_at=bought),
            product(brand="Sony", purchased_at=bought),
            product(brand="Apple", purchased_at=bought),
            product(brand="  ", purchased_at=bought),
        ])

        self.assertEqual(
            result["spending"]["topBrands"],
            [{"brand": "Sony", "purchases": 3}, {"brand": "Apple", "purchases": 1}],
        )


class RepeatBuyersTest(unittest.TestCase):
    def test_buckets_buyers_by_purchase_count(self):
        bought = utc(2026, 10, 10)
        purchases = (
            [product(owner="one", purchased_at=bought)]
            + [product(owner="two", purchased_at=bought)] * 2
            + [product(owner="four", purchased_at=bought)] * 4
        )

        repeat = compute(purchases)["repeatBuyers"]

        self.assertEqual(repeat["buyers"], 3)
        self.assertEqual(repeat["onePurchase"], 1)
        self.assertEqual(repeat["twoToThree"], 1)
        self.assertEqual(repeat["fourOrMore"], 1)
        self.assertEqual(repeat["repeatRate"], 0.6667)


class EmptyInputTest(unittest.TestCase):
    def test_empty_input_returns_zeros_and_nulls(self):
        result = compute([])

        self.assertEqual(result["totalPurchases"], 0)
        self.assertIsNone(result["conversion"]["rate"])
        self.assertIsNone(result["timeToPurchase"]["medianDays"])
        self.assertEqual(result["whenTheyBuy"]["peakWeekday"], [])
        self.assertEqual(result["spending"]["topBrands"], [])
        self.assertIsNone(result["repeatBuyers"]["repeatRate"])


if __name__ == "__main__":
    unittest.main()
