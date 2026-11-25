"""Sprint 4 BQ: How many users open a nearby store's detail per week?

Owner: Juan Felipe Sáenz. Type 3 (new feature usage): the Nearby Store detail
is a feature added to the Home; counting the distinct users who open it each
week tells whether the feature is used and worth improving.

Data: both apps write one `uxEvents` document with
`eventName == "nearby_store_detail_opened"` and `source == "home_nearby_store"`
every time the user opens the nearby store's detail from the Home.

Definitions:
- A week is a Monday-to-Sunday calendar week in America/Bogota, like BQ7.
- distinctUsers: users who opened the detail at least once that week. A user
  who opens it ten times in a week counts once; that is the answer to the BQ.
- opens: every recorded open, kept to show how often each user returns.

Limitations:
- Only opens recorded after the event existed are counted.
- An open made offline is recorded when Firestore syncs it again.
"""

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

ZONE = ZoneInfo("America/Bogota")
EVENT_NAME = "nearby_store_detail_opened"
SOURCE = "home_nearby_store"
PLATFORMS = ("android", "ios")
ALLOWED_WEEKS = (4, 8, 12)


def window(now=None, weeks=8):
    """Monday 00:00 of the first week in the window, and the end instant."""
    if type(weeks) is not int or weeks not in ALLOWED_WEEKS:
        raise ValueError("weeks must be 4, 8, or 12")
    end = now or datetime.now(timezone.utc)
    if end.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    local = end.astimezone(ZONE)
    monday = (local - timedelta(days=local.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return monday - timedelta(weeks=weeks - 1), local


def _valid(event):
    return (
        isinstance(event, dict)
        and event.get("eventName") == EVENT_NAME
        and event.get("source") == SOURCE
        and event.get("platform") in PLATFORMS
        and isinstance(event.get("userId"), str)
        and bool(event["userId"].strip())
        and isinstance(event.get("createdAt"), datetime)
        and event["createdAt"].tzinfo is not None
    )


def summarize(events, now=None, weeks=8):
    start, end = window(now, weeks)
    users_by_week = [set() for _ in range(weeks)]
    opens_by_week = [0] * weeks
    users_by_platform = {platform: set() for platform in PLATFORMS}
    ignored = 0

    for event in events:
        if not _valid(event):
            ignored += 1
            continue
        occurred = event["createdAt"].astimezone(ZONE)
        if not start <= occurred <= end:
            continue
        index = (occurred.date() - start.date()).days // 7
        user_id = event["userId"]
        users_by_week[index].add(user_id)
        opens_by_week[index] += 1
        users_by_platform[event["platform"]].add(user_id)

    counts = [len(users) for users in users_by_week]
    maximum = max(counts, default=0)
    all_users = set().union(*users_by_week)

    return {
        "timezone": "America/Bogota",
        "windowWeeks": weeks,
        "periodStart": start.isoformat(),
        "periodEnd": end.isoformat(),
        "currentWeekUsers": counts[-1],
        "previousWeekUsers": counts[-2] if weeks > 1 else 0,
        "averageWeeklyUsers": round(sum(counts) / weeks, 2),
        "distinctUsersInWindow": len(all_users),
        "totalOpens": sum(opens_by_week),
        "ignoredInvalidRecords": ignored,
        "weeks": [
            {
                "weekStart": (start + timedelta(weeks=i)).date().isoformat(),
                "label": (start + timedelta(weeks=i)).strftime("%d %b"),
                "distinctUsers": count,
                "opens": opens_by_week[i],
                "barPercent": round(count * 100 / maximum, 2) if maximum else 0,
                "partial": i == weeks - 1,
            }
            for i, count in enumerate(counts)
        ],
        "byPlatform": [
            {"platform": platform, "distinctUsers": len(users_by_platform[platform])}
            for platform in PLATFORMS
        ],
    }


def compute_from_firestore(db, params):
    from firebase_functions import https_fn
    from google.cloud.firestore_v1.base_query import FieldFilter

    weeks = params.get("weeks", 8)
    now = datetime.now(timezone.utc)
    try:
        start, end = window(now, weeks)
    except ValueError as error:
        raise https_fn.HttpsError(
            https_fn.FunctionsErrorCode.INVALID_ARGUMENT, str(error)
        ) from error

    # Single-field equality query: no composite index needed. The time
    # window is applied in memory by summarize().
    query = db.collection("uxEvents").where(
        filter=FieldFilter("eventName", "==", EVENT_NAME)
    )
    events = (doc.to_dict() or {} for doc in query.stream())
    return summarize(events, now=now, weeks=weeks)
