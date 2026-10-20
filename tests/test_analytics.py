"""Regression tests for backend analytics and the callable's admin gate."""

import sys
import types
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "functions"))
from analytics import (  # noqa: E402
    demographic_summary,
    get_admin_analytics,
    purchased_summary,
    recommended_summary,
    saved_summary,
)


class AnalyticsCalculationTest(unittest.TestCase):
    def test_saved_products_matches_active_user_distribution(self):
        products = [(f"p{i}", {"ownerId": "a"}) for i in range(6)] + [("p7", {"ownerId": "b"})]
        result = saved_summary(products, [("a", {}), ("b", {}), ("c", {})])
        self.assertEqual(result["distributionCounts"], [1, 1, 0, 0, 0])
        self.assertEqual((result["activeUsers"], result["zeroProductUsers"]), (2, 1))
        self.assertEqual((result["singleProductUsers"], result["multipleProductUsers"]), (1, 1))
        self.assertEqual(result["averagePerActiveUser"], 3.5)

    def test_bq3_uses_successful_events_even_if_product_was_deleted(self):
        events = [
            ("saved", {"eventType": "recommendation_shown", "savedAt": datetime.now(timezone.utc), "savedProductId": "deleted-product"}),
            ("shown", {"eventType": "recommendation_shown", "savedAt": None}),
            ("partial", {"eventType": "recommendation_shown", "savedAt": datetime.now(timezone.utc)}),
            ("other", {"eventType": "manual_save", "savedAt": datetime.now(timezone.utc), "savedProductId": "p"}),
        ]
        self.assertEqual(recommended_summary(events), {"total": 1})

    def test_purchase_month_uses_bogota_and_ignores_unpurchased(self):
        products = [
            ("one", {"categoryId": "fashion", "purchased": True, "purchasedAt": datetime(2026, 10, 1, 2, 0, tzinfo=timezone.utc)}),
            ("two", {"categoryId": "fashion", "purchased": False, "purchasedAt": datetime(2026, 10, 2, tzinfo=timezone.utc)}),
        ]
        result = purchased_summary(products, datetime(2026, 10, 20), 6)
        self.assertEqual(result["months"][-2:], ["2026-09", "2026-10"])
        self.assertEqual(result["monthlyTotals"][-2:], [1, 0])

    def test_demographics_counts_unique_owners_and_unknown_cities(self):
        products = [("p1", {"ownerId": "a", "categoryId": "fashion"}), ("p2", {"ownerId": "a", "categoryId": "fashion"}), ("p3", {"ownerId": "b", "categoryId": "fashion"})]
        users = [("a", {"age": 20, "gender": "Female", "cityId": "bogota"}), ("b", {"age": 30, "gender": "Male", "cityId": None})]
        result = demographic_summary("fashion", products, users, [("bogota", {"name": "Bogotá"})])
        self.assertEqual(result["userCount"], 2)
        self.assertEqual(result["medianAge"], "25")
        self.assertEqual(result["cities"][0]["label"], "Bogotá")
        self.assertEqual(result["cities"][-1]["count"], 1)

    def test_callable_rejects_non_admin_before_any_database_access(self):
        class HttpsError(Exception):
            def __init__(self, code, message):
                self.code = code
                super().__init__(message)
        codes = types.SimpleNamespace(UNAUTHENTICATED="unauthenticated", PERMISSION_DENIED="permission-denied")
        fake_https = types.SimpleNamespace(HttpsError=HttpsError, FunctionsErrorCode=codes)
        database = types.SimpleNamespace(client=lambda: self.fail("Database was accessed"))
        with patch.dict(sys.modules, {"firebase_admin": types.SimpleNamespace(firestore=database), "firebase_functions": types.SimpleNamespace(https_fn=fake_https)}):
            for auth, expected in [(None, "unauthenticated"), (types.SimpleNamespace(token={"admin": False}), "permission-denied")]:
                with self.subTest(expected=expected), self.assertRaises(HttpsError) as caught:
                    get_admin_analytics(types.SimpleNamespace(auth=auth, data={"view": "saved"}))
                self.assertEqual(caught.exception.code, expected)


if __name__ == "__main__":
    unittest.main()
