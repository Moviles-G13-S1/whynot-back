"""Unit tests for the product-save attempt summary (BQ Type 2)."""

import sys
import unittest
from pathlib import Path


FUNCTIONS_DIR = Path(__file__).resolve().parents[1] / "functions"
sys.path.insert(0, str(FUNCTIONS_DIR))

from analytics.product_save_attempts import (  # noqa: E402
    compute_from_firestore,
    compute_save_attempts,
)


def success(platform="android"):
    return {"platform": platform, "outcome": "success", "reason": None}


def failure(reason, platform="android"):
    return {"platform": platform, "outcome": "failure", "reason": reason}


class SaveAttemptsTest(unittest.TestCase):
    def test_counts_outcomes_and_success_rate(self):
        result = compute_save_attempts([
            success(), success(), success(), failure("invalid_price"),
        ])

        self.assertEqual(result["totalAttempts"], 4)
        self.assertEqual(result["successes"], 3)
        self.assertEqual(result["failures"], 1)
        self.assertEqual(result["successRate"], 75.0)

    def test_splits_by_platform(self):
        result = compute_save_attempts([
            success("android"), failure("backend_error", "ios"), success("ios"),
        ])

        self.assertEqual(
            result["platforms"],
            [
                {"platform": "android", "successes": 1, "failures": 0},
                {"platform": "ios", "successes": 1, "failures": 1},
            ],
        )

    def test_failure_reasons_sorted_by_count_then_name(self):
        result = compute_save_attempts([
            failure("invalid_price"), failure("backend_error"),
            failure("invalid_price"), failure(""),
        ])

        self.assertEqual(
            result["failureReasons"],
            [
                {"reason": "invalid_price", "count": 2},
                {"reason": "backend_error", "count": 1},
                {"reason": "unknown", "count": 1},
            ],
        )

    def test_unknown_outcomes_are_ignored(self):
        result = compute_save_attempts([{"platform": "android", "outcome": "maybe"}])

        self.assertEqual(result["totalAttempts"], 0)

    def test_no_attempts_has_no_success_rate(self):
        result = compute_save_attempts([])

        self.assertIsNone(result["successRate"])
        self.assertEqual(result["failureReasons"], [])


class FakeSnapshot:
    def __init__(self, data):
        self._data = data

    def to_dict(self):
        return self._data


class FakeDb:
    def __init__(self, events):
        self.events = events
        self.read = []

    def collection(self, name):
        self.read.append(name)
        events = self.events

        class Collection:
            def stream(self):
                return [FakeSnapshot(event) for event in events]

        return Collection()


class FirestoreReadTest(unittest.TestCase):
    def test_reads_the_save_events_collection(self):
        db = FakeDb([success(), failure("missing_name")])

        result = compute_from_firestore(db, {})

        self.assertEqual(db.read, ["productSaveEvents"])
        self.assertEqual(result["totalAttempts"], 2)


if __name__ == "__main__":
    unittest.main()
