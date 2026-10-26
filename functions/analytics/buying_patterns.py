"""Sprint 3 BQ: What are the buying patterns of users based on the products
they have marked as purchased?

Owner: Juan Felipe Sáenz. Type * (2 and 4):
- Type 2, direct user experience improvement: knowing how long a saved
  product takes to be bought, and on which days and times users buy, lets
  the app time reminders and highlights when they are useful.
- Type 4, benefits from data: purchases, conversion, prices and brands per
  category are what partner stores and brands would pay to know.

A purchase is a product that currently exists with `purchased == true`.
Everything time-based uses the selected window (6, 12 or 24 months, counting
the current one) in America/Bogota, like BQ4:

- totalPurchases: purchases whose `purchasedAt` is inside the window.
- conversion: of the products saved inside the window (`createdAt`), how many
  are already purchased, overall and per category.
- timeToPurchase: days from `createdAt` to `purchasedAt` for purchases in the
  window, as median, average, buckets and per category. A negative gap is
  inconsistent data and is counted in `skipped`.
- whenTheyBuy: purchases per weekday and per time of day, with the peaks
  (every tied value is listed).
- spending: median and average price per category and the top brands.
- repeatBuyers: how many purchases each buyer made inside the window.

Limitations:
- Deleted products leave no purchase history, so they are not counted.
- Purchases made before `purchasedAt` existed have no date; they are reported
  in `undatedPurchases` and left out of the window figures.
- `price` is the price the user saved, not a confirmed checkout amount.

Cost: conversion needs every product, so compute_from_firestore reads the whole
`products` collection once (plus `categories` for names). That is fine at the
course's scale; a large deployment would keep a pre-aggregated document.
"""

from datetime import datetime
from statistics import median
from zoneinfo import ZoneInfo

BOGOTA = ZoneInfo("America/Bogota")

DEFAULT_MONTHS_WINDOW = 6
WINDOW_OPTIONS = (6, 12, 24)
TOP_BRANDS = 5

WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
TIMES_OF_DAY = ("morning", "afternoon", "night")


def _text(value):
    return value.strip() if isinstance(value, str) else ""


def _local(moment):
    return moment.astimezone(BOGOTA) if moment.tzinfo else moment


def _months_ago(now, months):
    """The (year, month) that is `months` calendar months before `now`."""
    local = _local(now)
    absolute = local.year * 12 + (local.month - 1) - months
    return absolute // 12, absolute % 12 + 1


def _in_window(moment, oldest_month):
    if not isinstance(moment, datetime):
        return False
    local = _local(moment)
    return (local.year, local.month) >= oldest_month


def _price(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if value >= 0 else None


def _rate(part, whole):
    return round(part / whole, 4) if whole else None


def _round(value, digits):
    return round(value, digits) if value is not None else None


def _median(values):
    return median(values) if values else None


def _average(values):
    return sum(values) / len(values) if values else None


def _time_of_day(hour):
    if 5 <= hour < 12:
        return "morning"
    if 12 <= hour < 18:
        return "afternoon"
    return "night"


def _peaks(counts):
    """Every key tied at the highest non-zero count, sorted; empty if none."""
    top = max(counts.values(), default=0)
    if top == 0:
        return []
    return sorted(key for key, count in counts.items() if count == top)


def is_valid_window(months):
    return type(months) is int and months in WINDOW_OPTIONS


def compute_buying_patterns(products, now, months_window=DEFAULT_MONTHS_WINDOW, categories=None):
    """Build the buying-patterns answer from plain product dictionaries.

    products: iterable of dicts with `ownerId`, `categoryId`, `brand`,
        `price`, `purchased`, `purchasedAt` and `createdAt`.
    now: the moment the window is counted back from.
    months_window: 6, 12 or 24.
    categories: mapping id -> display name, used for labels only.
    """
    if not is_valid_window(months_window):
        raise ValueError("months_window must be 6, 12, or 24.")

    categories = categories or {}
    oldest_month = _months_ago(now, months_window - 1)

    def name(category_id):
        return categories.get(category_id) or category_id

    saved_by_category = {}
    purchased_saved_by_category = {}
    window_purchases = []
    undated = 0

    for product in products:
        category_id = _text(product.get("categoryId")) or "unknown"
        purchased = product.get("purchased") is True

        if _in_window(product.get("createdAt"), oldest_month):
            saved_by_category[category_id] = saved_by_category.get(category_id, 0) + 1
            if purchased:
                purchased_saved_by_category[category_id] = (
                    purchased_saved_by_category.get(category_id, 0) + 1
                )

        if not purchased:
            continue

        purchased_at = product.get("purchasedAt")
        if not isinstance(purchased_at, datetime):
            undated += 1
        elif _in_window(purchased_at, oldest_month):
            window_purchases.append((category_id, product))

    return {
        "monthsWindow": months_window,
        "totalPurchases": len(window_purchases),
        "undatedPurchases": undated,
        "conversion": _conversion(saved_by_category, purchased_saved_by_category, name),
        "timeToPurchase": _time_to_purchase(window_purchases, name),
        "whenTheyBuy": _when_they_buy(window_purchases),
        "spending": _spending(window_purchases, name),
        "repeatBuyers": _repeat_buyers(window_purchases),
    }


def _conversion(saved_by_category, purchased_by_category, name):
    saved = sum(saved_by_category.values())
    purchased = sum(purchased_by_category.values())

    by_category = [
        {
            "categoryId": category_id,
            "categoryName": name(category_id),
            "saved": count,
            "purchased": purchased_by_category.get(category_id, 0),
            "rate": _rate(purchased_by_category.get(category_id, 0), count),
        }
        for category_id, count in saved_by_category.items()
    ]
    by_category.sort(key=lambda item: (-(item["rate"] or 0), -item["saved"], item["categoryId"]))

    return {
        "savedInWindow": saved,
        "purchasedOfThose": purchased,
        "rate": _rate(purchased, saved),
        "byCategory": by_category,
    }


def _time_to_purchase(window_purchases, name):
    days_all = []
    days_by_category = {}
    skipped = 0
    buckets = {"sameDay": 0, "oneToSevenDays": 0, "eightToThirtyDays": 0, "overThirtyDays": 0}

    for category_id, product in window_purchases:
        created_at = product.get("createdAt")
        if not isinstance(created_at, datetime):
            continue

        days = (product["purchasedAt"] - created_at).total_seconds() / 86400
        if days < 0:
            skipped += 1
            continue

        days_all.append(days)
        days_by_category.setdefault(category_id, []).append(days)

        if days < 1:
            buckets["sameDay"] += 1
        elif days <= 7:
            buckets["oneToSevenDays"] += 1
        elif days <= 30:
            buckets["eightToThirtyDays"] += 1
        else:
            buckets["overThirtyDays"] += 1

    return {
        "medianDays": _round(_median(days_all), 1),
        "averageDays": _round(_average(days_all), 1),
        "measured": len(days_all),
        "skipped": skipped,
        "buckets": buckets,
        "byCategory": [
            {
                "categoryId": category_id,
                "categoryName": name(category_id),
                "medianDays": _round(_median(days), 1),
                "count": len(days),
            }
            for category_id, days in sorted(days_by_category.items())
        ],
    }


def _when_they_buy(window_purchases):
    by_weekday = {weekday: 0 for weekday in WEEKDAYS}
    by_time = {time: 0 for time in TIMES_OF_DAY}

    for _, product in window_purchases:
        local = _local(product["purchasedAt"])
        by_weekday[WEEKDAYS[local.weekday()]] += 1
        by_time[_time_of_day(local.hour)] += 1

    return {
        "byWeekday": [{"weekday": day, "purchases": by_weekday[day]} for day in WEEKDAYS],
        "byTimeOfDay": [{"timeOfDay": time, "purchases": by_time[time]} for time in TIMES_OF_DAY],
        "peakWeekday": _peaks(by_weekday),
        "peakTimeOfDay": _peaks(by_time),
    }


def _spending(window_purchases, name):
    prices_by_category = {}
    purchases_by_category = {}
    brand_counts = {}
    brand_spellings = {}

    for category_id, product in window_purchases:
        purchases_by_category[category_id] = purchases_by_category.get(category_id, 0) + 1

        price = _price(product.get("price"))
        if price is not None:
            prices_by_category.setdefault(category_id, []).append(price)

        brand = _text(product.get("brand"))
        if brand:
            key = brand.casefold()
            brand_counts[key] = brand_counts.get(key, 0) + 1
            spellings = brand_spellings.setdefault(key, {})
            spellings[brand] = spellings.get(brand, 0) + 1

    def display(key):
        spellings = brand_spellings[key]
        return sorted(spellings, key=lambda spelling: (-spellings[spelling], spelling))[0]

    top_brands = sorted(brand_counts, key=lambda key: (-brand_counts[key], key))[:TOP_BRANDS]

    return {
        "byCategory": [
            {
                "categoryId": category_id,
                "categoryName": name(category_id),
                "purchases": count,
                "medianPrice": _round(_median(prices_by_category.get(category_id, [])), 2),
                "averagePrice": _round(_average(prices_by_category.get(category_id, [])), 2),
            }
            for category_id, count in sorted(
                purchases_by_category.items(), key=lambda item: (-item[1], item[0])
            )
        ],
        "topBrands": [
            {"brand": display(key), "purchases": brand_counts[key]} for key in top_brands
        ],
    }


def _repeat_buyers(window_purchases):
    per_buyer = {}
    for _, product in window_purchases:
        owner = _text(product.get("ownerId"))
        if owner:
            per_buyer[owner] = per_buyer.get(owner, 0) + 1

    buyers = len(per_buyer)
    two_or_more = sum(1 for count in per_buyer.values() if count >= 2)

    return {
        "buyers": buyers,
        "onePurchase": sum(1 for count in per_buyer.values() if count == 1),
        "twoToThree": sum(1 for count in per_buyer.values() if 2 <= count <= 3),
        "fourOrMore": sum(1 for count in per_buyer.values() if count >= 4),
        "repeatRate": _rate(two_or_more, buyers),
    }


def compute_from_firestore(db, params):
    """Read the products and categories and compute the patterns.

    `params.months` picks the window (default 6).
    """
    months = params.get("months", DEFAULT_MONTHS_WINDOW)
    if not is_valid_window(months):
        from firebase_functions import https_fn

        raise https_fn.HttpsError(
            code=https_fn.FunctionsErrorCode.INVALID_ARGUMENT,
            message="months must be 6, 12, or 24.",
        )

    products = [doc.to_dict() or {} for doc in db.collection("products").stream()]

    categories = {}
    for snapshot in db.collection("categories").stream():
        category_name = _text((snapshot.to_dict() or {}).get("name"))
        if category_name:
            categories[snapshot.id] = category_name

    return compute_buying_patterns(products, datetime.now(BOGOTA), months, categories)
