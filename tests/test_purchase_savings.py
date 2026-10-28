"""Unit tests for the Sprint 3 BQ: money users saved on purchased products."""

import sys
import unittest
from pathlib import Path


FUNCTIONS_DIR = Path(__file__).resolve().parents[1] / "functions"
sys.path.insert(0, str(FUNCTIONS_DIR))

from analytics.purchase_savings import (  # noqa: E402
    compute_from_firestore,
    compute_purchase_savings,
)


def purchase(reference, paid, user="u1", category="tech", platform="android"):
    return {
        "userId": user,
        "categoryId": category,
        "platform": platform,
        "referencePrice": reference,
        "purchasePrice": paid,
    }


class SavingsTest(unittest.TestCase):
    def test_net_saving_offsets_overpaying(self):
        result = compute_purchase_savings([
            purchase(100, 80),
            purchase(50, 60),
            purchase(30, 30),
        ])

        self.assertEqual(result["purchases"], 3)
        self.assertEqual(result["referenceTotal"], 180)
        self.assertEqual(result["paidTotal"], 170)
        self.assertEqual(result["netSaved"], 10)
        self.assertEqual(result["grossSaved"], 20)
        self.assertEqual(result["overspent"], 10)
        self.assertEqual(
            (result["savedPurchases"], result["samePricePurchases"], result["overpaidPurchases"]),
            (1, 1, 1),
        )

    def test_rates_and_averages(self):
        result = compute_purchase_savings([
            purchase(200, 150, user="a"),
            purchase(100, 50, user="a"),
            purchase(100, 100, user="b"),
        ])

        self.assertEqual(result["buyers"], 2)
        self.assertEqual(result["savingRate"], 25.0)
        self.assertEqual(result["averageSavedPerPurchase"], 33.33)
        self.assertEqual(result["averageSavedPerBuyer"], 50.0)

    def test_categories_sorted_by_saving_with_names(self):
        result = compute_purchase_savings(
            [
                purchase(100, 90, category="beauty"),
                purchase(100, 60, category="tech"),
                purchase(100, 70, category="tech"),
            ],
            categories={"tech": "Technology"},
        )

        self.assertEqual(
            result["byCategory"],
            [
                {"categoryId": "tech", "categoryName": "Technology", "purchases": 2,
                 "netSaved": 70, "savingRate": 35.0},
                {"categoryId": "beauty", "categoryName": "beauty", "purchases": 1,
                 "netSaved": 10, "savingRate": 10.0},
            ],
        )

    def test_platforms_always_listed(self):
        result = compute_purchase_savings([purchase(10, 5, platform="ios")])

        self.assertEqual(
            result["byPlatform"],
            [
                {"platform": "android", "purchases": 0, "netSaved": 0},
                {"platform": "ios", "purchases": 1, "netSaved": 5},
            ],
        )

    def test_invalid_prices_are_skipped(self):
        result = compute_purchase_savings([
            purchase(None, 10),
            purchase(10, -1),
            purchase("10", 5),
            purchase(True, 5),
            purchase(10, 4),
        ])

        self.assertEqual(result["purchases"], 1)
        self.assertEqual(result["skipped"], 4)
        self.assertEqual(result["netSaved"], 6)

    def test_no_purchases_has_no_rates(self):
        result = compute_purchase_savings([])

        self.assertEqual(result["purchases"], 0)
        self.assertEqual(result["netSaved"], 0)
        self.assertIsNone(result["savingRate"])
        self.assertIsNone(result["averageSavedPerPurchase"])
        self.assertIsNone(result["averageSavedPerBuyer"])
        self.assertEqual(result["byCategory"], [])

    def test_decimal_prices_are_rounded_to_cents(self):
        result = compute_purchase_savings([purchase(10.1, 9.9), purchase(0.3, 0.1)])

        self.assertEqual(result["netSaved"], 0.4)


class FakeSnapshot:
    def __init__(self, doc_id, data):
        self.id = doc_id
        self._data = data

    def to_dict(self):
        return self._data


class FakeDb:
    def __init__(self, collections):
        self.collections = collections
        self.read = []

    def collection(self, name):
        self.read.append(name)
        docs = self.collections.get(name, {})

        class Collection:
            def stream(self):
                return [FakeSnapshot(i, d) for i, d in docs.items()]

        return Collection()


class FirestoreReadTest(unittest.TestCase):
    def test_reads_events_and_category_names(self):
        db = FakeDb({
            "productPurchaseEvents": {"p1": purchase(100, 75)},
            "categories": {"tech": {"name": "Tech"}},
        })

        result = compute_from_firestore(db, {})

        self.assertEqual(db.read, ["productPurchaseEvents", "categories"])
        self.assertEqual(result["netSaved"], 25)
        self.assertEqual(result["byCategory"][0]["categoryName"], "Tech")


if __name__ == "__main__":
    unittest.main()
