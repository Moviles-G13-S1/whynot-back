"""Unit tests for recommendation profile validation."""

import sys
import unittest
from pathlib import Path


FUNCTIONS_DIR = Path(__file__).resolve().parents[1] / "functions"
sys.path.insert(0, str(FUNCTIONS_DIR))

from recommendation_logic import has_valid_demographics  # noqa: E402


class DemographicProfileValidationTest(unittest.TestCase):
    def test_accepts_complete_profile(self):
        self.assertTrue(
            has_valid_demographics(
                {
                    "gender": "Female",
                    "age": 24,
                    "preferredCategoryId": "fashion",
                }
            )
        )

    def test_rejects_empty_legacy_profile(self):
        self.assertFalse(has_valid_demographics({}))

    def test_rejects_missing_or_invalid_ranking_fields(self):
        profiles = [
            {"age": 24, "preferredCategoryId": "fashion"},
            {"gender": "Female", "preferredCategoryId": "fashion"},
            {"gender": "Female", "age": 24},
            {
                "gender": "Female",
                "age": "24",
                "preferredCategoryId": "fashion",
            },
            {
                "gender": "Female",
                "age": True,
                "preferredCategoryId": "fashion",
            },
        ]

        for profile in profiles:
            with self.subTest(profile=profile):
                self.assertFalse(has_valid_demographics(profile))


if __name__ == "__main__":
    unittest.main()
