"""Shared, admin-only analytics callable.

Every business question (BQ) answered for the admin dashboard goes through the
single `get_admin_analytics` callable. A BQ is one module exposing
`compute_from_firestore(db, params)` plus one line in `METRICS`.
"""

from datetime import datetime, timezone

from firebase_admin import firestore
from firebase_functions import https_fn

from . import (
    bq4_purchases_by_category,
    bq6_demographics,
    buying_patterns,
    core_saving_features,
    dashboard_views,
    onboarding,
    product_save_attempts,
    purchase_savings,
    home_activation,
    wishlist_interactions,
    recommendation_home_opens,
    weekly_app_errors,
)


# metric name -> compute_from_firestore(db, params) returning JSON-safe data.
METRICS = {
    "weekly_app_errors": weekly_app_errors.compute_from_firestore,
    "home_activation": home_activation.compute_from_firestore,
    "bq4": bq4_purchases_by_category.compute_from_firestore,
    "bq6": bq6_demographics.compute_from_firestore,
    "saved": dashboard_views.compute_saved,
    "recommended": dashboard_views.compute_recommended,
    "purchased": dashboard_views.compute_purchased,
    "demographic": dashboard_views.compute_demographic,
    "save_attempts": product_save_attempts.compute_from_firestore,
    "onboarding": onboarding.compute_from_firestore,
    "wishlist_interactions": wishlist_interactions.compute_from_firestore,
    "buying_patterns": buying_patterns.compute_from_firestore,
    "recommendation_home_opens": recommendation_home_opens.compute_from_firestore,

    # Sprint 3 - Juliana: Compare current core saving feature records.
    "core_saving_features": core_saving_features.compute_from_firestore,

    # Sprint 3 - Miguel: Money users saved on the products they purchased.
    "purchase_savings": purchase_savings.compute_from_firestore,
}


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
    """Compute one admin metric, retaining the dashboard's legacy view request."""
    require_admin(req)

    if not isinstance(req.data, dict):
        raise https_fn.HttpsError(
            code=https_fn.FunctionsErrorCode.INVALID_ARGUMENT,
            message="metric is required.",
        )

    # The deployed web dashboard still sends {view, ...filters} and expects
    # the metric data directly. Keep it working while clients adopt the shared
    # {metric, params} contract.
    if "view" in req.data and "metric" not in req.data:
        view = req.data["view"]
        if view not in ("saved", "recommended", "purchased", "demographic"):
            raise https_fn.HttpsError(
                code=https_fn.FunctionsErrorCode.INVALID_ARGUMENT,
                message=f"Unknown view: {view}.",
            )
        params = {key: value for key, value in req.data.items() if key != "view"}
        return METRICS[view](firestore.client(), params)

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
