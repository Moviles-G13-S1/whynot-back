import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "functions" / "analytics"))
from unpurchased_over_30_days import count_unpurchased, compute_from_firestore


class UnpurchasedTests(unittest.TestCase):
    now = datetime(2026, 11, 26, 12, tzinfo=timezone.utc)
    boundary = now - timedelta(days=30)

    def test_strict_age_and_current_purchase_state(self):
        old = self.boundary - timedelta(microseconds=1)
        for created, flag, expected in [
            (old, False, 1), (old.astimezone(timezone(timedelta(hours=-5))), False, 1),
            (self.boundary, False, 0), (self.now, False, 0), (old, True, 0),
            (None, False, 0), (old.replace(tzinfo=None), False, 0),
            (old, None, 0), (old, 0, 0), ("yesterday", False, 0),
        ]:
            with self.subTest(created=created, flag=flag):
                self.assertEqual(count_unpurchased([dict(createdAt=created, purchased=flag)], self.now), expected)

    def test_counts_documents_individually(self):
        product = {"purchased": False, "createdAt": self.now - timedelta(days=31)}
        self.assertEqual(count_unpurchased([product, product, {}], self.now), 2)
        self.assertEqual(count_unpurchased([], self.now), 0)

    def test_firestore_adapter(self):
        db = Mock()
        projection = db.collection.return_value.where.return_value.select
        projection.return_value.stream.return_value = []
        result = compute_from_firestore(db, {})
        db.collection.assert_called_once_with("products")
        db.collection.return_value.where.assert_called_once_with("purchased", "==", False)
        self.assertEqual(result["count"], 0)
        self.assertIsNotNone(datetime.fromisoformat(result["cutoffUtc"]).tzinfo)
