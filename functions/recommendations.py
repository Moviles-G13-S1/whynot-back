"""Demographic product recommendation logic."""

from firebase_admin import firestore
from firebase_functions import https_fn


def _get_age_group(age):
    if age <= 17:
        return "13-17"
    if age <= 24:
        return "18-24"
    if age <= 34:
        return "25-34"
    if age <= 44:
        return "35-44"
    return "45+"


def _get_similarity_score(current_user, other_user):
    score = 0

    if current_user["gender"] == other_user["gender"]:
        score += 1

    if (
        current_user["preferredCategoryId"]
        == other_user["preferredCategoryId"]
    ):
        score += 1

    if (
        _get_age_group(current_user["age"])
        == _get_age_group(other_user["age"])
    ):
        score += 1

    return score


def _get_product_key(product):
    product_url = product.get("productUrl", "").strip().lower()
    if product_url:
        return product_url

    brand = product.get("brand", "").strip().lower()
    name = product.get("name", "").strip().lower()
    return f"{brand}|{name}"


def get_recommendation(req: https_fn.CallableRequest):
    """Choose one unseen product from a demographically similar user."""
    if req.auth is None:
        raise https_fn.HttpsError(
            code=https_fn.FunctionsErrorCode.UNAUTHENTICATED,
            message="You must be logged in.",
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

    current_products = (
        db.collection("products")
        .where("ownerId", "==", current_uid)
        .stream()
    )
    current_product_keys = {
        _get_product_key(document.to_dict())
        for document in current_products
    }

    ranked_users = []
    for user_document in db.collection("users").stream():
        if user_document.id == current_uid:
            continue

        other_user = user_document.to_dict()
        ranked_users.append(
            {
                "id": user_document.id,
                "score": _get_similarity_score(current_user, other_user),
                "ageDifference": abs(
                    current_user["age"] - other_user["age"]
                ),
            }
        )

    if not ranked_users:
        return {
            "recommendation": None,
            "message": "No other users were found.",
        }

    ranked_users.sort(
        key=lambda user: (
            -user["score"],
            user["ageDifference"],
            user["id"],
        )
    )

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

            if product.get("categoryId") != preferred_category:
                continue
            if _get_product_key(product) in current_product_keys:
                continue

            candidate = {"id": product_document.id, **product}
            if product.get("purchased", False):
                purchased_candidates.append(candidate)
            else:
                saved_candidates.append(candidate)

        if purchased_candidates:
            recommendation = purchased_candidates[0]
            reason = "A user with similar demographics bought this product."
            break

        if saved_candidates:
            recommendation = saved_candidates[0]
            reason = "A user with similar demographics saved this product."
            break

    if recommendation is None:
        return {
            "recommendation": None,
            "message": (
                "No similar user has a new product "
                "in the preferred category."
            ),
        }

    recommendation_event_ref = db.collection("productEvents").document()
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
