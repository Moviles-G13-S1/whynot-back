"""Unit tests for the onboarding funnel (BQ Type 2)."""

import sys
import unittest
from pathlib import Path


FUNCTIONS_DIR = Path(__file__).resolve().parents[1] / "functions"
sys.path.insert(0, str(FUNCTIONS_DIR))

from analytics.onboarding import compute_onboarding  # noqa: E402


def sign_up(user_id, platform="android"):
    return {"userId": user_id, "platform": platform, "step": "sign_up_completed"}


def first_wishlist(user_id, platform="android"):
    return {"userId": user_id, "platform": platform, "step": "first_wishlist_created"}


class OnboardingTest(unittest.TestCase):
    def test_funnel_counts_and_rates(self):
        result = compute_onboarding(
            [
                sign_up("a"), sign_up("b"), sign_up("c"), sign_up("d"),
                first_wishlist("a"), first_wishlist("b"),
            ],
            ["a", "a", "c"],
        )

        self.assertEqual(result["signUps"], 4)
        self.assertEqual(result["createdFirstWishlist"], 2)
        self.assertEqual(result["savedFirstProduct"], 2)
        self.assertEqual(result["wishlistRate"], 50.0)
        self.assertEqual(result["productRate"], 50.0)

    def test_ignores_users_without_a_recorded_sign_up(self):
        result = compute_onboarding([first_wishlist("old")], ["old"])

        self.assertEqual(result["signUps"], 0)
        self.assertEqual(result["createdFirstWishlist"], 0)
        self.assertEqual(result["savedFirstProduct"], 0)
        self.assertIsNone(result["wishlistRate"])
        self.assertIsNone(result["productRate"])

    def test_splits_sign_ups_by_platform(self):
        result = compute_onboarding(
            [sign_up("a", "android"), sign_up("b", "ios"), sign_up("c", "ios")],
            [],
        )

        self.assertEqual(
            result["platforms"],
            [
                {"platform": "android", "signUps": 1},
                {"platform": "ios", "signUps": 2},
            ],
        )

    def test_skips_malformed_events(self):
        result = compute_onboarding(
            [{"step": "sign_up_completed"}, {"userId": "a", "step": "other"}],
            [None],
        )

        self.assertEqual(result["signUps"], 0)


if __name__ == "__main__":
    unittest.main()
