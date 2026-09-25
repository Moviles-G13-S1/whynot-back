"""Nearest relevant store logic."""

import math

from firebase_admin import firestore
from firebase_functions import https_fn


def _calculate_distance_km(
    latitude_1,
    longitude_1,
    latitude_2,
    longitude_2,
):
    earth_radius_km = 6371

    latitude_1 = math.radians(latitude_1)
    longitude_1 = math.radians(longitude_1)
    latitude_2 = math.radians(latitude_2)
    longitude_2 = math.radians(longitude_2)

    latitude_difference = latitude_2 - latitude_1
    longitude_difference = longitude_2 - longitude_1

    value = (
        math.sin(latitude_difference / 2) ** 2
        + math.cos(latitude_1)
        * math.cos(latitude_2)
        * math.sin(longitude_difference / 2) ** 2
    )

    central_angle = 2 * math.atan2(
        math.sqrt(value),
        math.sqrt(1 - value),
    )
    return earth_radius_km * central_angle


def get_nearest_store(req: https_fn.CallableRequest):
    """Find the closest store, preferring the user's category."""
    if req.auth is None:
        raise https_fn.HttpsError(
            code=https_fn.FunctionsErrorCode.UNAUTHENTICATED,
            message="You must be logged in.",
        )

    if not isinstance(req.data, dict):
        raise https_fn.HttpsError(
            code=https_fn.FunctionsErrorCode.INVALID_ARGUMENT,
            message="Location is required.",
        )

    latitude = req.data.get("latitude")
    longitude = req.data.get("longitude")

    if not isinstance(latitude, (int, float)):
        raise https_fn.HttpsError(
            code=https_fn.FunctionsErrorCode.INVALID_ARGUMENT,
            message="Latitude must be a number.",
        )

    if not isinstance(longitude, (int, float)):
        raise https_fn.HttpsError(
            code=https_fn.FunctionsErrorCode.INVALID_ARGUMENT,
            message="Longitude must be a number.",
        )

    current_uid = req.auth.uid
    db = firestore.client()

    current_user_document = (
        db.collection("users")
        .document(current_uid)
        .get()
    )
    if not current_user_document.exists:
        raise https_fn.HttpsError(
            code=https_fn.FunctionsErrorCode.NOT_FOUND,
            message="User profile not found.",
        )

    current_user = current_user_document.to_dict()
    preferred_category = current_user["preferredCategoryId"]

    matching_stores = []
    all_stores = []

    for store_document in db.collection("stores").stream():
        store = store_document.to_dict()
        distance = _calculate_distance_km(
            latitude,
            longitude,
            store["latitude"],
            store["longitude"],
        )
        store_with_distance = {
            "id": store_document.id,
            **store,
            "distanceKm": distance,
        }

        all_stores.append(store_with_distance)
        if preferred_category in store["categoryIds"]:
            matching_stores.append(store_with_distance)

    if not all_stores:
        return {
            "store": None,
            "message": "No stores were found.",
        }

    candidates = matching_stores if matching_stores else all_stores
    nearest_store = min(
        candidates,
        key=lambda store: store["distanceKm"],
    )

    return {
        "store": {
            "id": nearest_store["id"],
            "name": nearest_store["name"],
            "address": nearest_store["address"],
            "latitude": nearest_store["latitude"],
            "longitude": nearest_store["longitude"],
            "categoryIds": nearest_store["categoryIds"],
            "websiteUrl": nearest_store["websiteUrl"],
            "imageUrl": nearest_store["imageUrl"],
            "distanceKm": round(nearest_store["distanceKm"], 2),
        }
    }
