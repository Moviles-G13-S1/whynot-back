"""Presence-only metric and its shared callable integration (no live writes)."""
import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "functions"))
from analytics import endpoint
from analytics.product_completeness import compute_from_firestore, compute_product_completeness
from firebase_functions import https_fn


class ProductCompletenessTests(unittest.TestCase):
    def test_union_does_not_double_count_missing_both(self):
        result = compute_product_completeness(iter([
            {"imageUrl": "image", "productUrl": "link"},
            {"imageUrl": "", "productUrl": "link"},
            {"imageUrl": "image", "productUrl": ""},
            {},
        ]))
        self.assertEqual(result, {
            "totalProducts": 4,
            "missingImageCount": 2, "missingImagePercentage": 50.0,
            "missingProductUrlCount": 2, "missingProductUrlPercentage": 50.0,
            "missingBothCount": 1, "incompleteCount": 3,
            "incompletePercentage": 75.0,
        })

    def test_missing_values_and_wrong_types(self):
        for value in (None, "", " \t\n", 0, False, [], {}):
            with self.subTest(value=value):
                result = compute_product_completeness([{"imageUrl": value, "productUrl": value}])
                self.assertEqual(result["missingBothCount"], 1)
                self.assertEqual(result["incompletePercentage"], 100.0)

    def test_nonempty_text_counts_without_url_validation_including_purchased(self):
        result = compute_product_completeness([
            {"imageUrl": " not a URL ", "productUrl": " unreachable ", "purchased": True},
            {"imageUrl": "x", "productUrl": "y", "purchased": False},
        ])
        self.assertEqual(result["totalProducts"], 2)
        self.assertEqual(result["incompletePercentage"], 0.0)

    def test_empty_and_fractional_percentages(self):
        empty = compute_product_completeness([])
        for key, value in empty.items():
            self.assertEqual(value, None if key.endswith("Percentage") else 0)
        result = compute_product_completeness([{}, {"imageUrl": "x", "productUrl": "y"}, {"imageUrl": "x", "productUrl": "y"}])
        self.assertAlmostEqual(result["incompletePercentage"], 100 / 3)
        json.dumps(empty, allow_nan=False)

    def test_firestore_projection_and_empty_documents(self):
        db = Mock()
        db.collection.return_value.select.return_value.stream.return_value = [
            Mock(to_dict=Mock(return_value={})), Mock(to_dict=Mock(return_value=None)),
        ]
        result = compute_from_firestore(db, {})
        db.collection.assert_called_once_with("products")
        db.collection.return_value.select.assert_called_once_with(["imageUrl", "productUrl"])
        self.assertEqual(result["missingBothCount"], 2)

    def test_real_registered_callable_returns_envelope(self):
        self.assertIs(endpoint.METRICS["product_completeness"], compute_from_firestore)
        db = Mock()
        db.collection.return_value.select.return_value.stream.return_value = []
        req = SimpleNamespace(auth=SimpleNamespace(token={"admin": True}), data={"metric": "product_completeness"})
        with patch.object(endpoint.firestore, "client", return_value=db):
            response = endpoint.get_admin_analytics(req)
        self.assertEqual(response["metric"], "product_completeness")
        self.assertEqual(response["data"], compute_product_completeness([]))
        json.dumps(response, allow_nan=False)

    def test_rejects_non_admin_before_reading(self):
        for auth in (None, SimpleNamespace(token={}), SimpleNamespace(token={"admin": "true"})):
            req = SimpleNamespace(auth=auth, data={"metric": "product_completeness"})
            with patch.object(endpoint.firestore, "client") as client:
                with self.assertRaises(https_fn.HttpsError):
                    endpoint.get_admin_analytics(req)
                client.assert_not_called()
