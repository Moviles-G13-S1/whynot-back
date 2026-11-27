"""Unit tests for Sprint 4 errors vs. saved products BQ."""

import sys
import unittest

from datetime import datetime, timedelta, timezone
from pathlib import Path


FUNCTIONS_DIR = Path(__file__).resolve().parents[1] / "functions"
sys.path.insert(0, str(FUNCTIONS_DIR))

from analytics.errors_vs_saved_products import (
    compute_errors_vs_saved_products,
)


NOW = datetime(2026, 11, 26, 18, tzinfo=timezone.utc)
OLD = NOW - timedelta(days=100)


def user(user_id):
    return user_id, {
        "createdAt": OLD,
    }


def product(product_id, owner_id, created_at=NOW):
    return product_id, {
        "ownerId": owner_id,
        "createdAt": created_at,
    }


def error(identifier, user_id, occurred_at=NOW, **changes):
    document_id = f"{identifier:032x}"

    data = {
        "eventId": document_id,
        "schemaVersion": 1,
        "userId": user_id,
        "platform": "ios",
        "feature": "profile",
        "operation": "load_profile",
        "code": "network",
        "source": "operation",
        "occurredAt": occurred_at,
        "createdAt": NOW,
    }

    data.update(changes)

    return document_id, data


def calculate(users=None, errors=None, products=None):
    return compute_errors_vs_saved_products(
        users=users or [],
        errors=errors or [],
        products=products or [],
        now=NOW,
        weeks=8,
    )


class ErrorsVsSavedProductsTest(unittest.TestCase):

    def test_negative_correlation(self):
        result = calculate(
            users=[
                user("u1"),
                user("u2"),
                user("u3"),
            ],
            errors=[
                error(1, "u2"),
                error(2, "u3"),
                error(3, "u3"),
            ],
            products=[
                product("p1", "u1"),
                product("p2", "u1"),
                product("p3", "u2"),
            ],
        )

        self.assertEqual(result["status"], "available")
        self.assertEqual(result["correlation"], -1.0)
        self.assertEqual(result["userCount"], 3)
        self.assertEqual(result["totalErrors"], 3)
        self.assertEqual(result["totalProducts"], 3)

    def test_positive_correlation(self):
        result = calculate(
            users=[
                user("u1"),
                user("u2"),
                user("u3"),
            ],
            errors=[
                error(1, "u2"),
                error(2, "u3"),
                error(3, "u3"),
            ],
            products=[
                product("p1", "u2"),
                product("p2", "u3"),
                product("p3", "u3"),
            ],
        )

        self.assertEqual(result["correlation"], 1.0)

    def test_no_linear_correlation(self):
        result = calculate(
            users=[
                user("u1"),
                user("u2"),
                user("u3"),
            ],
            errors=[
                error(1, "u2"),
                error(2, "u3"),
                error(3, "u3"),
            ],
            products=[
                product("p1", "u1"),
                product("p2", "u3"),
            ],
        )

        self.assertEqual(result["status"], "available")
        self.assertEqual(result["correlation"], 0.0)

    def test_users_with_zero_records_are_included(self):
        result = calculate(
            users=[
                user("u1"),
                user("u2"),
            ],
            errors=[
                error(1, "u1"),
            ],
            products=[
                product("p1", "u1"),
            ],
        )

        self.assertEqual(result["userCount"], 2)
        self.assertEqual(result["usersWithoutErrors"], 1)
        self.assertEqual(result["usersWithoutProducts"], 1)

        self.assertIn(
            {"errors": 0, "products": 0},
            result["points"],
        )

    def test_empty_database(self):
        result = calculate()

        self.assertEqual(result["status"], "empty")
        self.assertEqual(result["userCount"], 0)
        self.assertIsNone(result["correlation"])
        self.assertEqual(result["points"], [])

    def test_single_user(self):
        result = calculate(
            users=[user("u1")],
            errors=[error(1, "u1")],
            products=[product("p1", "u1")],
        )

        self.assertEqual(
            result["status"],
            "insufficient_variation",
        )

        self.assertIsNone(result["correlation"])

    def test_constant_error_counts(self):
        result = calculate(
            users=[
                user("u1"),
                user("u2"),
            ],
            products=[
                product("p1", "u1"),
            ],
        )

        self.assertEqual(result["totalErrors"], 0)
        self.assertIsNone(result["correlation"])

    def test_constant_product_counts(self):
        result = calculate(
            users=[
                user("u1"),
                user("u2"),
            ],
            errors=[
                error(1, "u1"),
            ],
        )

        self.assertEqual(result["totalProducts"], 0)
        self.assertIsNone(result["correlation"])

    def test_duplicate_records_count_once(self):
        result = calculate(
            users=[user("u1")],
            errors=[
                error(1, "u1"),
                error(1, "u1"),
            ],
            products=[
                product("p1", "u1"),
                product("p1", "u1"),
            ],
        )

        self.assertEqual(result["totalErrors"], 1)
        self.assertEqual(result["totalProducts"], 1)

    def test_records_outside_period_are_excluded(self):
        result = calculate(
            users=[user("u1")],
            errors=[
                error(1, "u1", OLD),
                error(2, "u1", NOW),
            ],
            products=[
                product("p1", "u1", OLD),
                product("p2", "u1", NOW),
            ],
        )

        self.assertEqual(result["totalErrors"], 1)
        self.assertEqual(result["totalProducts"], 1)

    def test_future_records_are_excluded(self):
        future = NOW + timedelta(days=1)

        result = calculate(
            users=[user("u1")],
            errors=[
                error(1, "u1", future),
            ],
            products=[
                product("p1", "u1", future),
            ],
        )

        self.assertEqual(result["totalErrors"], 0)
        self.assertEqual(result["totalProducts"], 0)

    def test_invalid_records_are_ignored(self):
        result = calculate(
            users=[user("u1")],
            errors=[
                error(1, "u1", code="invalid"),
                error(2, "u1", schemaVersion=True),
                error(3, "u1"),
            ],
            products=[
                ("p1", {"ownerId": "u1"}),
                product("p2", "u1"),
            ],
        )

        self.assertEqual(result["totalErrors"], 1)
        self.assertEqual(result["totalProducts"], 1)
        self.assertEqual(result["ignoredInvalidErrors"], 2)
        self.assertEqual(result["ignoredInvalidProducts"], 1)

    def test_unknown_users_are_excluded(self):
        result = calculate(
            users=[user("u1")],
            errors=[
                error(1, "unknown"),
            ],
            products=[
                product("p1", "unknown"),
            ],
        )

        self.assertEqual(result["totalErrors"], 0)
        self.assertEqual(result["totalProducts"], 0)

    def test_average_counts(self):
        result = calculate(
            users=[
                user("u1"),
                user("u2"),
            ],
            errors=[
                error(1, "u1"),
                error(2, "u1"),
            ],
            products=[
                product("p1", "u1"),
                product("p2", "u1"),
                product("p3", "u2"),
            ],
        )

        self.assertEqual(
            result["averageErrorsPerUser"], 1.0
        )

        self.assertEqual(
            result["averageProductsPerUser"], 1.5
        )

    def test_user_ids_are_not_exposed(self):
        result = calculate(
            users=[user("private-user-id")],
            errors=[error(1, "private-user-id")],
            products=[product("p1", "private-user-id")],
        )

        self.assertNotIn("private-user-id", str(result))


if __name__ == "__main__":
    unittest.main()