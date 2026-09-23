import hashlib
import math
import os

from google.auth.credentials import AnonymousCredentials

from firebase_admin import firestore, initialize_app
from firebase_functions import https_fn


# ---------------------------------------------------------------------------
# Firebase initialization
# ---------------------------------------------------------------------------

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
        {
            "projectId": project_id,
        },
    )
else:
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


def get_recommended_product_copy_id(
    user_id,
    source_product_id,
):
    raw_value = f"{user_id}:{source_product_id}".encode("utf-8")
    digest = hashlib.sha256(raw_value).hexdigest()

    return f"rec_{digest}"


def validate_source_product(product):
    required_string_fields = [
        "ownerId",
        "categoryId",
        "name",
        "brand",
        "imageUrl",
        "productUrl",
    ]

    for field in required_string_fields:
        if not isinstance(product.get(field), str):
            raise https_fn.HttpsError(
                code=https_fn.FunctionsErrorCode.FAILED_PRECONDITION,
                message=(
                    "The recommended product is incomplete or invalid: "
                    f"{field}."
                ),
            )

    if not product["ownerId"].strip():
        raise https_fn.HttpsError(
            code=https_fn.FunctionsErrorCode.FAILED_PRECONDITION,
            message="The recommended product has no owner.",
        )

    if not product["categoryId"].strip():
        raise https_fn.HttpsError(
            code=https_fn.FunctionsErrorCode.FAILED_PRECONDITION,
            message="The recommended product has no category.",
        )

    if not product["name"].strip():
        raise https_fn.HttpsError(
            code=https_fn.FunctionsErrorCode.FAILED_PRECONDITION,
            message="The recommended product has an empty name.",
        )

    if not product["brand"].strip():
        raise https_fn.HttpsError(
            code=https_fn.FunctionsErrorCode.FAILED_PRECONDITION,
            message="The recommended product has an empty brand.",
        )

    if len(product["name"]) > 200:
        raise https_fn.HttpsError(
            code=https_fn.FunctionsErrorCode.FAILED_PRECONDITION,
            message="The recommended product name is too long.",
        )

    if len(product["brand"]) > 200:
        raise https_fn.HttpsError(
            code=https_fn.FunctionsErrorCode.FAILED_PRECONDITION,
            message="The recommended product brand is too long.",
        )

    if len(product["imageUrl"]) > 2048:
        raise https_fn.HttpsError(
            code=https_fn.FunctionsErrorCode.FAILED_PRECONDITION,
            message="The recommended product image URL is too long.",
        )

    if len(product["productUrl"]) > 2048:
        raise https_fn.HttpsError(
            code=https_fn.FunctionsErrorCode.FAILED_PRECONDITION,
            message="The recommended product URL is too long.",
        )

    price = product.get("price")

    if (
        not isinstance(price, (int, float))
        or isinstance(price, bool)
        or price < 0
    ):
        raise https_fn.HttpsError(
            code=https_fn.FunctionsErrorCode.FAILED_PRECONDITION,
            message="The recommended product has an invalid price.",
        )


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

    # -----------------------------------------------------------------------
    # 1. Get current user
    # -----------------------------------------------------------------------

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

    # -----------------------------------------------------------------------
    # 2. Read products already owned by current user
    # -----------------------------------------------------------------------

    current_products = (
        db.collection("products")
        .where("ownerId", "==", current_uid)
        .stream()
    )

    current_product_keys = {
        get_product_key(document.to_dict())
        for document in current_products
    }

    # -----------------------------------------------------------------------
    # 3. Rank other users by demographic similarity
    # -----------------------------------------------------------------------

    ranked_users = []

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

        ranked_users.append(
            {
                "id": user_document.id,
                "score": score,
                "ageDifference": age_difference,
            }
        )

    if not ranked_users:
        return {
            "recommendation": None,
            "message": "No other users were found.",
        }

    # Most similar users first.
    #
    # First:
    #   higher demographic similarity score
    #
    # Second:
    #   smaller age difference
    #
    # Third:
    #   document ID only provides deterministic ordering
    #   if everything else is tied.
    ranked_users.sort(
        key=lambda user: (
            -user["score"],
            user["ageDifference"],
            user["id"],
        )
    )

    # -----------------------------------------------------------------------
    # 4. Find the most similar user that actually has a useful product
    # -----------------------------------------------------------------------

    recommendation = None
    reason = None

    for candidate_user in ranked_users:
        user_products = (
            db.collection("products")
            .where("ownerId", "==", candidate_user["id"])
            .stream()
        )

        purchased_candidates = []
        saved_candidates = []

        for product_document in user_products:
            product = product_document.to_dict()

            # The product must belong to the category
            # preferred by the current user.
            #
            # Example:
            #
            # preferredCategoryId = "technology"
            #
            # fashion     -> ignored
            # beauty      -> ignored
            # technology  -> candidate
            if product.get("categoryId") != preferred_category:
                continue

            # Do not recommend something the current user
            # already owns or has already saved.
            if get_product_key(product) in current_product_keys:
                continue

            candidate = {
                "id": product_document.id,
                **product,
            }

            # Purchased products are stronger recommendations,
            # but only inside the preferred category.
            if product.get("purchased", False):
                purchased_candidates.append(candidate)
            else:
                saved_candidates.append(candidate)

        # Prefer a purchased product from this similar user.
        if purchased_candidates:
            recommendation = purchased_candidates[0]

            reason = (
                "A user with similar demographics bought this product."
            )

            break

        # If the user has not purchased anything useful,
        # a saved product is also a valid recommendation.
        if saved_candidates:
            recommendation = saved_candidates[0]

            reason = (
                "A user with similar demographics saved this product."
            )

            break

        # If this similar user has no useful products in the
        # preferred category, continue to the next most similar user.

    # -----------------------------------------------------------------------
    # 5. No valid recommendation found
    # -----------------------------------------------------------------------

    if recommendation is None:
        return {
            "recommendation": None,
            "message": (
                "No similar user has a new product "
                "in the preferred category."
            ),
        }

    # -----------------------------------------------------------------------
    # 6. Register recommendation event
    # -----------------------------------------------------------------------

    recommendation_event_ref = (
        db.collection("productEvents")
        .document()
    )

    recommendation_event_ref.set(
        {
            "eventType": "recommendation_shown",
            "userId": current_uid,
            "sourceProductId": recommendation["id"],
            "createdAt": firestore.SERVER_TIMESTAMP,
            "savedAt": None,
            "savedProductId": None,
        }
    )

    # -----------------------------------------------------------------------
    # 7. Return recommendation
    # -----------------------------------------------------------------------

    return {
        "recommendation": {
            "recommendationEventId": recommendation_event_ref.id,
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
# BQ3: save a product from a recommendation
# ---------------------------------------------------------------------------

@https_fn.on_call()
def save_recommended_product(req: https_fn.CallableRequest):
    if req.auth is None:
        raise https_fn.HttpsError(
            code=https_fn.FunctionsErrorCode.UNAUTHENTICATED,
            message="You must be logged in.",
        )

    if not isinstance(req.data, dict):
        raise https_fn.HttpsError(
            code=https_fn.FunctionsErrorCode.INVALID_ARGUMENT,
            message=(
                "recommendationEventId and wishlistId are required."
            ),
        )

    recommendation_event_id = req.data.get(
        "recommendationEventId"
    )

    wishlist_id = req.data.get("wishlistId")

    if (
        not isinstance(recommendation_event_id, str)
        or not recommendation_event_id.strip()
    ):
        raise https_fn.HttpsError(
            code=https_fn.FunctionsErrorCode.INVALID_ARGUMENT,
            message="recommendationEventId is required.",
        )

    if (
        not isinstance(wishlist_id, str)
        or not wishlist_id.strip()
    ):
        raise https_fn.HttpsError(
            code=https_fn.FunctionsErrorCode.INVALID_ARGUMENT,
            message="wishlistId is required.",
        )

    recommendation_event_id = recommendation_event_id.strip()
    wishlist_id = wishlist_id.strip()

    current_uid = req.auth.uid
    db = firestore.client()

    # -----------------------------------------------------------------------
    # 1. Validate recommendation event
    # -----------------------------------------------------------------------

    event_ref = (
        db.collection("productEvents")
        .document(recommendation_event_id)
    )

    event_document = event_ref.get()

    if not event_document.exists:
        raise https_fn.HttpsError(
            code=https_fn.FunctionsErrorCode.NOT_FOUND,
            message="Recommendation event not found.",
        )

    event = event_document.to_dict()

    if event.get("eventType") != "recommendation_shown":
        raise https_fn.HttpsError(
            code=https_fn.FunctionsErrorCode.FAILED_PRECONDITION,
            message="Invalid recommendation event.",
        )

    if event.get("userId") != current_uid:
        raise https_fn.HttpsError(
            code=https_fn.FunctionsErrorCode.PERMISSION_DENIED,
            message=(
                "This recommendation does not belong "
                "to the current user."
            ),
        )

    # If this recommendation was already saved,
    # return the previous result.
    #
    # This makes the operation idempotent and prevents
    # double taps or network retries from incrementing BQ3 twice.
    if event.get("savedAt") is not None:
        return {
            "saved": True,
            "alreadySaved": True,
            "productId": event.get("savedProductId"),
        }

    source_product_id = event.get("sourceProductId")

    if (
        not isinstance(source_product_id, str)
        or not source_product_id
    ):
        raise https_fn.HttpsError(
            code=https_fn.FunctionsErrorCode.FAILED_PRECONDITION,
            message="The recommendation has no source product.",
        )

    # -----------------------------------------------------------------------
    # 2. Read and validate source product
    # -----------------------------------------------------------------------

    source_product_ref = (
        db.collection("products")
        .document(source_product_id)
    )

    source_product_document = source_product_ref.get()

    if not source_product_document.exists:
        raise https_fn.HttpsError(
            code=https_fn.FunctionsErrorCode.FAILED_PRECONDITION,
            message="The recommended product no longer exists.",
        )

    source_product = source_product_document.to_dict()

    validate_source_product(source_product)

    if source_product["ownerId"] == current_uid:
        raise https_fn.HttpsError(
            code=https_fn.FunctionsErrorCode.FAILED_PRECONDITION,
            message=(
                "You cannot save your own product "
                "as a recommendation."
            ),
        )

    # -----------------------------------------------------------------------
    # 3. Validate destination wishlist
    # -----------------------------------------------------------------------

    wishlist_ref = (
        db.collection("wishlists")
        .document(wishlist_id)
    )

    wishlist_document = wishlist_ref.get()

    if not wishlist_document.exists:
        raise https_fn.HttpsError(
            code=https_fn.FunctionsErrorCode.NOT_FOUND,
            message="Wishlist not found.",
        )

    wishlist = wishlist_document.to_dict()

    if wishlist.get("ownerId") != current_uid:
        raise https_fn.HttpsError(
            code=https_fn.FunctionsErrorCode.PERMISSION_DENIED,
            message=(
                "The wishlist does not belong "
                "to the current user."
            ),
        )

    if wishlist.get("categoryId") != source_product["categoryId"]:
        raise https_fn.HttpsError(
            code=https_fn.FunctionsErrorCode.INVALID_ARGUMENT,
            message=(
                "The wishlist category must match "
                "the recommended product category."
            ),
        )

    # -----------------------------------------------------------------------
    # 4. Generate deterministic destination product ID
    # -----------------------------------------------------------------------

    saved_product_id = get_recommended_product_copy_id(
        current_uid,
        source_product_id,
    )

    saved_product_ref = (
        db.collection("products")
        .document(saved_product_id)
    )

    # -----------------------------------------------------------------------
    # 5. Prevent manual duplicate
    # -----------------------------------------------------------------------

    source_product_key = get_product_key(source_product)

    current_products = (
        db.collection("products")
        .where("ownerId", "==", current_uid)
        .stream()
    )

    for product_document in current_products:
        current_product = product_document.to_dict()

        if (
            get_product_key(current_product)
            == source_product_key
        ):
            if product_document.id == saved_product_id:
                continue

            raise https_fn.HttpsError(
                code=https_fn.FunctionsErrorCode.ALREADY_EXISTS,
                message="This product is already saved.",
            )

    # -----------------------------------------------------------------------
    # 6. BQ3 metric
    # -----------------------------------------------------------------------

    metric_ref = (
        db.collection("adminMetrics")
        .document("recommendedProductSaves")
    )

    transaction = db.transaction()

    # -----------------------------------------------------------------------
    # 7. Save recommendation and increment BQ3 atomically
    # -----------------------------------------------------------------------

    @firestore.transactional
    def save_in_transaction(transaction):
        event_snapshot = event_ref.get(
            transaction=transaction
        )

        if not event_snapshot.exists:
            raise https_fn.HttpsError(
                code=https_fn.FunctionsErrorCode.NOT_FOUND,
                message="Recommendation event not found.",
            )

        event_data = event_snapshot.to_dict()

        if event_data.get("eventType") != "recommendation_shown":
            raise https_fn.HttpsError(
                code=https_fn.FunctionsErrorCode.FAILED_PRECONDITION,
                message="Invalid recommendation event.",
            )

        if event_data.get("userId") != current_uid:
            raise https_fn.HttpsError(
                code=https_fn.FunctionsErrorCode.PERMISSION_DENIED,
                message=(
                    "This recommendation does not belong "
                    "to the current user."
                ),
            )

        # Another request may have consumed the event
        # while this request was waiting.
        if event_data.get("savedAt") is not None:
            return {
                "saved": True,
                "alreadySaved": True,
                "productId": event_data.get("savedProductId"),
            }

        existing_saved_product = saved_product_ref.get(
            transaction=transaction
        )

        metric_snapshot = metric_ref.get(
            transaction=transaction
        )

        # If the deterministic product already exists,
        # do not increment BQ3 again.
        if existing_saved_product.exists:
            transaction.update(
                event_ref,
                {
                    "savedAt": firestore.SERVER_TIMESTAMP,
                    "savedProductId": saved_product_id,
                },
            )

            return {
                "saved": True,
                "alreadySaved": True,
                "productId": saved_product_id,
            }

        # Current BQ3 total.
        if metric_snapshot.exists:
            metric_data = metric_snapshot.to_dict()

            current_total = metric_data.get("total", 0)

            if (
                not isinstance(current_total, int)
                or isinstance(current_total, bool)
                or current_total < 0
            ):
                current_total = 0

        else:
            current_total = 0

        # Save a copy of the recommended product
        # inside the authenticated user's wishlist.
        transaction.set(
            saved_product_ref,
            {
                "ownerId": current_uid,
                "wishlistId": wishlist_id,
                "categoryId": source_product["categoryId"],
                "name": source_product["name"],
                "brand": source_product["brand"],
                "price": source_product["price"],
                "imageUrl": source_product["imageUrl"],
                "productUrl": source_product["productUrl"],
                "purchased": False,
                "purchasedAt": None,
                "createdAt": firestore.SERVER_TIMESTAMP,
                "updatedAt": firestore.SERVER_TIMESTAMP,
            },
        )

        # Mark the recommendation event as consumed.
        transaction.update(
            event_ref,
            {
                "savedAt": firestore.SERVER_TIMESTAMP,
                "savedProductId": saved_product_id,
            },
        )

        # Increment BQ3.
        transaction.set(
            metric_ref,
            {
                "metric": "recommendedProductsSaved",
                "total": current_total + 1,
                "updatedAt": firestore.SERVER_TIMESTAMP,
            },
            merge=True,
        )

        return {
            "saved": True,
            "alreadySaved": False,
            "productId": saved_product_id,
        }

    return save_in_transaction(transaction)


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

    # -----------------------------------------------------------------------
    # 1. Get current user's preferred category
    # -----------------------------------------------------------------------

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

    # -----------------------------------------------------------------------
    # 2. Calculate distance to stores
    # -----------------------------------------------------------------------

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

    # -----------------------------------------------------------------------
    # 3. Prefer stores related to preferred category
    # -----------------------------------------------------------------------

    candidates = (
        matching_stores
        if matching_stores
        else all_stores
    )

    # -----------------------------------------------------------------------
    # 4. Find nearest store
    # -----------------------------------------------------------------------

    nearest_store = None
    shortest_distance = float("inf")

    for store in candidates:
        if store["distanceKm"] < shortest_distance:
            shortest_distance = store["distanceKm"]
            nearest_store = store

    # -----------------------------------------------------------------------
    # 5. Return store
    # -----------------------------------------------------------------------

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