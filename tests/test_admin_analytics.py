"""Unit tests for the admin-only get_admin_analytics callable."""

import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


FUNCTIONS_DIR = Path(__file__).resolve().parents[1] / "functions"
sys.path.insert(0, str(FUNCTIONS_DIR))

from firebase_functions import https_fn  # noqa: E402

from analytics import endpoint  # noqa: E402


def request(data, token=None, signed_in=True):
    auth = SimpleNamespace(uid="uid-1", token=token or {}) if signed_in else None
    return SimpleNamespace(auth=auth, data=data)


ADMIN = {"admin": True}


class AdminAnalyticsTest(unittest.TestCase):
    def setUp(self):
        self.compute = mock.Mock(return_value={"categories": []})
        self.db = object()

        patch_metrics = mock.patch.dict(
            endpoint.METRICS, {"bq6": self.compute}, clear=True
        )
        patch_client = mock.patch.object(
            endpoint.firestore, "client", return_value=self.db
        )
        patch_metrics.start()
        patch_client.start()
        self.addCleanup(patch_metrics.stop)
        self.addCleanup(patch_client.stop)

    def assert_rejected(self, req, code):
        with self.assertRaises(https_fn.HttpsError) as raised:
            endpoint.get_admin_analytics(req)
        self.assertEqual(raised.exception.code, code)
        self.compute.assert_not_called()

    def test_rejects_signed_out_caller(self):
        self.assert_rejected(
            request({"metric": "bq6"}, signed_in=False),
            https_fn.FunctionsErrorCode.UNAUTHENTICATED,
        )

    def test_rejects_signed_in_non_admin(self):
        for token in ({}, {"admin": False}, {"admin": "true"}):
            with self.subTest(token=token):
                self.assert_rejected(
                    request({"metric": "bq6"}, token=token),
                    https_fn.FunctionsErrorCode.PERMISSION_DENIED,
                )

    def test_rejects_missing_or_unknown_metric(self):
        for data in (None, "bq6", {}, {"metric": 6}, {"metric": "bq99"}):
            with self.subTest(data=data):
                self.assert_rejected(
                    request(data, token=ADMIN),
                    https_fn.FunctionsErrorCode.INVALID_ARGUMENT,
                )

    def test_rejects_params_that_are_not_an_object(self):
        self.assert_rejected(
            request({"metric": "bq6", "params": [1]}, token=ADMIN),
            https_fn.FunctionsErrorCode.INVALID_ARGUMENT,
        )

    def test_admin_gets_bq6_with_envelope(self):
        response = endpoint.get_admin_analytics(
            request({"metric": "bq6", "params": {"x": 1}}, token=ADMIN)
        )

        self.compute.assert_called_once_with(self.db, {"x": 1})
        self.assertEqual(response["metric"], "bq6")
        self.assertEqual(response["data"], {"categories": []})
        self.assertIsInstance(response["generatedAt"], str)
        json.dumps(response)

    def test_params_default_to_empty_object(self):
        endpoint.get_admin_analytics(request({"metric": " bq6 "}, token=ADMIN))

        self.compute.assert_called_once_with(self.db, {})


class RegistryTest(unittest.TestCase):
    def test_bq4_is_registered(self):
        from analytics import bq4_purchases_by_category

        self.assertIs(
            endpoint.METRICS["bq4"],
            bq4_purchases_by_category.compute_from_firestore,
        )

    def test_save_attempts_is_registered(self):
        from analytics import product_save_attempts

        self.assertIs(
            endpoint.METRICS["save_attempts"],
            product_save_attempts.compute_from_firestore,
        )

    def test_bq6_is_registered(self):
        from analytics import bq6_demographics

        self.assertIs(
            endpoint.METRICS["bq6"],
            bq6_demographics.compute_from_firestore,
        )

    def test_dashboard_views_are_registered(self):
        from analytics import dashboard_views

        for name in ("saved", "recommended", "purchased", "demographic"):
            with self.subTest(name=name):
                self.assertIs(
                    endpoint.METRICS[name],
                    getattr(dashboard_views, f"compute_{name}"),
                )

    def test_legacy_dashboard_request_returns_unwrapped_data(self):
        compute = mock.Mock(return_value={"total": 3})
        db = object()
        with mock.patch.dict(endpoint.METRICS, {"recommended": compute}):
            with mock.patch.object(endpoint.firestore, "client", return_value=db):
                result = endpoint.get_admin_analytics(
                    request({"view": "recommended"}, token=ADMIN)
                )

        self.assertEqual(result, {"total": 3})
        compute.assert_called_once_with(db, {})


if __name__ == "__main__":
    unittest.main()
