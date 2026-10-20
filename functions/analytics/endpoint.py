"""Shared, admin-only analytics callable.

Every business question (BQ) answered for the admin dashboard goes through the
single `get_admin_analytics` callable. A BQ is one module exposing
`compute_from_firestore(db, params)` plus one line in `METRICS`.
"""

from datetime import datetime, timezone

from firebase_admin import firestore
from firebase_functions import https_fn


# metric name -> compute_from_firestore(db, params) returning JSON-safe data.
METRICS = {}


def require_admin(req: https_fn.CallableRequest):
    """Reject callers who are not signed in with the `admin: true` claim.

    Authorization comes from the signed ID token, never from a Firestore
    field, matching `isAdmin()` in firestore.rules.
    """
    if req.auth is None:
        raise https_fn.HttpsError(
            code=https_fn.FunctionsErrorCode.UNAUTHENTICATED,
            message="You must be logged in.",
        )

    token = req.auth.token or {}
    if token.get("admin") is not True:
        raise https_fn.HttpsError(
            code=https_fn.FunctionsErrorCode.PERMISSION_DENIED,
            message="Administrator access is required.",
        )


def get_admin_analytics(req: https_fn.CallableRequest):
    """Compute one admin metric, chosen by `metric` in the request data."""
    require_admin(req)

    if not isinstance(req.data, dict):
        raise https_fn.HttpsError(
            code=https_fn.FunctionsErrorCode.INVALID_ARGUMENT,
            message="metric is required.",
        )

    metric = req.data.get("metric")
    if not isinstance(metric, str) or not metric.strip():
        raise https_fn.HttpsError(
            code=https_fn.FunctionsErrorCode.INVALID_ARGUMENT,
            message="metric is required.",
        )

    metric = metric.strip()
    compute = METRICS.get(metric)
    if compute is None:
        raise https_fn.HttpsError(
            code=https_fn.FunctionsErrorCode.INVALID_ARGUMENT,
            message=f"Unknown metric: {metric}.",
        )

    params = req.data.get("params", {})
    if params is None:
        params = {}
    if not isinstance(params, dict):
        raise https_fn.HttpsError(
            code=https_fn.FunctionsErrorCode.INVALID_ARGUMENT,
            message="params must be an object.",
        )

    data = compute(firestore.client(), params)

    return {
        "metric": metric,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "data": data,
    }
