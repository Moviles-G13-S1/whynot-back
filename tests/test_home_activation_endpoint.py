import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'functions'))
from firebase_functions import https_fn
from analytics import endpoint, home_activation


class MartinEndpointTest(unittest.TestCase):
    def test_metric_is_registered(self):
        self.assertIs(endpoint.METRICS['home_activation'], home_activation.compute_from_firestore)

    def test_non_admin_cannot_read_home_events(self):
        req = SimpleNamespace(auth=SimpleNamespace(uid='user', token={}), data={'metric': 'home_activation'})
        with patch.object(endpoint.firestore, 'client') as client:
            with self.assertRaises(https_fn.HttpsError) as caught:
                endpoint.get_admin_analytics(req)
            self.assertEqual(caught.exception.code, https_fn.FunctionsErrorCode.PERMISSION_DENIED)
            client.assert_not_called()

    def test_admin_receives_home_aggregate(self):
        req = SimpleNamespace(auth=SimpleNamespace(uid='admin', token={'admin': True}), data={'metric': 'home_activation'})
        db = Mock()
        db.collection.return_value.stream.return_value = []
        with patch.object(endpoint.firestore, 'client', return_value=db):
            response = endpoint.get_admin_analytics(req)
        self.assertEqual(response['metric'], 'home_activation')
        self.assertEqual([item['count'] for item in response['data']['events']], [0, 0, 0])
        db.collection.assert_called_once_with('uxEvents')

    def test_teammate_onboarding_metric_is_preserved(self):
        from analytics import onboarding
        self.assertIs(endpoint.METRICS['onboarding'], onboarding.compute_from_firestore)
