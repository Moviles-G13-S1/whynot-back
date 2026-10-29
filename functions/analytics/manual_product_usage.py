"""Martin's Sprint 3 BQ: manual entry among current saved products."""

from .core_saving_features import compute_core_saving_features


def compute_manual_product_usage(products, events):
    classified = compute_core_saving_features([], products, events)
    counts = {item["id"]: item["count"] for item in classified["features"]}
    manual = counts["manual_product"]
    recommended = counts["recommended_product"]
    known = manual + recommended
    return {
        "manualProducts": manual,
        "recommendedProducts": recommended,
        "classifiedProducts": known,
        "unclassifiedProducts": classified["unclassifiedProducts"],
        "totalCurrentProducts": classified["totalCurrentProducts"],
        "manualPercentage": round(manual / known * 100, 1) if known else None,
    }


def compute_from_firestore(db, params):
    products = [(doc.id, doc.to_dict() or {})
                for doc in db.collection("products").stream()]
    events = [(doc.id, doc.to_dict() or {})
              for doc in db.collection("productEvents").stream()]
    return compute_manual_product_usage(products, events)
