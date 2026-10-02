"""Recommended-product save and administrative metric logic."""

import hashlib

from firebase_admin import firestore
from firebase_functions import https_fn


def _get_product_key(product):
    product_url = product.get("productUrl", "").strip().lower()
    if product_url:
        return product_url

    brand = product.get("brand", "").strip().lower()
    name = product.get("name", "").strip().lower()
    return f"{brand}|{name}"


def _get_recommended_product_copy_id(user_id, source_product_id):
    raw_value = f"{user_id}:{source_product_id}".encode("utf-8")
    digest = hashlib.sha256(raw_value).hexdigest()
    return f"rec_{digest}"


def _validate_source_product(product):
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


def save_recommended_product(req: https_fn.CallableRequest):
    """Save a shown recommendation exactly once and increment BQ3."""
    if req.auth is None:
        raise https_fn.HttpsError(
            code=https_fn.FunctionsErrorCode.UNAUTHENTICATED,
            message="You must be logged in.",
        )

    if not isinstance(req.data, dict):
        raise https_fn.HttpsError(
            code=https_fn.FunctionsErrorCode.INVALID_ARGUMENT,
            message="recommendationEventId and wishlistId are required.",
        )

    recommendation_event_id = req.data.get("recommendationEventId")
    wishlist_id = req.data.get("wishlistId")

    if (
        not isinstance(recommendation_event_id, str)
        or not recommendation_event_id.strip()
    ):
        raise https_fn.HttpsError(
            code=https_fn.FunctionsErrorCode.INVALID_ARGUMENT,
            message="recommendationEventId is required.",
        )

    if not isinstance(wishlist_id, str) or not wishlist_id.strip():
        raise https_fn.HttpsError(
            code=https_fn.FunctionsErrorCode.INVALID_ARGUMENT,
            message="wishlistId is required.",
        )

    recommendation_event_id = recommendation_event_id.strip()
    wishlist_id = wishlist_id.strip()
    current_uid = req.auth.uid
    db = firestore.client()

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
            message="This recommendation does not belong to the current user.",
        )

    if event.get("savedAt") is not None:
        return {
            "saved": True,
            "alreadySaved": True,
            "productId": event.get("savedProductId"),
        }

    source_product_id = event.get("sourceProductId")
    if not isinstance(source_product_id, str) or not source_product_id:
        raise https_fn.HttpsError(
            code=https_fn.FunctionsErrorCode.FAILED_PRECONDITION,
            message="The recommendation has no source product.",
        )

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
    _validate_source_product(source_product)

    if source_product["ownerId"] == current_uid:
        raise https_fn.HttpsError(
            code=https_fn.FunctionsErrorCode.FAILED_PRECONDITION,
            message="You cannot save your own product as a recommendation.",
        )

    wishlist_ref = db.collection("wishlists").document(wishlist_id)
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
            message="The wishlist does not belong to the current user.",
        )

    if wishlist.get("categoryId") != source_product["categoryId"]:
        raise https_fn.HttpsError(
            code=https_fn.FunctionsErrorCode.INVALID_ARGUMENT,
            message=(
                "The wishlist category must match "
                "the recommended product category."
            ),
        )

    saved_product_id = _get_recommended_product_copy_id(
        current_uid,
        source_product_id,
    )
    saved_product_ref = (
        db.collection("products")
        .document(saved_product_id)
    )

    source_product_key = _get_product_key(source_product)
    current_products = (
        db.collection("products")
        .where("ownerId", "==", current_uid)
        .stream()
    )

    for product_document in current_products:
        current_product = product_document.to_dict()
        if _get_product_key(current_product) == source_product_key:
            if product_document.id == saved_product_id:
                continue

            raise https_fn.HttpsError(
                code=https_fn.FunctionsErrorCode.ALREADY_EXISTS,
                message="This product is already saved.",
            )

    metric_ref = (
        db.collection("adminMetrics")
        .document("recommendedProductSaves")
    )
    transaction = db.transaction()

    @firestore.transactional
    def save_in_transaction(transaction):
        event_snapshot = event_ref.get(transaction=transaction)
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

        if event_data.get("savedAt") is not None:
            return {
                "saved": True,
                "alreadySaved": True,
                "productId": event_data.get("savedProductId"),
            }

        existing_saved_product = saved_product_ref.get(
            transaction=transaction
        )
        metric_snapshot = metric_ref.get(transaction=transaction)

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

        transaction.update(
            event_ref,
            {
                "savedAt": firestore.SERVER_TIMESTAMP,
                "savedProductId": saved_product_id,
            },
        )

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
