"""Jerónimo's Sprint 4 Type 2 BQ: missing image/link in current products.

Only field presence is measured. Non-empty strings count as present without
URL validation or network requests. Purchased products remain saved products.
"""


def _has_text(value):
    return isinstance(value, str) and bool(value.strip())


def compute_product_completeness(products):
    total = missing_image = missing_link = missing_both = 0
    for product in products:
        total += 1
        no_image = not _has_text(product.get("imageUrl"))
        no_link = not _has_text(product.get("productUrl"))
        missing_image += no_image
        missing_link += no_link
        missing_both += no_image and no_link

    incomplete = missing_image + missing_link - missing_both

    def percentage(count):
        return count / total * 100 if total else None

    return {
        "totalProducts": total,
        "missingImageCount": missing_image,
        "missingImagePercentage": percentage(missing_image),
        "missingProductUrlCount": missing_link,
        "missingProductUrlPercentage": percentage(missing_link),
        "missingBothCount": missing_both,
        "incompleteCount": incomplete,
        "incompletePercentage": percentage(incomplete),
    }


def compute_from_firestore(db, params):
    documents = db.collection("products").select(["imageUrl", "productUrl"]).stream()
    return compute_product_completeness(doc.to_dict() or {} for doc in documents)
