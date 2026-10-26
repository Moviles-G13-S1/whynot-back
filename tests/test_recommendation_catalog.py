"""Catalog eligibility and event creation tests without a live Firestore."""

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "functions"))

import recommendations  # noqa: E402


class FakeDoc:
    def __init__(self, doc_id, data):
        self.id = doc_id
        self.data = data
        self.exists = data is not None

    def to_dict(self):
        return self.data

    def get(self):
        return self

    def set(self, data):
        self.data = data


class FakeCollection:
    def __init__(self, documents):
        self.documents = documents
        self.owner_id = None

    def document(self, doc_id=None):
        if doc_id is None:
            doc_id = f"event-{len(self.documents) + 1}"
            self.documents[doc_id] = FakeDoc(doc_id, None)
        return self.documents.get(doc_id, FakeDoc(doc_id, None))

    def where(self, name, operator, value):
        assert name == "ownerId" and operator == "=="
        filtered = FakeCollection(self.documents)
        filtered.owner_id = value
        return filtered

    def stream(self):
        return [
            doc for doc in self.documents.values()
            if self.owner_id is None or doc.data.get("ownerId") == self.owner_id
        ]


class FakeDB:
    def __init__(self):
        self.users = FakeCollection({
            "me": FakeDoc("me", {"age": 24, "gender": "F", "preferredCategoryId": "fashion"}),
            "peer": FakeDoc("peer", {"age": 25, "gender": "F", "preferredCategoryId": "fashion"}),
            "other": FakeDoc("other", {"age": 43, "gender": "M", "preferredCategoryId": "other"}),
        })
        self.products = FakeCollection({
            "mine": FakeDoc("mine", {"ownerId": "me", "name": "Owned", "brand": "A", "productUrl": "owned", "categoryId": "fashion"}),
            "p1": FakeDoc("p1", {"ownerId": "peer", "name": "Jacket", "brand": "B", "productUrl": "jacket", "categoryId": "fashion", "price": 20, "imageUrl": "", "purchased": True}),
            "p2": FakeDoc("p2", {"ownerId": "peer", "name": "Shoes", "brand": "B", "productUrl": "shoes", "categoryId": "fashion", "price": 10, "imageUrl": "", "purchased": False}),
            "p3": FakeDoc("p3", {"ownerId": "other", "name": "Chair", "brand": "C", "productUrl": "chair", "categoryId": "other"}),
        })
        self.events = FakeCollection({})

    def collection(self, name):
        return {"users": self.users, "products": self.products, "productEvents": self.events}[name]


class CatalogTest(unittest.TestCase):
    def setUp(self):
        self.db = FakeDB()
        patcher = patch.object(recommendations.firestore, "client", return_value=self.db)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_catalog_lists_eligible_items_without_creating_events(self):
        req = SimpleNamespace(auth=SimpleNamespace(uid="me"), data=None)
        items = recommendations.get_recommendation_catalog(req)["recommendations"]
        self.assertEqual([item["sourceProductId"] for item in items], ["p1", "p2"])
        self.assertEqual(self.db.events.documents, {})

    def test_open_rechecks_item_and_creates_only_its_event(self):
        req = SimpleNamespace(auth=SimpleNamespace(uid="me"), data={"sourceProductId": "p2"})
        result = recommendations.get_recommendation(req)["recommendation"]
        self.assertEqual(result["name"], "Shoes")
        self.assertEqual(result["recommendationEventId"], "event-1")
        self.assertEqual(self.db.events.documents["event-1"].data["sourceProductId"], "p2")
        self.assertEqual(len(self.db.events.documents), 1)

    def test_open_rejects_stale_item(self):
        req = SimpleNamespace(auth=SimpleNamespace(uid="me"), data={"sourceProductId": "missing"})
        with self.assertRaises(recommendations.https_fn.HttpsError):
            recommendations.get_recommendation(req)
        self.assertEqual(self.db.events.documents, {})


if __name__ == "__main__":
    unittest.main()
