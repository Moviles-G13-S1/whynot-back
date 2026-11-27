"""Martín's Type 2 BQ. One current products document represents one saved item."""
from datetime import datetime, timedelta, timezone


def count_unpurchased(products, now):
    cutoff = now - timedelta(days=30)
    return sum(
        1 for product in products
        if product.get("purchased") is False
        and isinstance(created := product.get("createdAt"), datetime)
        and created.utcoffset() is not None
        and created < cutoff
    )


def compute_from_firestore(db, params):
    now = datetime.now(timezone.utc)
    documents = db.collection("products").where("purchased", "==", False).select(
        ["createdAt", "purchased"]
    ).stream()
    return {"count": count_unpurchased((doc.to_dict() for doc in documents), now),
            "cutoffUtc": (now - timedelta(days=30)).isoformat()}
