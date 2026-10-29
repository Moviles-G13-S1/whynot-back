"""Calendar boundaries, deduplication and shared-callable integration for BQ Type 1."""
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "functions"))
from analytics import endpoint, weekly_app_errors as metric
from firebase_functions import https_fn

NOW = datetime(2026, 10, 28, 17, tzinfo=timezone.utc)


def event(identifier, occurred=NOW, **changes):
    document_id = f"{identifier:032x}"
    data = {"eventId": document_id, "schemaVersion": 1, "userId": "user-1", "platform": "ios",
            "feature": "profile", "operation": "load_profile", "code": "network", "source": "operation",
            "occurredAt": occurred, "createdAt": NOW}
    data.update(changes)
    return document_id, data


class WeeklyErrorsTest(unittest.TestCase):
    def test_empty_result_has_every_zero_week_and_partial_current_week(self):
        result = metric.summarize([], now=NOW)
        self.assertEqual(result["totalErrors"], 0)
        self.assertEqual(len(result["weeks"]), 8)
        self.assertEqual(result["weeks"][-1]["weekStart"], "2026-10-26")
        self.assertTrue(result["weeks"][-1]["partial"])
        self.assertEqual(sum(week["barPercent"] for week in result["weeks"]), 0)

    def test_bogota_sunday_to_monday_boundary_is_not_utc_midnight(self):
        sunday = datetime(2026, 10, 26, 4, 59, 59, tzinfo=timezone.utc)
        monday = datetime(2026, 10, 26, 5, tzinfo=timezone.utc)
        result = metric.summarize([event(1, sunday), event(2, monday)], now=NOW)
        self.assertEqual(result["previousWeekErrors"], 1)
        self.assertEqual(result["currentWeekErrors"], 1)

    def test_year_boundary_uses_calendar_monday(self):
        result = metric.summarize([event(1, datetime(2025, 12, 31, 12, tzinfo=timezone.utc))],
                                  now=datetime(2026, 1, 1, 18, tzinfo=timezone.utc), weeks=4)
        self.assertEqual(result["weeks"][-1]["weekStart"], "2025-12-29")
        self.assertEqual(result["currentWeekErrors"], 1)

    def test_duplicate_delivery_counts_once_but_distinct_attempts_count_separately(self):
        result = metric.summarize([event(1), event(1), event(2)], now=NOW)
        self.assertEqual(result["totalErrors"], 2)

    def test_occurrence_time_not_late_delivery_assigns_week(self):
        occurred = NOW - timedelta(days=9)
        result = metric.summarize([event(1, occurred, createdAt=NOW)], now=NOW)
        self.assertEqual(result["currentWeekErrors"], 0)
        self.assertEqual(result["weeks"][-2]["count"], 1)

    def test_filters_future_outside_window_and_malformed_records(self):
        start, _ = metric.window(NOW, 4)
        events = [event(1, start - timedelta(microseconds=1)), event(2, NOW + timedelta(seconds=1)),
                  event(3, start), event(4, NOW.replace(tzinfo=None)), event(5, feature=[]),
                  event(6, schemaVersion=True), event(7, code="validation"), ("bad", None)]
        result = metric.summarize(events, now=NOW, weeks=4)
        self.assertEqual(result["totalErrors"], 1)
        self.assertEqual(result["ignoredInvalidRecords"], 5)

    def test_breakdowns_and_scaled_bars_are_backend_calculations(self):
        result = metric.summarize([event(1), event(2, platform="web", feature="runtime", source="framework", code="unexpected"),
                                   event(3, NOW - timedelta(days=7))], now=NOW)
        self.assertEqual(result["totalErrors"], 3)
        self.assertEqual(result["weeks"][-1]["barPercent"], 100)
        self.assertEqual(result["weeks"][-2]["barPercent"], 50)
        self.assertEqual(result["byCode"][0], {"key": "network", "count": 2})
        self.assertEqual(sum(item["count"] for item in result["byPlatform"]), 3)

    def test_shared_endpoint_authorization_and_metric_registration(self):
        self.assertIs(endpoint.METRICS["weekly_app_errors"], metric.compute_from_firestore)
        compute = mock.Mock(return_value=metric.summarize([], now=NOW))
        with mock.patch.dict(endpoint.METRICS, {"weekly_app_errors": compute}), mock.patch.object(endpoint.firestore, "client", return_value="db"):
            with self.assertRaises(https_fn.HttpsError):
                endpoint.get_admin_analytics(SimpleNamespace(auth=None, data={"metric": "weekly_app_errors"}))
            compute.assert_not_called()
            result = endpoint.get_admin_analytics(SimpleNamespace(auth=SimpleNamespace(token={"admin": True}),
                data={"metric": "weekly_app_errors", "params": {"weeks": 4}}))
            compute.assert_called_once_with("db", {"weeks": 4})
            self.assertEqual(result["metric"], "weekly_app_errors")

    def test_query_bounds_and_invalid_week_filter(self):
        db = mock.Mock()
        query = db.collection.return_value
        query.where.return_value = query
        document_id, data = event(1, datetime.now(timezone.utc))
        query.stream.return_value = [SimpleNamespace(id=document_id, to_dict=lambda: data)]
        result = metric.compute_from_firestore(db, {"weeks": 4})
        self.assertEqual(result["totalErrors"], 1)
        db.collection.assert_called_once_with("applicationErrorEvents")
        self.assertEqual(query.where.call_count, 2)
        for value in (0, 1, 99, "8", True):
            with self.subTest(value=value), self.assertRaises(https_fn.HttpsError) as error:
                metric.compute_from_firestore(db, {"weeks": value})
            self.assertEqual(error.exception.code, https_fn.FunctionsErrorCode.INVALID_ARGUMENT)


if __name__ == "__main__":
    unittest.main()
