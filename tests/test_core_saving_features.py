"""Unit tests for Juliana's Sprint 3 core saving features BQ."""

import hashlib
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock


FUNCTIONS_DIR = Path(__file__).resolve().parents[1] / "functions"
sys.path.insert(0, str(FUNCTIONS_DIR))

from analytics.core_saving_features import (  # noqa: E402
    compute_core_saving_features,
    compute_from_firestore,
)


SAVED_AT = datetime(2026, 10, 27, tzinfo=timezone.utc)


def recommendation_id(user, source):
    digest = hashlib.sha256(f"{user}:{source}".encode()).hexdigest()
    return f"rec_{digest}"


def saved_event(user, source):
    return {
        "eventType": "recommendation_shown",
        "userId": user,
        "sourceProductId": source,
        "savedProductId": recommendation_id(user, source),
        "savedAt": SAVED_AT,
    }


def calculate(wishlists=None, products=None, events=None):
    return compute_core_saving_features(
        wishlists or [],
        products or [],
        events or [],
    )


def counts(result):
    return {
        feature["id"]: feature["count"]
        for feature in result["features"]
    }


class CoreSavingFeaturesTest(unittest.TestCase):

    def test_counts_current_records(self):
        rec_id = recommendation_id("user1", "source1")

        result = calculate(
            wishlists=[("w1", {}), ("w2", {}), ("w3", {})],
            products=[
                ("p1", {"ownerId": "user1"}),
                ("p2", {"ownerId": "user1"}),
                (rec_id, {"ownerId": "user1"}),
            ],
            events=[("e1", saved_event("user1", "source1"))],
        )

        self.assertEqual(counts(result), {
            "wishlist": 3,
            "manual_product": 2,
            "recommended_product": 1,
        })
        self.assertEqual(result["leaders"], ["wishlist"])
        self.assertEqual(result["status"], "leader")

    def test_deleted_recommendation_does_not_count(self):
        result = calculate(
            events=[("e1", saved_event("user1", "source1"))],
        )

        self.assertEqual(counts(result)["recommended_product"], 0)
        self.assertEqual(result["totalCurrentProducts"], 0)

    def test_duplicate_events_do_not_duplicate_products(self):
        rec_id = recommendation_id("user1", "source1")
        event = saved_event("user1", "source1")

        result = calculate(
            products=[(rec_id, {"ownerId": "user1"})],
            events=[("e1", event), ("e2", event)],
        )

        self.assertEqual(counts(result)["recommended_product"], 1)

    def test_recommendation_must_belong_to_product_owner(self):
        rec_id = recommendation_id("user1", "source1")

        result = calculate(
            products=[(rec_id, {"ownerId": "another-user"})],
            events=[("e1", saved_event("user1", "source1"))],
        )

        self.assertEqual(counts(result)["recommended_product"], 0)
        self.assertEqual(result["unclassifiedProducts"], 1)
        self.assertFalse(result["classificationComplete"])

    def test_unsaved_event_does_not_count(self):
        rec_id = recommendation_id("user1", "source1")
        event = saved_event("user1", "source1")
        event["savedAt"] = None

        result = calculate(
            products=[(rec_id, {"ownerId": "user1"})],
            events=[("e1", event)],
        )

        self.assertEqual(counts(result)["recommended_product"], 0)
        self.assertEqual(result["unclassifiedProducts"], 1)

    def test_incorrect_recommendation_id_does_not_count(self):
        rec_id = recommendation_id("user1", "source1")
        event = saved_event("user1", "source2")
        event["savedProductId"] = rec_id

        result = calculate(
            products=[(rec_id, {"ownerId": "user1"})],
            events=[("e1", event)],
        )

        self.assertEqual(counts(result)["recommended_product"], 0)
        self.assertEqual(result["unclassifiedProducts"], 1)

    def test_ties_are_reported(self):
        result = calculate(
            wishlists=[("w1", {})],
            products=[("p1", {"ownerId": "user1"})],
        )

        self.assertEqual(result["status"], "tie")
        self.assertEqual(
            result["leaders"],
            ["wishlist", "manual_product"],
        )
        self.assertEqual(result["highestCount"], 1)

    def test_empty_database_has_no_winner(self):
        result = calculate()

        self.assertEqual(result["status"], "empty")
        self.assertEqual(result["leaders"], [])
        self.assertEqual(result["highestCount"], 0)

    def test_firestore_reads_three_collections(self):
        collections = {
            "wishlists": [("w1", {})],
            "products": [("p1", {"ownerId": "user1"})],
            "productEvents": [],
        }

        db = Mock()

        def collection(name):
            docs = [
                SimpleNamespace(id=doc_id, to_dict=lambda data=data: data)
                for doc_id, data in collections[name]
            ]
            return SimpleNamespace(stream=lambda: iter(docs))

        db.collection.side_effect = collection

        result = compute_from_firestore(db, {})

        self.assertEqual(counts(result)["wishlist"], 1)
        self.assertEqual(counts(result)["manual_product"], 1)
        self.assertEqual(counts(result)["recommended_product"], 0)

        self.assertEqual(
            [call.args[0] for call in db.collection.call_args_list],
            ["wishlists", "products", "productEvents"],
        )


if __name__ == "__main__":
    unittest.main()