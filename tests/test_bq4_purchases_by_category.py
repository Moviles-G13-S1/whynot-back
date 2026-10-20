"""Unit tests for BQ4: top purchased category per month."""

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace


FUNCTIONS_DIR = Path(__file__).resolve().parents[1] / "functions"
sys.path.insert(0, str(FUNCTIONS_DIR))

from analytics.bq4_purchases_by_category import (  # noqa: E402
    compute_from_firestore,
    compute_purchases_by_category,
)


# Bogotá is UTC-5 all year, so noon there is 17:00 UTC.
NOW = datetime(2026, 10, 20, 17, 0, tzinfo=timezone.utc)


def purchased_on(year, month, day=15, category_id="tech"):
    return {
        "categoryId": category_id,
        "purchased": True,
        "purchasedAt": datetime(year, month, day, 17, 0, tzinfo=timezone.utc),
    }


def compute(products, months_window=6, categories=None):
    return compute_purchases_by_category(products, NOW, months_window, categories)


class MonthlyWinnerTest(unittest.TestCase):
    def test_month_reports_its_top_category(self):
        result = compute([
            purchased_on(2026, 10, category_id="tech"),
            purchased_on(2026, 10, category_id="tech"),
            purchased_on(2026, 10, category_id="beauty"),
        ])

        month = result["months"][0]
        self.assertEqual((month["year"], month["month"]), (2026, 10))
        self.assertEqual(month["label"], "Oct 2026")
        self.assertEqual(month["totalPurchases"], 3)
        self.assertEqual(month["topCategoryIds"], ["tech"])
        self.assertEqual(month["topCategoryPurchases"], 2)
        self.assertEqual(
            month["byCategory"],
            [
                {"categoryId": "tech", "categoryName": "tech", "purchases": 2},
                {"categoryId": "beauty", "categoryName": "beauty", "purchases": 1},
            ],
        )

    def test_tie_reports_every_category_sorted(self):
        result = compute([
            purchased_on(2026, 10, category_id="tech"),
            purchased_on(2026, 10, category_id="beauty"),
        ])

        month = result["months"][0]
        self.assertEqual(month["topCategoryIds"], ["beauty", "tech"])
        self.assertEqual(month["topCategoryPurchases"], 1)
        self.assertEqual(
            [entry["categoryId"] for entry in month["byCategory"]],
            ["beauty", "tech"],
        )

    def test_months_are_newest_first_and_empty_months_are_left_out(self):
        result = compute([
            purchased_on(2026, 6),
            purchased_on(2026, 10),
            purchased_on(2026, 8),
        ])

        self.assertEqual(
            [(m["year"], m["month"]) for m in result["months"]],
            [(2026, 10), (2026, 8), (2026, 6)],
        )

    def test_names_come_from_the_category_catalog(self):
        result = compute(
            [purchased_on(2026, 10, category_id="tech")],
            categories={"tech": "Technology"},
        )

        month = result["months"][0]
        self.assertEqual(month["topCategoryNames"], ["Technology"])
        self.assertEqual(month["byCategory"][0]["categoryName"], "Technology")
        self.assertEqual(result["overallTopCategoryNames"], ["Technology"])


class WindowTest(unittest.TestCase):
    def test_window_counts_the_current_month(self):
        # A 6-month window ending in October 2026 starts in May 2026.
        result = compute([
            purchased_on(2026, 5),
            purchased_on(2026, 4),
        ])

        self.assertEqual([m["month"] for m in result["months"]], [5])
        self.assertEqual(result["totalPurchases"], 1)
        self.assertEqual(result["monthsWindow"], 6)

    def test_window_crosses_the_year_boundary(self):
        result = compute(
            [purchased_on(2025, 11), purchased_on(2025, 10)],
            months_window=12,
        )

        self.assertEqual(
            [(m["year"], m["month"]) for m in result["months"]],
            [(2025, 11)],
        )

    def test_invalid_window_is_rejected(self):
        for window in (0, 3, 7, True, "6", None):
            with self.subTest(window=window):
                with self.assertRaises(ValueError):
                    compute([], months_window=window)

    def test_month_uses_bogota_time(self):
        # 03:00 UTC on Oct 1 is still Sep 30 in Bogotá.
        product = purchased_on(2026, 10)
        product["purchasedAt"] = datetime(2026, 10, 1, 3, 0, tzinfo=timezone.utc)

        result = compute([product])

        self.assertEqual(result["months"][0]["month"], 9)


class SelectionTest(unittest.TestCase):
    def test_products_not_purchased_are_ignored(self):
        product = purchased_on(2026, 10)
        product["purchased"] = False

        result = compute([product])

        self.assertEqual(result["months"], [])
        self.assertEqual(result["totalPurchases"], 0)
        self.assertEqual(result["undatedPurchases"], 0)

    def test_purchase_without_date_is_counted_as_undated(self):
        product = purchased_on(2026, 10)
        product["purchasedAt"] = None

        result = compute([product, purchased_on(2026, 10)])

        self.assertEqual(result["undatedPurchases"], 1)
        self.assertEqual(result["totalPurchases"], 1)

    def test_overall_top_uses_the_whole_window_and_keeps_ties(self):
        result = compute([
            purchased_on(2026, 10, category_id="tech"),
            purchased_on(2026, 9, category_id="beauty"),
            purchased_on(2026, 8, category_id="beauty"),
            purchased_on(2026, 7, category_id="tech"),
        ])

        self.assertEqual(result["overallTopCategoryIds"], ["beauty", "tech"])

    def test_no_purchases_gives_an_empty_answer(self):
        self.assertEqual(
            compute([]),
            {
                "months": [],
                "totalPurchases": 0,
                "undatedPurchases": 0,
                "overallTopCategoryIds": [],
                "overallTopCategoryNames": [],
                "monthsWindow": 6,
            },
        )


class FakeSnapshot:
    def __init__(self, doc_id, data):
        self.id = doc_id
        self._data = data

    def to_dict(self):
        return self._data


class FakeDb:
    """Just enough of the Firestore client for compute_from_firestore."""

    def __init__(self, collections):
        self.collections = collections
        self.queries = []

    def collection(self, name):
        db = self
        docs = self.collections.get(name, {})

        class Collection:
            def where(self, field, op, value):
                db.queries.append((name, field, op, value))
                matching = {
                    doc_id: data for doc_id, data in docs.items()
                    if op == "==" and data.get(field) == value
                }
                return SimpleNamespace(stream=lambda: [
                    FakeSnapshot(doc_id, data)
                    for doc_id, data in matching.items()
                ])

            def stream(self):
                return [FakeSnapshot(i, d) for i, d in docs.items()]

        return Collection()


class FirestoreReadTest(unittest.TestCase):
    def test_reads_only_purchased_products_and_category_names(self):
        recent = datetime.now(timezone.utc) - timedelta(days=1)
        db = FakeDb({
            "products": {
                "p1": {"categoryId": "tech", "purchased": True, "purchasedAt": recent},
                "p2": {"categoryId": "beauty", "purchased": False, "purchasedAt": None},
            },
            "categories": {"tech": {"name": "Tech"}},
        })

        result = compute_from_firestore(db, {"months": 12})

        self.assertEqual(db.queries, [("products", "purchased", "==", True)])
        self.assertEqual(result["monthsWindow"], 12)
        self.assertEqual(result["totalPurchases"], 1)
        self.assertEqual(result["overallTopCategoryNames"], ["Tech"])

    def test_window_defaults_to_six_months(self):
        result = compute_from_firestore(FakeDb({}), {})

        self.assertEqual(result["monthsWindow"], 6)

    def test_invalid_window_is_an_invalid_argument(self):
        from firebase_functions import https_fn

        db = FakeDb({})
        with self.assertRaises(https_fn.HttpsError) as raised:
            compute_from_firestore(db, {"months": 3})

        self.assertEqual(
            raised.exception.code,
            https_fn.FunctionsErrorCode.INVALID_ARGUMENT,
        )
        self.assertEqual(db.queries, [])


if __name__ == "__main__":
    unittest.main()
