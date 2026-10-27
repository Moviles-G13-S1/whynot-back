"""Endpoint tests for Juliana's Sprint 3 core saving features BQ."""

import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

FUNCTIONS_DIR = Path(__file__).resolve().parents[1] / "functions"
sys.path.insert(0, str(FUNCTIONS_DIR))

from firebase_functions import https_fn  # noqa: E402
from analytics import endpoint, core_saving_features  # noqa: E402


def request(admin=False, signed_in=True):
    auth = (
        SimpleNamespace(
            uid="user1",
            token={"admin": admin},
        )
        if signed_in
        else None
    )
    return SimpleNamespace(
        auth=auth,
        data={"metric": "core_saving_features", "params": {}},
    )


class CoreSavingFeaturesEndpointTest(unittest.TestCase):

    def test_metric_is_registered(self):
        self.assertIs(
            endpoint.METRICS["core_saving_features"],
            core_saving_features.compute_from_firestore,
        )

    def test_admin_can_request_metric(self):
        expected = {
            "features": [],
            "leaders": [],
            "status": "empty",
        }

        compute = mock.Mock(return_value=expected)
        db = object()

        with mock.patch.dict(
            endpoint.METRICS,
            {"core_saving_features": compute},
        ):
            with mock.patch.object(
                endpoint.firestore,
                "client",
                return_value=db,
            ):
                response = endpoint.get_admin_analytics(
                    request(admin=True)
                )

        compute.assert_called_once_with(db, {})
        self.assertEqual(response["metric"], "core_saving_features")
        self.assertEqual(response["data"], expected)
        self.assertIsInstance(response["generatedAt"], str)

        json.dumps(response)

    def test_signed_out_user_is_rejected(self):
        with mock.patch.object(endpoint.firestore, "client") as client:
            with self.assertRaises(https_fn.HttpsError) as raised:
                endpoint.get_admin_analytics(request(signed_in=False))

        self.assertEqual(
            raised.exception.code,
            https_fn.FunctionsErrorCode.UNAUTHENTICATED,
        )
        client.assert_not_called()

    def test_non_admin_is_rejected(self):
        with mock.patch.object(endpoint.firestore, "client") as client:
            with self.assertRaises(https_fn.HttpsError) as raised:
                endpoint.get_admin_analytics(request(admin=False))

        self.assertEqual(
            raised.exception.code,
            https_fn.FunctionsErrorCode.PERMISSION_DENIED,
        )
        client.assert_not_called()


if __name__ == "__main__":
    unittest.main()