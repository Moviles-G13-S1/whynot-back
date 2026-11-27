"""Sprint 4 - Errors vs. saved products.

Business Question:
Is there a relationship between the number of errors a user
experiences and the number of products they save?
"""

from collections import Counter
from datetime import datetime, timezone
from statistics import correlation, mean

from . import weekly_app_errors


def is_valid_string(value):
    return isinstance(value, str) and bool(value.strip())


def is_valid_timestamp(value):
    return (
        isinstance(value, datetime)
        and value.tzinfo is not None
        and value.utcoffset() is not None
    )


def is_valid_error(document_id, event):
    """Use the same error validation criteria as Weekly App Errors."""

    if not isinstance(event, dict):
        return False

    return (
        isinstance(document_id, str)
        and weekly_app_errors.ID.fullmatch(document_id) is not None
        and event.get("eventId") == document_id
        and type(event.get("schemaVersion")) is int
        and event["schemaVersion"] == 1
        and weekly_app_errors._allowed(
            event.get("feature"), weekly_app_errors.FEATURES
        )
        and weekly_app_errors._allowed(
            event.get("code"), weekly_app_errors.CODES
        )
        and weekly_app_errors._allowed(
            event.get("platform"), weekly_app_errors.PLATFORMS
        )
        and weekly_app_errors._allowed(
            event.get("source"), weekly_app_errors.SOURCES
        )
        and isinstance(event.get("operation"), str)
        and weekly_app_errors.OPERATION.fullmatch(
            event["operation"]
        ) is not None
        and is_valid_string(event.get("userId"))
        and is_valid_timestamp(event.get("occurredAt"))
    )


def compute_errors_vs_saved_products(
    users,
    errors,
    products,
    now=None,
    weeks=8,
):
    """Calculate the relationship between errors and saved products."""

    # Reuse the same calendar window as Jeronimo's Sprint 3 BQ.
    start, end = weekly_app_errors.window(now, weeks)

    # Identify registered users, including users with zero records.
    user_ids = set()

    for user_id, user in users:
        if not is_valid_string(user_id):
            continue

        if not isinstance(user, dict):
            continue

        created_at = user.get("createdAt")

        if not is_valid_timestamp(created_at):
            continue

        if created_at <= end:
            user_ids.add(user_id)

    error_counts = Counter()
    product_counts = Counter()

    seen_errors = set()
    seen_products = set()

    ignored_errors = 0
    ignored_products = 0

    # Count valid application errors per user.
    for document_id, event in errors:

        if not is_valid_error(document_id, event):
            ignored_errors += 1
            continue

        if document_id in seen_errors:
            continue

        user_id = event["userId"]
        occurred_at = event["occurredAt"]

        if user_id not in user_ids:
            continue

        if not start <= occurred_at <= end:
            continue

        seen_errors.add(document_id)
        error_counts[user_id] += 1

    # Count existing products created during the same period.
    for document_id, product in products:

        if not is_valid_string(document_id):
            ignored_products += 1
            continue

        if not isinstance(product, dict):
            ignored_products += 1
            continue

        if document_id in seen_products:
            continue

        owner_id = product.get("ownerId")
        created_at = product.get("createdAt")

        if (
            not is_valid_string(owner_id)
            or not is_valid_timestamp(created_at)
        ):
            ignored_products += 1
            continue

        if owner_id not in user_ids:
            continue

        if not start <= created_at <= end:
            continue

        seen_products.add(document_id)
        product_counts[owner_id] += 1

    # Join both collections using the Firebase Authentication UID.
    # Do not expose user identifiers in the analytics response.
    points = [
        {
            "errors": error_counts[user_id],
            "products": product_counts[user_id],
        }
        for user_id in user_ids
    ]

    points.sort(
        key=lambda point: (point["errors"], point["products"])
    )

    errors_per_user = [
        point["errors"] for point in points
    ]

    products_per_user = [
        point["products"] for point in points
    ]

    user_count = len(points)

    # Pearson correlation requires at least two observations
    # and nonconstant values in both variables.
    coefficient = None

    if user_count == 0:
        status = "empty"

    elif (
        user_count < 2
        or len(set(errors_per_user)) < 2
        or len(set(products_per_user)) < 2
    ):
        status = "insufficient_variation"

    else:
        coefficient = correlation(
            errors_per_user,
            products_per_user,
        )

        status = "available"

    return {
        "schemaVersion": 1,
        "timezone": "America/Bogota",
        "windowWeeks": weeks,
        "periodStart": start.isoformat(),
        "periodEnd": end.isoformat(),

        "status": status,
        "userCount": user_count,

        "totalErrors": sum(errors_per_user),
        "totalProducts": sum(products_per_user),

        "averageErrorsPerUser": (
            round(mean(errors_per_user), 2)
            if user_count else 0
        ),

        "averageProductsPerUser": (
            round(mean(products_per_user), 2)
            if user_count else 0
        ),

        "usersWithErrors": sum(
            count > 0 for count in errors_per_user
        ),

        "usersWithoutErrors": sum(
            count == 0 for count in errors_per_user
        ),

        "usersWithProducts": sum(
            count > 0 for count in products_per_user
        ),

        "usersWithoutProducts": sum(
            count == 0 for count in products_per_user
        ),

        "correlation": (
            round(coefficient, 4)
            if coefficient is not None else None
        ),

        "ignoredInvalidErrors": ignored_errors,
        "ignoredInvalidProducts": ignored_products,

        "points": points,
    }


def compute_from_firestore(db, params):
    """Read Firestore records and calculate the business question."""

    from google.cloud.firestore_v1.base_query import FieldFilter
    from firebase_functions import https_fn

    weeks = params.get("weeks", 8)
    now = datetime.now(timezone.utc)

    try:
        start, end = weekly_app_errors.window(now, weeks)

    except ValueError as error:
        raise https_fn.HttpsError(
            https_fn.FunctionsErrorCode.INVALID_ARGUMENT,
            str(error),
        ) from error

    # Registered users.
    users = db.collection("users")

    # Application errors collected by Jeronimo's Sprint 3 feature.
    errors = (
        db.collection("applicationErrorEvents")
        .where(filter=FieldFilter("occurredAt", ">=", start))
        .where(filter=FieldFilter("occurredAt", "<=", end))
    )

    # Products created within the same time window.
    products = (
        db.collection("products")
        .where(filter=FieldFilter("createdAt", ">=", start))
        .where(filter=FieldFilter("createdAt", "<=", end))
    )

    return compute_errors_vs_saved_products(
        users=(
            (doc.id, doc.to_dict() or {})
            for doc in users.stream()
        ),
        errors=(
            (doc.id, doc.to_dict() or {})
            for doc in errors.stream()
        ),
        products=(
            (doc.id, doc.to_dict() or {})
            for doc in products.stream()
        ),
        now=now,
        weeks=weeks,
    )