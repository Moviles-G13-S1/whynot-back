"""Demographic product recommendation logic."""

from collections import Counter, deque

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
    """Rank unseen products across preferred and personally saved categories."""
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

    current_products = [
        doc.to_dict()
        for doc in db.collection("products").where("ownerId", "==", current_uid).stream()
    ]
    current_keys = {_get_product_key(product) for product in current_products}
    category_counts = Counter(
        product["categoryId"]
        for product in current_products
        if isinstance(product.get("categoryId"), str)
        and product["categoryId"].strip()
    )
    preferred_category = current_user["preferredCategoryId"]
    categories = [preferred_category] + sorted(
        (category for category in category_counts if category != preferred_category),
        key=lambda category: (-category_counts[category], category),
    )
    candidates_by_category = {category: deque() for category in categories}
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

    seen = set(current_keys)
    for _score, _age_difference, owner_id in ranked_users:
        products = []
        for doc in db.collection("products").where("ownerId", "==", owner_id).stream():
            product = doc.to_dict()
            if product.get("categoryId") not in candidates_by_category:
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
            candidates_by_category[product["categoryId"]].append({
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
    # Santiago Casasbuenas: Interleave the user's active categories so a
    # strong fashion match cannot hide every technology result at the bottom.
    found = []
    while any(candidates_by_category.values()):
        for category in categories:
            if candidates_by_category[category]:
                found.append(candidates_by_category[category].popleft())
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
    if requested_source is not None and (
        not isinstance(requested_source, str) or not requested_source.strip()
    ):
        raise https_fn.HttpsError(
            code=https_fn.FunctionsErrorCode.INVALID_ARGUMENT,
            message="sourceProductId must be a non-empty string.",
        )
    event_only = request_data.get("eventOnly", False)
    if not isinstance(event_only, bool) or (event_only and requested_source is None):
        raise https_fn.HttpsError(
            code=https_fn.FunctionsErrorCode.INVALID_ARGUMENT,
            message="eventOnly requires a sourceProductId and must be boolean.",
        )

    candidates = _eligible_products(db, current_uid)
    selected = (
        next(
            (item for item in candidates
             if item["sourceProductId"] == requested_source),
            None,
        )
        if requested_source is not None
        else (candidates[0] if candidates else None)
    )
    if selected is None:
        if requested_source is not None:
            raise https_fn.HttpsError(
                code=https_fn.FunctionsErrorCode.NOT_FOUND,
                message="This recommendation is no longer available.",
            )
        return {
            "recommendation": None,
            "message": "No similar user has a new product in your categories.",
        }

    event_ref = db.collection("productEvents").document()
    event_ref.set({
        "eventType": "recommendation_shown",
        "userId": current_uid,
        "sourceProductId": selected["sourceProductId"],
        "createdAt": firestore.SERVER_TIMESTAMP,
        "savedAt": None,
        "savedProductId": None,
    })
    if event_only:
        return {"recommendation": {"recommendationEventId": event_ref.id}}
    return {"recommendation": {
        "recommendationEventId": event_ref.id,
        **{key: value for key, value in selected.items()
           if key != "sourceProductId"},
    }}
