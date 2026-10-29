"""Martin's manual-product share, using the shared classification rules."""
import hashlib
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'functions'))
from analytics.manual_product_usage import compute_manual_product_usage, compute_from_firestore


class ManualProductUsageTest(unittest.TestCase):
    def test_admin_endpoint_registration_and_access(self):
        from analytics import endpoint
        from firebase_functions import https_fn
        from types import SimpleNamespace
        from unittest.mock import Mock, patch
        self.assertIs(endpoint.METRICS['manual_product_usage'], compute_from_firestore)
        request = SimpleNamespace(auth=SimpleNamespace(token={'admin': True}),
                                  data={'metric': 'manual_product_usage', 'params': {}})
        db = Mock()
        db.collection.return_value.stream.return_value = []
        with patch.object(endpoint.firestore, 'client', return_value=db):
            self.assertIsNone(endpoint.get_admin_analytics(request)['data']['manualPercentage'])
        request.auth.token = {'admin': False}
        with self.assertRaises(https_fn.HttpsError):
            endpoint.get_admin_analytics(request)

    def test_empty_has_no_percentage(self):
        result = compute_manual_product_usage([], [])
        self.assertIsNone(result['manualPercentage'])
        self.assertEqual(result['totalCurrentProducts'], 0)

    def test_confirmed_recommendation_and_manual_share(self):
        saved_id = 'rec_' + hashlib.sha256(b'u1:source1').hexdigest()
        products = [('manual1', {}), ('manual2', {}), (saved_id, {'ownerId': 'u1'})]
        event = {'eventType': 'recommendation_shown', 'userId': 'u1',
                 'sourceProductId': 'source1', 'savedProductId': saved_id,
                 'savedAt': datetime.now(timezone.utc)}
        result = compute_manual_product_usage(products, [('e1', event), ('e2', event)])
        self.assertEqual(result['manualProducts'], 2)
        self.assertEqual(result['recommendedProducts'], 1)
        self.assertEqual(result['manualPercentage'], 66.7)

    def test_unmatched_recommendations_are_excluded_from_denominator(self):
        result = compute_manual_product_usage([('manual', {}), ('rec_unknown', {})], [])
        self.assertEqual(result['manualPercentage'], 100)
        self.assertEqual(result['unclassifiedProducts'], 1)
        self.assertEqual(result['totalCurrentProducts'], 2)
        self.assertIsNone(compute_manual_product_usage([('rec_unknown', {})], [])['manualPercentage'])

    def test_deleted_product_event_is_not_a_current_save(self):
        event = {'eventType': 'recommendation_shown', 'savedAt': datetime.now(timezone.utc),
                 'userId': 'u1', 'sourceProductId': 'source1', 'savedProductId': 'rec_deleted'}
        self.assertEqual(compute_manual_product_usage([], [('e1', event)])['recommendedProducts'], 0)

    def test_firestore_reads_shared_collections(self):
        from unittest.mock import Mock
        db = Mock()
        db.collection.return_value.stream.return_value = []
        result = compute_from_firestore(db, {})
        self.assertEqual([call.args[0] for call in db.collection.call_args_list], ['products', 'productEvents'])
        self.assertIsNone(result['manualPercentage'])


if __name__ == '__main__':
    unittest.main()
