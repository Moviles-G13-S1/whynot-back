import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "functions"))
from analytics import recommendation_home_opens as metric
from analytics.endpoint import METRICS
from analytics import endpoint
from firebase_functions import https_fn


class RecommendationHomeOpensTest(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 26, tzinfo=timezone.utc)
        self.id = "a" * 32

    def event(self, kind, impression=None, **changes):
        impression = impression or self.id
        suffix = "display" if kind == "card_displayed" else "open"
        data = {"platform": "flutter", "userId": "user", "recommendationEventId": "rec",
                "impressionId": impression, "eventType": kind,
                "createdAt": self.now - timedelta(days=1)}
        data.update(changes)
        return f"{impression}_{suffix}", data

    def test_pairs_distinct_valid_events(self):
        events = [self.event("card_displayed"), self.event("card_displayed"),
                  self.event("detail_opened"), self.event("detail_opened"),
                  self.event("detail_opened", "b" * 32)]
        result = metric.summarize(events, self.now)
        self.assertEqual((result["numerator"], result["denominator"], result["percentage"]), (1, 1, 100))

    def test_rejects_direct_visits_mismatch_and_out_of_window(self):
        events = [self.event("card_displayed"),
                  self.event("detail_opened", userId="other"),
                  self.event("detail_opened", "b" * 32),
                  self.event("card_displayed", "c" * 32, createdAt=self.now - timedelta(days=31)),
                  self.event("card_displayed", "d" * 32, platform="android"),
                  self.event("card_displayed", "e" * 32, createdAt="invalid")]
        result = metric.summarize(events, self.now)
        self.assertEqual((result["numerator"], result["denominator"]), (0, 1))

    def test_open_before_display_does_not_pair(self):
        events = [self.event("card_displayed"),
                  self.event("detail_opened", createdAt=self.now - timedelta(days=2))]
        self.assertEqual(metric.summarize(events, self.now)["numerator"], 0)

    def test_no_displays_is_no_data_and_registered(self):
        result = metric.summarize([self.event("detail_opened")], self.now)
        self.assertEqual(result["denominator"], 0)
        self.assertIsNone(result["percentage"])
        self.assertIs(METRICS["recommendation_home_opens"], metric.compute_from_firestore)

    def test_callable_requires_admin_for_home_metric(self):
        payload = {"metric": "recommendation_home_opens"}
        for auth, code in ((None, https_fn.FunctionsErrorCode.UNAUTHENTICATED),
                           (SimpleNamespace(token={"admin": False}), https_fn.FunctionsErrorCode.PERMISSION_DENIED)):
            with self.subTest(auth=auth), self.assertRaises(https_fn.HttpsError) as raised:
                endpoint.get_admin_analytics(SimpleNamespace(auth=auth, data=payload))
            self.assertEqual(raised.exception.code, code)
        database = mock.Mock()
        database.collection.return_value.stream.return_value = []
        with mock.patch.object(endpoint.firestore, "client", return_value=database):
            result = endpoint.get_admin_analytics(SimpleNamespace(
                auth=SimpleNamespace(token={"admin": True}), data=payload))
        self.assertEqual(result["data"]["denominator"], 0)
