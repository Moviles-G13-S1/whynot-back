"""BQ4: Which category has the highest number of products marked as purchased
per month?

A purchase is a product that currently exists with `purchased == true`; its
month comes from `purchasedAt`. This is the calculation the Kotlin admin
dashboard ran in AdminInsightsController.calculatePurchasedProductsStats,
moved to the backend so every client gets the same answer:

- Only months inside the selected window (6, 12 or 24 months, counting the
  current one) are reported, newest first, and only if they have purchases.
- Every category tied at the highest count is reported, so a tie is shown as
  a tie instead of one category being picked arbitrarily.
- Purchases made before `purchasedAt` existed have no month. They are counted
  in `undatedPurchases` instead of being silently dropped.

Months are calendar months in America/Bogota, the zone the Kotlin devices and
the web dashboard use.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

BOGOTA = ZoneInfo("America/Bogota")

DEFAULT_MONTHS_WINDOW = 6

# The windows the admin screens offer.
WINDOW_OPTIONS = (6, 12, 24)

MONTH_NAMES = (
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
)


def _text(value):
    return value.strip() if isinstance(value, str) else ""


def _local(moment):
    return moment.astimezone(BOGOTA) if moment.tzinfo else moment


def _year_month(moment):
    local = _local(moment)
    return local.year, local.month


def _months_ago(now, months):
    """The (year, month) that is `months` calendar months before `now`."""
    local = _local(now)
    absolute = local.year * 12 + (local.month - 1) - months
    return absolute // 12, absolute % 12 + 1


def _tied_at_max(counts):
    """Every category with the highest count, sorted; empty without counts."""
    if not counts:
        return []

    top = max(counts.values())
    return sorted(category for category, count in counts.items() if count == top)


def is_valid_window(months):
    return type(months) is int and months in WINDOW_OPTIONS


def compute_purchases_by_category(products, now, months_window=DEFAULT_MONTHS_WINDOW, categories=None):
    """Build the BQ4 answer from plain dictionaries.

    products: iterable of product dicts (`purchased`, `purchasedAt`,
        `categoryId`).
    now: the moment the window is counted back from.
    months_window: 6, 12 or 24.
    categories: mapping id -> display name, used for labels only.
    """
    if not is_valid_window(months_window):
        raise ValueError("months_window must be 6, 12, or 24.")

    categories = categories or {}

    def name(category_id):
        return categories.get(category_id) or category_id

    dated = []
    undated = 0

    for product in products:
        if product.get("purchased") is not True:
            continue

        moment = product.get("purchasedAt")
        if not isinstance(moment, datetime):
            undated += 1
            continue

        dated.append((_text(product.get("categoryId")), _year_month(moment)))

    oldest_allowed = _months_ago(now, months_window - 1)
    in_window = [
        (category_id, year_month)
        for category_id, year_month in dated
        if year_month >= oldest_allowed
    ]

    counts_by_month = {}
    for category_id, year_month in in_window:
        counts = counts_by_month.setdefault(year_month, {})
        counts[category_id] = counts.get(category_id, 0) + 1

    months = []
    for (year, month) in sorted(counts_by_month, reverse=True):
        counts = counts_by_month[(year, month)]
        top_ids = _tied_at_max(counts)

        by_category = sorted(counts.items(), key=lambda item: (-item[1], item[0]))

        months.append({
            "year": year,
            "month": month,
            "label": f"{MONTH_NAMES[month - 1]} {year}",
            "totalPurchases": sum(counts.values()),
            "topCategoryIds": top_ids,
            "topCategoryNames": [name(category_id) for category_id in top_ids],
            "topCategoryPurchases": max(counts.values()),
            "byCategory": [
                {
                    "categoryId": category_id,
                    "categoryName": name(category_id),
                    "purchases": count,
                }
                for category_id, count in by_category
            ],
        })

    overall_counts = {}
    for category_id, _ in in_window:
        overall_counts[category_id] = overall_counts.get(category_id, 0) + 1

    overall_top_ids = _tied_at_max(overall_counts)

    return {
        "months": months,
        "totalPurchases": len(in_window),
        "undatedPurchases": undated,
        "overallTopCategoryIds": overall_top_ids,
        "overallTopCategoryNames": [name(category_id) for category_id in overall_top_ids],
        "monthsWindow": months_window,
    }


def compute_from_firestore(db, params):
    """Read only what BQ4 needs and compute it.

    `params.months` picks the window (default 6). Purchased products come from
    a single-field equality query, so no composite index is needed.
    """
    months = params.get("months", DEFAULT_MONTHS_WINDOW)
    if not is_valid_window(months):
        from firebase_functions import https_fn

        raise https_fn.HttpsError(
            code=https_fn.FunctionsErrorCode.INVALID_ARGUMENT,
            message="months must be 6, 12, or 24.",
        )

    products = [
        doc.to_dict() or {}
        for doc in db.collection("products")
        .where("purchased", "==", True)
        .stream()
    ]

    categories = _names(db.collection("categories").stream())

    return compute_purchases_by_category(
        products,
        datetime.now(BOGOTA),
        months,
        categories,
    )


def _names(snapshots):
    names = {}
    for snapshot in snapshots:
        name = _text((snapshot.to_dict() or {}).get("name"))
        if name:
            names[snapshot.id] = name
    return names
