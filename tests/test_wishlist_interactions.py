"""Supporting Wishlist UX metric contract."""

import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "functions"))
from analytics import endpoint, wishlist_interactions  # noqa: E402


class WishlistInteractionsTest(unittest.TestCase):
    def test_counts_actions_outcomes_users_and_reasons_once_per_operation(self):
        events = [
            ("a", {"schemaVersion": 1, "operationId": "a", "action": "open", "outcome": "intent", "userId": "u1"}),
            ("b", {"schemaVersion": 1, "operationId": "b", "action": "create", "outcome": "success", "userId": "u1"}),
            ("c", {"schemaVersion": 1, "operationId": "c", "action": "delete", "outcome": "blocked", "reason": "nonempty", "userId": "u1"}),
            ("c-copy", {"schemaVersion": 1, "operationId": "c", "action": "delete", "outcome": "blocked", "reason": "nonempty", "userId": "u1"}),
            ("d", {"schemaVersion": 1, "operationId": "d", "action": "delete", "outcome": "success", "userId": "u2"}),
            ("legacy", {"operationId": "legacy", "action": "open", "outcome": "intent", "userId": "u3"}),
        ]
        result = wishlist_interactions.summarize(events)
        self.assertEqual(result["totalEvents"], 4)
        self.assertEqual(result["actions"]["open"]["successRate"], None)
        self.assertEqual(result["actions"]["delete"]["uniqueUsers"], 2)
        self.assertEqual(result["actions"]["delete"]["successRate"], 50.0)
        self.assertEqual(result["actions"]["delete"]["failureReasons"], {"nonempty": 1})

    def test_registered_under_admin_callable(self):
        self.assertIs(endpoint.METRICS["wishlist_interactions"], wishlist_interactions.compute_from_firestore)
        doc = mock.Mock(id="e", to_dict=mock.Mock(return_value={"schemaVersion": 1, "operationId": "e", "action": "edit", "outcome": "failure", "reason": "validation", "userId": "u"}))
        db = mock.Mock()
        db.collection.return_value.stream.return_value = [doc]
        result = wishlist_interactions.compute_from_firestore(db, {})
        db.collection.assert_called_once_with("wishlistInteractionEvents")
        self.assertEqual(result["actions"]["edit"]["failureReasons"], {"validation": 1})


if __name__ == "__main__":
    unittest.main()
