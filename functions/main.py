"""Firebase Functions entrypoints for WhyNot.

Firebase discovers the decorated functions in this module. Feature logic lives
in focused modules so this file remains a small composition root.
"""

import os

from google.auth.credentials import AnonymousCredentials

from firebase_admin import initialize_app
from firebase_functions import https_fn

from analytics import get_admin_analytics as handle_get_admin_analytics
from nearest_store import get_nearest_store as handle_get_nearest_store
from recommendations import (
    get_recommendation as handle_get_recommendation,
    get_recommendation_catalog as handle_get_recommendation_catalog,
)
from recommended_product_saves import (
    save_recommended_product as handle_save_recommended_product,
)
from wishlist_mutations import delete_empty_wishlist as handle_delete_empty_wishlist


IS_EMULATOR = any([
    os.environ.get("FUNCTIONS_EMULATOR") == "true",
    os.environ.get("FIREBASE_EMULATOR_HUB") is not None,
    os.environ.get("FIRESTORE_EMULATOR_HOST") is not None,
    os.environ.get("FIREBASE_AUTH_EMULATOR_HOST") is not None,
])

if IS_EMULATOR:
    project_id = (
        os.environ.get("GCLOUD_PROJECT")
        or os.environ.get("GOOGLE_CLOUD_PROJECT")
        or "demo-whynot"
    )
    initialize_app(
        AnonymousCredentials(),
        {"projectId": project_id},
    )
else:
    initialize_app()


@https_fn.on_call()
def get_recommendation(req: https_fn.CallableRequest):
    """Return a demographic product recommendation."""
    return handle_get_recommendation(req)


@https_fn.on_call()
def get_recommendation_catalog(req: https_fn.CallableRequest):
    """Return all currently eligible recommendations for catalog browsing."""
    return handle_get_recommendation_catalog(req)


@https_fn.on_call()
def save_recommended_product(req: https_fn.CallableRequest):
    """Save a recommendation and record its successful event."""
    return handle_save_recommended_product(req)


@https_fn.on_call()
def get_nearest_store(req: https_fn.CallableRequest):
    """Return the nearest store relevant to the current user."""
    return handle_get_nearest_store(req)


@https_fn.on_call(invoker="public")
def get_admin_analytics(req: https_fn.CallableRequest):
    """Return one processed admin metric; requires the admin claim."""
    return handle_get_admin_analytics(req)


@https_fn.on_call()
def delete_empty_wishlist(req: https_fn.CallableRequest):
    """Delete only an owned, empty wishlist and record the outcome."""
    return handle_delete_empty_wishlist(req)
