import sys
import unittest
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "functions"))
from analytics.home_activation import summarize_home_activation, compute_from_firestore


def event(name="home_empty_state_clicked", user="a", **overrides):
    return {"eventName": name, "userId": user, "source": "home_empty_state", "platform": "android", **overrides}


class HomeActivationTest(unittest.TestCase):
    def test_empty_counts(self):
        result = summarize_home_activation([])
        self.assertEqual([e["count"] for e in result["events"]], [0, 0, 0])

    def test_counts_interactions_and_distinct_users_separately(self):
        result = summarize_home_activation([event(), event(), event(user="b")])
        self.assertEqual(result["events"][1], {"eventName": "home_empty_state_clicked", "count": 3, "distinctUsers": 2})

    def test_all_three_interactions(self):
        events = [event(n) for n in ("home_empty_state_viewed", "home_empty_state_clicked", "add_product_navigation")]
        self.assertEqual([e["count"] for e in summarize_home_activation(events)["events"]], [1, 1, 1])

    def test_ignores_invalid_records(self):
        records = [event("unknown"), event(user=""), event(platform="ios"), event(source="unknown"), {}]
        self.assertEqual([e["count"] for e in summarize_home_activation(records)["events"]], [0, 0, 0])

    def test_reads_only_ux_events(self):
        db = Mock()
        db.collection.return_value.stream.return_value = [Mock(to_dict=Mock(return_value=event()))]
        result = compute_from_firestore(db, {})
        db.collection.assert_called_once_with("uxEvents")
        self.assertEqual(result["events"][1]["count"], 1)
