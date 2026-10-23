"""Delete callable contract, including idempotent outcomes and ownership."""

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "functions"))
from firebase_functions import https_fn  # noqa: E402
import wishlist_mutations  # noqa: E402


class Snapshot:
    def __init__(self, data):
        self.exists = data is not None
        self._data = data

    def to_dict(self):
        return self._data


class Document:
    def __init__(self, db, collection, key):
        self.db, self.collection, self.key = db, collection, key

    def get(self, transaction=None):
        return Snapshot(self.db.data[self.collection].get(self.key))


class Collection:
    def __init__(self, db, name):
        self.db, self.name = db, name

    def document(self, key):
        return Document(self.db, self.name, key)

    def where(self, field, op, value):
        self.field, self.value = field, value
        return self

    def limit(self, count):
        return self

    def stream(self, transaction=None):
        return [Snapshot(item) for item in self.db.data[self.name].values() if item.get(self.field) == self.value][:1]


class Transaction:
    def update(self, ref, values):
        current = ref.db.data[ref.collection][ref.key]
        for key, value in values.items():
            if value is wishlist_mutations.firestore.DELETE_FIELD:
                current.pop(key, None)
            else:
                current[key] = value

    def delete(self, ref):
        ref.db.data[ref.collection].pop(ref.key)

    def create(self, ref, values):
        assert ref.key not in ref.db.data[ref.collection]
        ref.db.data[ref.collection][ref.key] = values


class Database:
    def __init__(self, owner='alice', products=None):
        self.data = {
            'wishlists': {'w1': {'ownerId': owner, 'categoryId': 'fashion'}},
            'products': products or {}, 'wishlistInteractionEvents': {},
        }

    def collection(self, name):
        return Collection(self, name)

    def transaction(self):
        return Transaction()


def request(uid='alice', operation='op1'):
    return SimpleNamespace(auth=SimpleNamespace(uid=uid), data={
        'wishlistId': 'w1', 'operationId': operation, 'platform': 'android',
    })


class DeleteWishlistTest(unittest.TestCase):
    def call(self, db, req):
        with mock.patch.object(wishlist_mutations.firestore, 'client', return_value=db), \
             mock.patch.object(wishlist_mutations.firestore, 'transactional', side_effect=lambda fn: fn):
            return wishlist_mutations.delete_empty_wishlist(req)

    def test_success_is_atomic_with_event_and_idempotent(self):
        db = Database()
        self.assertEqual(self.call(db, request()), {'outcome': 'success', 'reason': 'none'})
        self.assertNotIn('w1', db.data['wishlists'])
        self.assertEqual(db.data['wishlistInteractionEvents']['op1']['outcome'], 'success')
        self.assertEqual(self.call(db, request()), {'outcome': 'success', 'reason': 'none'})
        self.assertEqual(len(db.data['wishlistInteractionEvents']), 1)

    def test_nonempty_stays_intact_and_records_blocked(self):
        db = Database(products={'p1': {'wishlistId': 'w1'}})
        self.assertEqual(self.call(db, request()), {'outcome': 'blocked', 'reason': 'nonempty'})
        self.assertIn('w1', db.data['wishlists'])
        self.assertIn('p1', db.data['products'])
        self.assertNotIn('deleting', db.data['wishlists']['w1'])

    def test_foreign_owner_cannot_delete(self):
        db = Database(owner='bob')
        self.assertEqual(self.call(db, request()), {'outcome': 'failure', 'reason': 'not_found'})
        self.assertIn('w1', db.data['wishlists'])

    def test_stale_reservation_can_be_recovered(self):
        db = Database()
        db.data['wishlists']['w1'].update({
            'deleting': True, 'deleteOperationId': 'abandoned',
            'deleteReservedAt': datetime.now(timezone.utc) - timedelta(minutes=3),
        })
        self.assertEqual(self.call(db, request()), {'outcome': 'success', 'reason': 'none'})

    def test_missing_auth_and_bad_input(self):
        db = Database()
        with self.assertRaises(https_fn.HttpsError):
            self.call(db, SimpleNamespace(auth=None, data={}))
        with self.assertRaises(https_fn.HttpsError):
            self.call(db, SimpleNamespace(auth=SimpleNamespace(uid='alice'), data={'wishlistId': 'w1'}))


if __name__ == '__main__':
    unittest.main()
