import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "functions"))
from analytics.nearby_detail_opens import compute_from_firestore, summarize, window

# Wednesday 2026-11-25 15:00 in Bogota (UTC-5).
NOW = datetime(2026, 11, 25, 20, 0, tzinfo=timezone.utc)


def event(user="a", days_ago=0, platform="android", **overrides):
    return {
        "eventName": "nearby_store_detail_opened",
        "source": "home_nearby_store",
        "platform": platform,
        "userId": user,
        "createdAt": NOW - timedelta(days=days_ago),
        **overrides,
    }


class WindowTest(unittest.TestCase):
    def test_window_starts_on_a_bogota_monday(self):
        start, _ = window(NOW, 4)
        self.assertEqual(start.weekday(), 0)
        self.assertEqual(start.date().isoformat(), "2026-11-02")

    def test_rejects_unsupported_window(self):
        for weeks in (0, 5, "8", 8.0):
            with self.assertRaises(ValueError):
                window(NOW, weeks)

    def test_rejects_naive_now(self):
        with self.assertRaises(ValueError):
            window(datetime(2026, 11, 25), 4)


class SummarizeTest(unittest.TestCase):
    def test_empty_window(self):
        result = summarize([], now=NOW, weeks=4)
        self.assertEqual(result["currentWeekUsers"], 0)
        self.assertEqual([w["distinctUsers"] for w in result["weeks"]], [0, 0, 0, 0])
        self.assertTrue(result["weeks"][-1]["partial"])

    def test_a_user_counts_once_per_week_but_every_open_is_kept(self):
        result = summarize([event("a"), event("a"), event("b")], now=NOW, weeks=4)
        self.assertEqual(result["currentWeekUsers"], 2)
        self.assertEqual(result["weeks"][-1]["opens"], 3)
        self.assertEqual(result["totalOpens"], 3)

    def test_users_are_split_by_calendar_week(self):
        # Monday 23 Nov (this week) and Sunday 22 Nov (previous week).
        events = [event("a", days_ago=2), event("b", days_ago=3)]
        result = summarize(events, now=NOW, weeks=4)
        self.assertEqual(result["currentWeekUsers"], 1)
        self.assertEqual(result["previousWeekUsers"], 1)
        self.assertEqual(result["distinctUsersInWindow"], 2)

    def test_same_user_in_two_weeks_counts_in_each_week_once_in_window(self):
        result = summarize([event("a"), event("a", days_ago=7)], now=NOW, weeks=4)
        self.assertEqual([w["distinctUsers"] for w in result["weeks"]], [0, 0, 1, 1])
        self.assertEqual(result["distinctUsersInWindow"], 1)
        self.assertEqual(result["averageWeeklyUsers"], 0.5)

    def test_events_outside_the_window_are_left_out(self):
        result = summarize([event("old", days_ago=60)], now=NOW, weeks=4)
        self.assertEqual(result["distinctUsersInWindow"], 0)
        self.assertEqual(result["ignoredInvalidRecords"], 0)

    def test_platforms_are_counted_separately(self):
        result = summarize([event("a"), event("b", platform="ios")], now=NOW, weeks=4)
        self.assertEqual(result["byPlatform"], [
            {"platform": "android", "distinctUsers": 1},
            {"platform": "ios", "distinctUsers": 1},
        ])

    def test_invalid_records_are_ignored(self):
        records = [
            event(eventName="home_empty_state_clicked"),
            event(source="home_bottom_bar"),
            event(platform="web"),
            event(user=""),
            event(createdAt="yesterday"),
            event(createdAt=datetime(2026, 11, 25)),
            {},
            None,
        ]
        result = summarize(records, now=NOW, weeks=4)
        self.assertEqual(result["ignoredInvalidRecords"], len(records))
        self.assertEqual(result["totalOpens"], 0)

    def test_bars_are_relative_to_the_busiest_week(self):
        events = [event("a"), event("b"), event("c", days_ago=7)]
        result = summarize(events, now=NOW, weeks=4)
        self.assertEqual([w["barPercent"] for w in result["weeks"]], [0, 0, 50.0, 100.0])


class FirestoreTest(unittest.TestCase):
    def test_reads_only_the_detail_event(self):
        doc = Mock()
        doc.to_dict.return_value = event("a")
        db = Mock()
        db.collection.return_value.where.return_value.stream.return_value = [doc]

        result = compute_from_firestore(db, {"weeks": 4})

        db.collection.assert_called_once_with("uxEvents")
        self.assertEqual(result["windowWeeks"], 4)

    def test_invalid_weeks_is_a_client_error(self):
        from firebase_functions import https_fn

        with self.assertRaises(https_fn.HttpsError):
            compute_from_firestore(Mock(), {"weeks": 3})


if __name__ == "__main__":
    unittest.main()
