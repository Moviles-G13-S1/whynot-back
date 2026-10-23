"""Web dashboard views for the team's business questions.

The demographic view is a legacy view of current product owners. It is not
BQ6, which Juan Felipe Sáenz implements for purchased-product buyers in
``bq6_demographics.py``.
"""

from collections import Counter
from datetime import datetime
from statistics import median
from zoneinfo import ZoneInfo

from .bq5_zero_products import count_zero_product_users

BOGOTA = ZoneInfo("America/Bogota")


def _read_collection(db, name):
    """Load source records shared by the dashboard's BQ calculations."""
    return [(doc.id, doc.to_dict() or {}) for doc in db.collection(name).stream()]


def saved_summary(products, profiles):
    """BQ1 (Jerónimo Franco), BQ2 (Juliana Durán), and BQ5 (Martín Riveira).

    Report saved-product counts, users with 2+ products, and users with none.
    """

    # Count how many products each user currently has saved.
    # The ownerId field identifies the user who owns each product.
    counts = Counter(data.get("ownerId", "") for _, data in products)

    buckets = [0] * 5
    for count in counts.values():
        buckets[0 if count <= 5 else 1 if count <= 10 else 2 if count <= 20 else 3 if count <= 50 else 4] += 1

    # BQ2 — How many users save another product after their first one?
    # Responsible: Juliana Durán
    #
    # We want to count users with at least two currently saved products.
    #
    # Step 1: Count users who have at least one saved product.
    active = len(counts)

    # Step 2: Count users who have exactly one saved product.
    singles = sum(count == 1 for count in counts.values())

    # Step 3: Subtract single-product users from active users.
    # The result represents users with two or more saved products.
    # This measures current saved products, not historical save events.

    return {
        "activeUsers": active,
        "zeroProductUsers": count_zero_product_users(counts.keys(), profiles),
        "totalProducts": len(products),
        "singleProductUsers": singles,

        # BQ2 (Juliana Durán): Users with 2+ currently saved products.
        "multipleProductUsers": active - singles,

        "averagePerActiveUser": len(products) / active if active else 0,
        "distributionCounts": buckets,
    }


def recommended_summary(events, now=None):
    """BQ3 (Santiago Casasbuenas): summarize recommendation-save events.

    Count successful saves even if their product was later deleted. All
    conversion and chart calculations stay in the backend.
    """
    now = now or datetime.now(BOGOTA)
    months = []
    for offset in range(5, -1, -1):
        absolute_month = now.year * 12 + now.month - 1 - offset
        months.append(f"{absolute_month // 12:04d}-{absolute_month % 12 + 1:02d}")
    month_counts = Counter()
    shown = 0
    saved = 0
    undated = 0
    savers = set()

    for _, data in events:
        if data.get("eventType") != "recommendation_shown":
            continue
        shown += 1
        if not (
            data.get("savedAt") is not None
            and isinstance(data.get("savedProductId"), str)
            and bool(data["savedProductId"])
        ):
            continue
        saved += 1
        user_id = data.get("userId")
        if isinstance(user_id, str) and user_id:
            savers.add(user_id)
        saved_at = data["savedAt"]
        if not isinstance(saved_at, datetime):
            undated += 1
            continue
        local_date = saved_at.astimezone(BOGOTA) if saved_at.tzinfo else saved_at
        month = f"{local_date.year:04d}-{local_date.month:02d}"
        if month in months:
            month_counts[month] += 1

    peak = max((month_counts[month] for month in months), default=0)
    return {
        "total": saved,
        "recommendationsShown": shown,
        "saveRatePercent": round(saved * 100 / shown, 1) if shown else 0,
        "distinctSavers": len(savers),
        "undatedSaves": undated,
        "monthlySaves": [
            {
                "month": month,
                "label": datetime.strptime(month, "%Y-%m").strftime("%b %Y"),
                "count": month_counts[month],
                "barPercent": round(month_counts[month] * 100 / peak, 1) if peak else 0,
            }
            for month in months
        ],
    }


def purchased_summary(products, now, window_months):
    """BQ4 chart (Miguel Velandia): monthly purchased-product counts by category.

    The exact top-category BQ4 answer is in bq4_purchases_by_category.py.
    """
    months = []
    for offset in range(window_months - 1, -1, -1):
        absolute_month = now.year * 12 + now.month - 1 - offset
        months.append(f"{absolute_month // 12:04d}-{absolute_month % 12 + 1:02d}")
    counts = {}
    totals = [0] * window_months
    for _, product in products:
        date = product.get("purchasedAt")
        if product.get("purchased") is not True or not isinstance(date, datetime):
            continue
        local_date = date.astimezone(BOGOTA) if date.tzinfo else date
        key = f"{local_date.year:04d}-{local_date.month:02d}"
        if key not in months:
            continue
        index = months.index(key)
        category = product.get("categoryId", "")
        counts.setdefault(category, [0] * window_months)[index] += 1
        totals[index] += 1
    peak = max(totals, default=0)
    return {
        "months": months,
        "categories": [{"categoryId": key, "monthlyCounts": counts[key]} for key in sorted(counts)],
        "monthlyTotals": totals,
        "chartMaximum": max(3, (peak + 2) // 3 * 3),
        "currentMonthCount": totals[-1],
        "previousMonthCount": totals[-2],
    }


def demographic_summary(category_id, products, profiles, cities):
    """Legacy demographic view of current product owners; no assigned BQ.

    BQ6 (Juan Felipe Sáenz) instead profiles purchased-product buyers.
    """
    owner_ids = {p.get("ownerId") for _, p in products if p.get("categoryId") == category_id}
    users = [p for uid, p in profiles if uid in owner_ids]
    total = len(users)
    ages = sorted(p.get("age", 0) for p in users)
    middle = median(ages) if ages else None
    median_age = "—" if middle is None else str(int(middle)) if middle == int(middle) else str(middle)
    age_counts = [0] * 6
    gender_counts = Counter()
    city_counts = Counter()
    for user in users:
        age = user.get("age", 0)
        age_counts[0 if age <= 17 else 1 if age <= 24 else 2 if age <= 34 else 3 if age <= 44 else 4 if age <= 54 else 5] += 1
        gender_counts[user.get("gender")] += 1
        city_counts[user.get("cityId") or "other"] += 1

    def group(label, count):
        """Format one segment of the legacy demographic view."""
        return {"label": label, "count": count, "percent": (count * 100 + total // 2) // total if total else 0}

    city_names = {uid: data.get("name", uid) for uid, data in cities}
    ranked = sorted(((uid, count) for uid, count in city_counts.items() if uid != "other" and uid in city_names), key=lambda pair: (-pair[1], pair[0]))[:4]
    other = total - sum(count for _, count in ranked)
    return {
        "userCount": total,
        "medianAge": median_age,
        "ages": [group(label, age_counts[index]) for index, label in enumerate(["13–17", "18–24", "25–34", "35–44", "45–54", "55+"])],
        "genders": [group("Women", gender_counts["Female"]), group("Men", gender_counts["Male"]), group("Other", gender_counts["Other"])],
        "cities": [group(city_names[uid], count) for uid, count in ranked] + [group("Other / unknown", other)],
    }



def compute_saved(db, params):
    """Load BQ1 (Jerónimo), BQ2 (Juliana), and BQ5 (Martín) inputs."""
    return saved_summary(_read_collection(db, "products"), _read_collection(db, "users"))


def compute_recommended(db, params):
    """Load BQ3 recommendation events (Santiago Casasbuenas)."""
    return recommended_summary(_read_collection(db, "productEvents"))


def compute_purchased(db, params):
    """Load the BQ4 supporting purchase chart (Miguel Velandia)."""
    from firebase_functions import https_fn

    months = params.get("months", 6)
    if type(months) is not int or months not in (6, 12, 24):
        raise https_fn.HttpsError(
            code=https_fn.FunctionsErrorCode.INVALID_ARGUMENT,
            message="Months must be 6, 12, or 24.",
        )
    return purchased_summary(_read_collection(db, "products"), datetime.now(BOGOTA), months)


def compute_demographic(db, params):
    """Load the legacy owner profile, distinct from Juan Felipe's BQ6."""
    from firebase_functions import https_fn

    categories = _read_collection(db, "categories")
    if not categories:
        return {"categories": [], "categoryId": None}
    category_id = params.get("categoryId") or categories[0][0]
    if not isinstance(category_id, str) or category_id not in {uid for uid, _ in categories}:
        raise https_fn.HttpsError(
            code=https_fn.FunctionsErrorCode.INVALID_ARGUMENT,
            message="Unknown category.",
        )
    result = demographic_summary(
        category_id,
        _read_collection(db, "products"),
        _read_collection(db, "users"),
        _read_collection(db, "cities"),
    )
    result["categories"] = [
        {"id": uid, "name": item.get("name", uid)}
        for uid, item in categories
    ]
    result["categoryId"] = category_id
    return result
