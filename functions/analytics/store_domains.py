"""Sprint 4 BQ: Which online stores (link domains) appear most in saved products?

Owner: Santiago Casasbuenas. Type 4, benefits from data: knowing which stores
WhyNot users save products from, and how often those products are bought, is
information partner stores and brands would pay for.

Data: current `products` documents. A product has no store field; the store is
the domain of its optional `productUrl`. The `stores` collection (physical
stores used by Nearby) only provides readable names for domains that match a
store's `websiteUrl`.

Definitions:
- domain: the registrable domain of `productUrl`, lowercased, so
  `https://www2.hm.com/es_co/...` and `hm.com/...` are both `hm.com`, and
  `https://www.falabella.com.co/...` is `falabella.com.co`.
- products per store: current products whose link has that domain.
- users per store: distinct owners of those products.
- purchased per store: those products already marked as purchased.
- link coverage: products with a usable link / all current products.

Limitations:
- Products without a link, or with a link that is not a web address, cannot
  be attributed to a store; they are reported apart, never guessed.
- Short links (for example `bit.ly`) are counted under the shortener's domain.
- Deleted products are not in `products`, so they are not counted.
- The domain rule knows a fixed list of two-level country suffixes
  (`com.co`, `co.uk`, ...), not the full public suffix list.

Cost: one read of `products`, `stores` and `categories`.
"""

from urllib.parse import urlsplit

DEFAULT_LIMIT = 10
MAX_LIMIT = 50

# Second-level suffixes under which the registrable domain has three labels.
MULTI_LABEL_SUFFIXES = {
    "com.co", "net.co", "org.co", "edu.co", "gov.co",
    "com.mx", "com.ar", "com.br", "com.pe", "com.ec", "com.uy", "com.ve",
    "co.uk", "org.uk", "co.jp", "com.au", "com.es", "com.cn",
}


def _text(value):
    return value.strip() if isinstance(value, str) else ""


def normalize_domain(url):
    """Return the registrable domain of a product link, or None if unusable."""
    text = _text(url)
    if not text or any(char.isspace() for char in text):
        return None
    if "://" not in text:
        text = f"https://{text}"
    try:
        parts = urlsplit(text)
        host = parts.hostname
    except ValueError:
        return None
    if parts.scheme.lower() not in ("http", "https") or not host:
        return None
    # "user@host" is not a product page (it is how "mailto:x@store.com" parses).
    if parts.username is not None:
        return None

    host = host.lower().rstrip(".")
    labels = host.split(".")
    if len(labels) < 2 or any(not label for label in labels):
        return None
    # IP addresses and hosts without a real top-level domain are not stores.
    if all(label.isdigit() for label in labels) or not labels[-1].isalpha():
        return None

    if len(labels) >= 3 and ".".join(labels[-2:]) in MULTI_LABEL_SUFFIXES:
        return ".".join(labels[-3:])
    return ".".join(labels[-2:])


def _common_prefix_words(names):
    words = [name.split() for name in names]
    prefix = []
    for column in zip(*words):
        if all(word == column[0] for word in column):
            prefix.append(column[0])
        else:
            break
    return " ".join(prefix)


def store_names_by_domain(stores):
    """Map domain -> readable brand name from seeded `stores` documents.

    Store names follow "Brand - Mall"; older ones are "Brand Mall". The brand
    is the part before " - ", or the words shared by every store of a domain.
    """
    names_by_domain = {}
    for store in stores:
        domain = normalize_domain(store.get("websiteUrl"))
        name = _text(store.get("name"))
        if domain and name:
            names_by_domain.setdefault(domain, []).append(name)

    result = {}
    for domain, names in names_by_domain.items():
        brands = sorted({name.split(" - ")[0].strip() for name in names if " - " in name})
        if brands:
            result[domain] = brands[0]
        else:
            result[domain] = _common_prefix_words(names) or sorted(names)[0]
    return result


def _limit(params):
    value = (params or {}).get("limit", DEFAULT_LIMIT)
    if isinstance(value, bool) or not isinstance(value, int):
        return DEFAULT_LIMIT
    return max(1, min(MAX_LIMIT, value))


def _percent(part, whole):
    return round(part / whole * 100, 1) if whole else None


def compute_store_domains(products, stores=(), categories=None, limit=DEFAULT_LIMIT):
    """Rank link domains among current products.

    products: iterable of product dicts (`productUrl`, `ownerId`, `purchased`,
    `categoryId`). stores: iterable of store dicts (`name`, `websiteUrl`).
    categories: mapping id -> display name, for labels only.
    """
    categories = categories or {}
    names = store_names_by_domain(stores)

    total = 0
    without_link = 0
    invalid_link = 0
    per_domain = {}
    per_category = {}

    for product in products:
        total += 1
        url = _text(product.get("productUrl"))
        if not url:
            without_link += 1
            continue
        domain = normalize_domain(url)
        if domain is None:
            invalid_link += 1
            continue

        row = per_domain.setdefault(domain, {"products": 0, "owners": set(), "purchased": 0})
        row["products"] += 1
        owner = _text(product.get("ownerId"))
        if owner:
            row["owners"].add(owner)
        if product.get("purchased") is True:
            row["purchased"] += 1

        category_id = _text(product.get("categoryId"))
        if category_id:
            counts = per_category.setdefault(category_id, {})
            counts[domain] = counts.get(domain, 0) + 1

    linked = sum(row["products"] for row in per_domain.values())

    def describe(domain, row):
        return {
            "domain": domain,
            "name": names.get(domain) or domain,
            "knownStore": domain in names,
            "products": row["products"],
            "users": len(row["owners"]),
            "purchased": row["purchased"],
            "purchasedPercentage": _percent(row["purchased"], row["products"]),
            "share": _percent(row["products"], linked),
        }

    ranked = sorted(
        per_domain.items(),
        key=lambda item: (-item[1]["products"], -len(item[1]["owners"]), item[0]),
    )
    top = [describe(domain, row) for domain, row in ranked[:limit]]
    rest = ranked[limit:]

    leaders = []
    for category_id in sorted(per_category):
        counts = per_category[category_id]
        best = max(counts.values())
        tied = sorted(domain for domain, count in counts.items() if count == best)
        leaders.append({
            "categoryId": category_id,
            "categoryName": categories.get(category_id) or category_id,
            "products": best,
            "stores": [{"domain": domain, "name": names.get(domain) or domain} for domain in tied],
        })

    return {
        "totalProducts": total,
        "linkedProducts": linked,
        "withoutLink": without_link,
        "invalidLink": invalid_link,
        "linkCoverage": _percent(linked, total),
        "distinctStores": len(per_domain),
        "knownStores": sum(1 for domain in per_domain if domain in names),
        "limit": limit,
        "stores": top,
        "otherStores": {
            "stores": len(rest),
            "products": sum(row["products"] for _, row in rest),
        },
        "categoryLeaders": leaders,
    }


def compute_from_firestore(db, params):
    """Read current products, seeded stores and category names."""
    products = [doc.to_dict() or {} for doc in db.collection("products").stream()]
    stores = [doc.to_dict() or {} for doc in db.collection("stores").stream()]
    categories = {}
    for doc in db.collection("categories").stream():
        name = _text((doc.to_dict() or {}).get("name"))
        if name:
            categories[doc.id] = name
    return compute_store_domains(products, stores, categories, _limit(params))
