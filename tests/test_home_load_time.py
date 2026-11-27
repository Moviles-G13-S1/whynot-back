import os
import sys
import unittest
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "functions"))

from analytics.home_load_time import compute_home_load_time  # noqa: E402

NOW = datetime(2026, 11, 27, 12, 0, tzinfo=timezone.utc)


def load(duration, platform="android", screen="home", days_ago=1):
    return {
        "userId": "u1",
        "screen": screen,
        "durationMs": duration,
        "platform": platform,
        "createdAt": NOW - timedelta(days=days_ago),
    }


class HomeLoadTimeTest(unittest.TestCase):

    def test_average_per_platform_is_the_answer(self):
        result = compute_home_load_time(
            [load(1000), load(3000), load(2000, platform="ios")], now=NOW
        )

        android, ios = result["platforms"]
        self.assertEqual(android["platform"], "android")
        self.assertEqual(android["loads"], 2)
        self.assertEqual(android["averageMs"], 2000.0)
        self.assertEqual(ios["averageMs"], 2000.0)
        self.assertEqual(result["overall"]["loads"], 3)

    def test_median_and_p90_resist_one_very_slow_load(self):
        events = [load(d) for d in (1000, 1100, 1200, 1300, 1400, 1500, 1600, 1700, 1800, 16000)]

        android = compute_home_load_time(events, now=NOW)["platforms"][0]

        self.assertEqual(android["averageMs"], 2860.0)
        self.assertEqual(android["medianMs"], 1450.0)
        self.assertEqual(android["p90Ms"], 1800)
        self.assertEqual(android["slowestMs"], 16000)
        self.assertEqual(android["fastestMs"], 1000)

    def test_a_platform_without_loads_reports_nulls(self):
        result = compute_home_load_time([load(1500)], now=NOW)

        ios = result["platforms"][1]
        self.assertEqual(ios["loads"], 0)
        self.assertIsNone(ios["averageMs"])
        self.assertIsNone(result["fastestPlatform"])

    def test_fastest_platform_when_both_have_loads(self):
        result = compute_home_load_time(
            [load(3000), load(1000, platform="ios")], now=NOW
        )
        self.assertEqual(result["fastestPlatform"], "ios")

    def test_invalid_events_are_ignored(self):
        result = compute_home_load_time(
            [
                load(1000),
                load(0),
                load(-5),
                load(500_000),
                load("1000"),
                load(1000, platform="web"),
                load(1000, screen="search"),
                {"durationMs": 1000},
            ],
            now=NOW,
        )
        self.assertEqual(result["overall"]["loads"], 1)
        self.assertEqual(result["ignoredEvents"], 7)

    def test_days_window_keeps_recent_loads_only(self):
        result = compute_home_load_time(
            [load(1000, days_ago=1), load(9000, days_ago=20)], now=NOW, days=7
        )
        self.assertEqual(result["overall"]["loads"], 1)
        self.assertEqual(result["overall"]["averageMs"], 1000.0)
        self.assertEqual(result["days"], 7)

    def test_days_must_be_7_or_30(self):
        with self.assertRaises(ValueError):
            compute_home_load_time([], now=NOW, days=10)

    def test_no_events(self):
        result = compute_home_load_time([], now=NOW)
        self.assertEqual(result["overall"]["loads"], 0)
        self.assertIsNone(result["overall"]["averageMs"])


if __name__ == "__main__":
    unittest.main()
