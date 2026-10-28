"""Sprint 3 BQ: How much money have users saved on the products they marked as
purchased in the app?

Owner: Miguel Velandia. Type 2, direct user experience improvement: knowing
whether people actually pay less than the price they saved shows whether
WhyNot helps them wait for a better price, and which categories it helps most.

Data: when a user marks a product as purchased, the app asks what they paid and
writes one `productPurchaseEvents/{productId}` document with

- referencePrice: the price the product was saved with (the price the user
  expected to pay), checked by the rules against the product itself;
- purchasePrice: what the user says they actually paid.

The saved product price alone cannot tell savings apart, which is why the
price paid is recorded at the moment of purchase.

Definitions:
- saving of one purchase = referencePrice - purchasePrice. It is negative when
  the user paid more than the saved price.
- netSaved: the sum of every saving, so overpaying offsets savings. This is the
  answer to the BQ.
- grossSaved / overspent: the positive and negative parts kept apart.
- savingRate: netSaved as a percentage of the total reference price.

Limitations:
- The price paid is what the user types; it is not a verified checkout.
- Purchases marked before this event existed have no price paid and are not
  counted.
- Events are history: deleting the product later does not remove its saving.

Cost: one read of `productPurchaseEvents` (plus `categories` for names).
"""

PLATFORMS = ("android", "ios")


def _text(value):
    return value.strip() if isinstance(value, str) else ""


def _price(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if value >= 0 else None


def _round(value):
    return round(value, 2)


def _rate(part, whole):
    return _round(part * 100.0 / whole) if whole else None


def _average(total, count):
    return _round(total / count) if count else None


def compute_purchase_savings(events, categories=None):
    """Build the BQ answer from purchase-event dicts.

    events: iterable of dicts with `userId`, `categoryId`, `platform`,
        `referencePrice` and `purchasePrice`. Events with a missing or negative
        price are skipped and counted in `skipped`.
    categories: mapping id -> display name, used for labels only.
    """
    categories = categories or {}

    purchases = 0
    skipped = 0
    buyers = set()
    reference_total = 0.0
    paid_total = 0.0
    gross_saved = 0.0
    overspent = 0.0
    saved_count = 0
    same_count = 0
    overpaid_count = 0
    by_category = {}
    by_platform = {platform: {"purchases": 0, "netSaved": 0.0} for platform in PLATFORMS}

    for event in events:
        reference = _price(event.get("referencePrice"))
        paid = _price(event.get("purchasePrice"))
        if reference is None or paid is None:
            skipped += 1
            continue

        saving = reference - paid
        purchases += 1
        reference_total += reference
        paid_total += paid

        user_id = _text(event.get("userId"))
        if user_id:
            buyers.add(user_id)

        if saving > 0:
            saved_count += 1
            gross_saved += saving
        elif saving < 0:
            overpaid_count += 1
            overspent += -saving
        else:
            same_count += 1

        category_id = _text(event.get("categoryId"))
        category = by_category.setdefault(
            category_id, {"purchases": 0, "referenceTotal": 0.0, "netSaved": 0.0}
        )
        category["purchases"] += 1
        category["referenceTotal"] += reference
        category["netSaved"] += saving

        platform = _text(event.get("platform"))
        platform_totals = by_platform.setdefault(platform, {"purchases": 0, "netSaved": 0.0})
        platform_totals["purchases"] += 1
        platform_totals["netSaved"] += saving

    net_saved = reference_total - paid_total

    categories_out = [
        {
            "categoryId": category_id,
            "categoryName": categories.get(category_id) or category_id,
            "purchases": totals["purchases"],
            "netSaved": _round(totals["netSaved"]),
            "savingRate": _rate(totals["netSaved"], totals["referenceTotal"]),
        }
        for category_id, totals in by_category.items()
    ]
    categories_out.sort(key=lambda c: (-c["netSaved"], c["categoryId"]))

    return {
        "purchases": purchases,
        "buyers": len(buyers),
        "referenceTotal": _round(reference_total),
        "paidTotal": _round(paid_total),
        "netSaved": _round(net_saved),
        "grossSaved": _round(gross_saved),
        "overspent": _round(overspent),
        "savingRate": _rate(net_saved, reference_total),
        "averageSavedPerPurchase": _average(net_saved, purchases),
        "averageSavedPerBuyer": _average(net_saved, len(buyers)),
        "savedPurchases": saved_count,
        "samePricePurchases": same_count,
        "overpaidPurchases": overpaid_count,
        "byCategory": categories_out,
        "byPlatform": [
            {
                "platform": platform,
                "purchases": totals["purchases"],
                "netSaved": _round(totals["netSaved"]),
            }
            for platform, totals in by_platform.items()
        ],
        "skipped": skipped,
    }


def compute_from_firestore(db, params):
    """Read every purchase event and the category names. `params` is ignored."""
    events = [
        doc.to_dict() or {}
        for doc in db.collection("productPurchaseEvents").stream()
    ]
    categories = _names(db.collection("categories").stream())
    return compute_purchase_savings(events, categories)


def _names(snapshots):
    names = {}
    for snapshot in snapshots:
        name = _text((snapshot.to_dict() or {}).get("name"))
        if name:
            names[snapshot.id] = name
    return names
