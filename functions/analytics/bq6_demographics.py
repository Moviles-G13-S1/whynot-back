"""BQ6: What is the demographic profile of the average buyer per category?

Buyers are the owners of products marked as purchased, joined with their
`users/{uid}` profile. A user counts once per category no matter how many
products they bought in it. This mirrors the Kotlin admin dashboard
(AdminInsightsController.calculateDemographicProfile) so both clients can
show the same numbers.
"""

UNKNOWN_CITY = "unknown"
OTHER_CITIES = "other"
UNKNOWN_GENDER = "Unknown"
TOP_CITIES = 4

# The same age groups the recommendation feature uses to score similarity.
AGE_GROUPS = [
    ("13–17", 13, 17),
    ("18–24", 18, 24),
    ("25–34", 25, 34),
    ("35–44", 35, 44),
    ("45+", 45, 200),
]


def _text(value):
    return value.strip() if isinstance(value, str) else ""


def _age(profile):
    age = profile.get("age")
    if isinstance(age, bool) or not isinstance(age, int):
        return 0
    return age


def _city_id(profile):
    return _text(profile.get("cityId")) or UNKNOWN_CITY


def _median_age(buyers):
    ages = sorted(age for age in (_age(b) for b in buyers) if age > 0)
    if not ages:
        return None

    middle = len(ages) // 2
    if len(ages) % 2 == 1:
        return ages[middle]
    return (ages[middle - 1] + ages[middle]) // 2


def _age_groups(buyers):
    return [
        {
            "label": label,
            "userCount": sum(1 for b in buyers if low <= _age(b) <= high),
        }
        for label, low, high in AGE_GROUPS
    ]


def _genders(buyers):
    counts = {}
    for buyer in buyers:
        gender = _text(buyer.get("gender")) or UNKNOWN_GENDER
        counts[gender] = counts.get(gender, 0) + 1

    total = len(buyers)
    shares = [
        {
            "gender": gender,
            "userCount": count,
            "percentage": count * 100.0 / total if total else 0.0,
        }
        for gender, count in counts.items()
    ]
    shares.sort(key=lambda share: (-share["userCount"], share["gender"]))
    return shares


def _top_cities(buyers, city_names):
    counts = {}
    for buyer in buyers:
        city_id = _city_id(buyer)
        counts[city_id] = counts.get(city_id, 0) + 1

    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))

    def share(city_id, count, name=None):
        entry = {"cityId": city_id, "userCount": count}
        name = name or city_names.get(city_id)
        if name:
            entry["cityName"] = name
        return entry

    if len(ranked) <= TOP_CITIES:
        return [share(city_id, count) for city_id, count in ranked]

    leading = [share(city_id, count) for city_id, count in ranked[:TOP_CITIES]]
    rest = sum(count for _, count in ranked[TOP_CITIES:])
    return leading + [share(OTHER_CITIES, rest, name="Other cities")]


def compute_demographic_profile(products, users, categories=None, cities=None):
    """Build the BQ6 profile from plain dictionaries.

    products: iterable of product dicts (`ownerId`, `categoryId`, `purchased`).
    users: mapping uid -> profile dict. Owners without a profile are skipped.
    categories / cities: mapping id -> display name, used for labels only.
    """
    categories = categories or {}
    cities = cities or {}

    buyer_ids_by_category = {}
    for product in products:
        if product.get("purchased") is not True:
            continue

        owner_id = _text(product.get("ownerId"))
        category_id = _text(product.get("categoryId"))
        if not owner_id or not category_id or owner_id not in users:
            continue

        buyer_ids_by_category.setdefault(category_id, set()).add(owner_id)

    category_profiles = []
    for category_id, buyer_ids in buyer_ids_by_category.items():
        buyers = [users[uid] for uid in sorted(buyer_ids)]
        category_profiles.append({
            "categoryId": category_id,
            "categoryName": categories.get(category_id) or category_id,
            "buyers": len(buyers),
            "medianAge": _median_age(buyers),
            "ageGroups": _age_groups(buyers),
            "genders": _genders(buyers),
            "topCities": _top_cities(buyers, cities),
        })

    category_profiles.sort(key=lambda c: (-c["buyers"], c["categoryId"]))

    all_buyer_ids = set().union(*buyer_ids_by_category.values())

    return {
        "categories": category_profiles,
        "totalBuyers": len(all_buyer_ids),
        "profilesWithoutCity": sum(
            1 for uid in all_buyer_ids
            if not _text(users[uid].get("cityId"))
        ),
    }


def compute_from_firestore(db, params):
    """Read only what BQ6 needs and compute it.

    Purchased products come from a single-field equality query, so no
    composite index is needed. Only the profiles of their owners are read.
    """
    products = [
        doc.to_dict() or {}
        for doc in db.collection("products")
        .where("purchased", "==", True)
        .stream()
    ]

    owner_ids = sorted({
        _text(product.get("ownerId"))
        for product in products
        if _text(product.get("ownerId"))
    })

    users = {}
    if owner_ids:
        refs = [db.collection("users").document(uid) for uid in owner_ids]
        for snapshot in db.get_all(refs):
            if snapshot.exists:
                users[snapshot.id] = snapshot.to_dict() or {}

    categories = _names(db.collection("categories").stream())
    cities = _names(db.collection("cities").stream())

    return compute_demographic_profile(products, users, categories, cities)


def _names(snapshots):
    names = {}
    for snapshot in snapshots:
        name = _text((snapshot.to_dict() or {}).get("name"))
        if name:
            names[snapshot.id] = name
    return names
