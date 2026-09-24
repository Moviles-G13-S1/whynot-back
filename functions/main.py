"""Firebase Functions entrypoints for WhyNot.

Firebase discovers the decorated functions in this module. Feature logic lives
in focused modules so this file remains a small composition root.
"""

import os

from google.auth.credentials import AnonymousCredentials

from firebase_admin import initialize_app
from firebase_functions import https_fn

from nearest_store import get_nearest_store as handle_get_nearest_store
from recommendations import get_recommendation as handle_get_recommendation
from recommended_product_saves import (
    save_recommended_product as handle_save_recommended_product,
)


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
def save_recommended_product(req: https_fn.CallableRequest):
    """Save a recommendation and update its administrative metric."""
    return handle_save_recommended_product(req)


@https_fn.on_call()
def get_nearest_store(req: https_fn.CallableRequest):
    """Return the nearest store relevant to the current user."""
    return handle_get_nearest_store(req)
