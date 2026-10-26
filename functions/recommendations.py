"""Demographic product recommendation logic."""

from firebase_admin import firestore
from firebase_functions import https_fn

from recommendation_logic import has_valid_demographics


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


def _eligible_products(db, current_uid):
    """Rank all distinct, unseen products in the user's preferred category."""
    current_user_document = db.collection("users").document(current_uid).get()
    if not current_user_document.exists:
        raise https_fn.HttpsError(
            code=https_fn.FunctionsErrorCode.NOT_FOUND,
            message="User profile not found.",
        )
    current_user = current_user_document.to_dict()
    if not has_valid_demographics(current_user):
        raise https_fn.HttpsError(
            code=https_fn.FunctionsErrorCode.FAILED_PRECONDITION,
            message="Complete your profile before requesting recommendations.",
        )

    current_keys = {
        _get_product_key(doc.to_dict())
        for doc in db.collection("products").where("ownerId", "==", current_uid).stream()
    }
    ranked_users = []
    for user_document in db.collection("users").stream():
        if user_document.id == current_uid:
            continue
        other = user_document.to_dict()
        if not has_valid_demographics(other):
            continue
        ranked_users.append((
            -_get_similarity_score(current_user, other),
            abs(current_user["age"] - other["age"]),
            user_document.id,
        ))
    ranked_users.sort()

    found = []
    seen = set(current_keys)
    for _score, _age_difference, owner_id in ranked_users:
        products = []
        for doc in db.collection("products").where("ownerId", "==", owner_id).stream():
            product = doc.to_dict()
            if product.get("categoryId") != current_user["preferredCategoryId"]:
                continue
            products.append({"id": doc.id, **product})
        # Stable sorting retains Firestore order within bought/saved groups,
        # matching the original top-pick choice for each ranked user.
        products.sort(key=lambda product: not product.get("purchased", False))
        for product in products:
            key = _get_product_key(product)
            if key in seen:
                continue
            seen.add(key)
            found.append({
                "sourceProductId": product["id"],
                "name": product.get("name", ""),
                "brand": product.get("brand", ""),
                "price": product.get("price", 0),
                "imageUrl": product.get("imageUrl", ""),
                "productUrl": product.get("productUrl", ""),
                "categoryId": product["categoryId"],
                "reason": (
                    "A user with similar demographics bought this product."
                    if product.get("purchased", False)
                    else "A user with similar demographics saved this product."
                ),
            })
    return found


def get_recommendation_catalog(req: https_fn.CallableRequest):
    """Return every currently eligible product without recording a shown event."""
    if req.auth is None:
        raise https_fn.HttpsError(
            code=https_fn.FunctionsErrorCode.UNAUTHENTICATED,
            message="You must be logged in.",
        )
    return {"recommendations": _eligible_products(firestore.client(), req.auth.uid)}


def get_recommendation(req: https_fn.CallableRequest):
    """Choose one unseen product from a demographically similar user."""
    if req.auth is None:
        raise https_fn.HttpsError(
            code=https_fn.FunctionsErrorCode.UNAUTHENTICATED,
            message="You must be logged in.",
        )

    current_uid = req.auth.uid
    db = firestore.client()

    # A catalog item is validated against current eligibility before an event
    # is created. Merely fetching catalog rows does not count as "shown".
    request_data = req.data or {}
    if not isinstance(request_data, dict):
        raise https_fn.HttpsError(
            code=https_fn.FunctionsErrorCode.INVALID_ARGUMENT,
            message="Request data must be an object.",
        )
    requested_source = request_data.get("sourceProductId")
    if requested_source is not None:
        if not isinstance(requested_source, str) or not requested_source.strip():
            raise https_fn.HttpsError(
                code=https_fn.FunctionsErrorCode.INVALID_ARGUMENT,
                message="sourceProductId must be a non-empty string.",
            )
        selected = next(
            (item for item in _eligible_products(db, current_uid)
             if item["sourceProductId"] == requested_source),
            None,
        )
        if selected is None:
            raise https_fn.HttpsError(
                code=https_fn.FunctionsErrorCode.NOT_FOUND,
                message="This recommendation is no longer available.",
            )
        event_ref = db.collection("productEvents").document()
        event_ref.set({
            "eventType": "recommendation_shown",
            "userId": current_uid,
            "sourceProductId": selected["sourceProductId"],
            "createdAt": firestore.SERVER_TIMESTAMP,
            "savedAt": None,
            "savedProductId": None,
        })
        return {"recommendation": {
            "recommendationEventId": event_ref.id,
            **{k: v for k, v in selected.items() if k != "sourceProductId"},
        }}

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
    if not has_valid_demographics(current_user):
        raise https_fn.HttpsError(
            code=https_fn.FunctionsErrorCode.FAILED_PRECONDITION,
            message="Complete your profile before requesting recommendations.",
        )

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

        # Legacy and partially-created profile documents must not make the
        # recommendation request fail for every user. They cannot be ranked
        # reliably, so ignore them until their owners complete their profile.
        if not has_valid_demographics(other_user):
            continue

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
