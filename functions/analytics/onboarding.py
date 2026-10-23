"""Onboarding funnel recorded by the mobile clients (BQ Type 2).

When a user finishes signing up, and later when they create their first
wishlist, the app writes one document to `onboardingEvents` with the `step`
it reached. The document id is `{userId}_{step}`, so each user counts at
most once per step.

This module turns those events, plus the saved products, into a funnel:
how many new users sign up, how many go on to create a wishlist, and how
many save their first product.
"""

PLATFORMS = ("android", "ios")

SIGN_UP = "sign_up_completed"
FIRST_WISHLIST = "first_wishlist_created"


def _text(value):
    return value.strip() if isinstance(value, str) else ""


def _rate(part, whole):
    return part * 100.0 / whole if whole else None


def compute_onboarding(events, product_owner_ids):
    """Summarize onboarding event dicts (`userId`, `platform`, `step`).

    `product_owner_ids` holds the `ownerId` of every saved product, so the
    last funnel step counts signed-up users who own at least one product.
    """
    signed_up = {}
    with_wishlist = set()

    for event in events:
        user_id = _text(event.get("userId"))
        if not user_id:
            continue

        step = event.get("step")
        if step == SIGN_UP:
            signed_up[user_id] = _text(event.get("platform"))
        elif step == FIRST_WISHLIST:
            with_wishlist.add(user_id)

    owners = {_text(owner) for owner in product_owner_ids}

    sign_ups = len(signed_up)
    wishlist_users = len(with_wishlist & signed_up.keys())
    product_users = len(owners & signed_up.keys())

    per_platform = {platform: 0 for platform in PLATFORMS}
    for platform in signed_up.values():
        per_platform[platform] = per_platform.get(platform, 0) + 1

    return {
        "signUps": sign_ups,
        "createdFirstWishlist": wishlist_users,
        "savedFirstProduct": product_users,
        "wishlistRate": _rate(wishlist_users, sign_ups),
        "productRate": _rate(product_users, sign_ups),
        "platforms": [
            {"platform": platform, "signUps": count}
            for platform, count in per_platform.items()
        ],
    }


def compute_from_firestore(db, params):
    """Read the onboarding events and product owners. `params` is ignored."""
    events = [
        doc.to_dict() or {}
        for doc in db.collection("onboardingEvents").stream()
    ]
    owners = [
        (doc.to_dict() or {}).get("ownerId")
        for doc in db.collection("products").stream()
    ]
    return compute_onboarding(events, owners)
