import math

from firebase_admin import firestore, initialize_app
from firebase_functions import https_fn


initialize_app()


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def get_age_group(age):
    if age <= 17:
        return "13-17"
    if age <= 24:
        return "18-24"
    if age <= 34:
        return "25-34"
    if age <= 44:
        return "35-44"

    return "45+"


def get_similarity_score(current_user, other_user):
    score = 0

    if current_user["gender"] == other_user["gender"]:
        score += 1

    if (
        current_user["preferredCategoryId"]
        == other_user["preferredCategoryId"]
    ):
        score += 1

    if (
        get_age_group(current_user["age"])
        == get_age_group(other_user["age"])
    ):
        score += 1

    return score


def get_product_key(product):
    product_url = product.get("productUrl", "").strip().lower()

    if product_url:
        return product_url

    brand = product.get("brand", "").strip().lower()
    name = product.get("name", "").strip().lower()

    return f"{brand}|{name}"


def calculate_distance_km(
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


# ---------------------------------------------------------------------------
# Smart Feature: demographic recommendation
# ---------------------------------------------------------------------------

@https_fn.on_call()
def get_recommendation(req: https_fn.CallableRequest):
    if req.auth is None:
        raise https_fn.HttpsError(
            code=https_fn.FunctionsErrorCode.UNAUTHENTICATED,
            message="You must be logged in.",
        )

    current_uid = req.auth.uid
    db = firestore.client()

    # 1. Get the current user.
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

    # 2. Find the most similar user.
    best_user_id = None
    best_score = -1
    best_age_difference = float("inf")

    for user_document in db.collection("users").stream():
        if user_document.id == current_uid:
            continue

        other_user = user_document.to_dict()

        score = get_similarity_score(
            current_user,
            other_user,
        )

        age_difference = abs(
            current_user["age"] - other_user["age"]
        )

        if score > best_score:
            best_score = score
            best_age_difference = age_difference
            best_user_id = user_document.id

        elif (
            score == best_score
            and age_difference < best_age_difference
        ):
            best_age_difference = age_difference
            best_user_id = user_document.id

    if best_user_id is None:
        return {
            "recommendation": None,
            "message": "No other users were found.",
        }

    # 3. Read the current user's products.
    current_products = (
        db.collection("products")
        .where("ownerId", "==", current_uid)
        .stream()
    )

    current_product_keys = {
        get_product_key(document.to_dict())
        for document in current_products
    }

    # 4. Read products from the most similar user.
    similar_user_products = (
        db.collection("products")
        .where("ownerId", "==", best_user_id)
        .stream()
    )

    purchased_candidates = []
    saved_candidates = []

    for product_document in similar_user_products:
        product = product_document.to_dict()

        # Do not recommend something the current user already has.
        if get_product_key(product) in current_product_keys:
            continue

        if product["purchased"]:
            purchased_candidates.append(product)
        else:
            saved_candidates.append(product)

    # 5. Prefer a purchased product.
    if purchased_candidates:
        recommendation = purchased_candidates[0]
        reason = (
            "A user with similar demographics bought this product."
        )

    elif saved_candidates:
        recommendation = saved_candidates[0]
        reason = (
            "A user with similar demographics saved this product."
        )

    else:
        return {
            "recommendation": None,
            "message": (
                "The most similar user has no new products "
                "to recommend."
            ),
        }

    # 6. Return exactly one recommendation.
    return {
        "recommendation": {
            "name": recommendation["name"],
            "brand": recommendation["brand"],
            "price": recommendation["price"],
            "imageUrl": recommendation["imageUrl"],
            "productUrl": recommendation["productUrl"],
            "categoryId": recommendation["categoryId"],
            "reason": reason,
        }
    }


# ---------------------------------------------------------------------------
# Context-Aware Feature: nearest relevant store
# ---------------------------------------------------------------------------

@https_fn.on_call()
def get_nearest_store(req: https_fn.CallableRequest):
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

    # 1. Get the current user's preferred category.
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

    # 2. Loop through stores and calculate their distance.
    for store_document in db.collection("stores").stream():
        store = store_document.to_dict()

        distance = calculate_distance_km(
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

    # 3. Prefer stores related to the user's preferred category.
    candidates = (
        matching_stores
        if matching_stores
        else all_stores
    )

    # 4. Find the nearest store with a simple loop.
    nearest_store = None
    shortest_distance = float("inf")

    for store in candidates:
        if store["distanceKm"] < shortest_distance:
            shortest_distance = store["distanceKm"]
            nearest_store = store

    # 5. Return exactly one store.
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
            "distanceKm": round(
                nearest_store["distanceKm"],
                2,
            ),
        }
    }
