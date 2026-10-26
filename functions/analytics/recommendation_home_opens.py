"""Type 3: visible Flutter Home recommendation cards opened in detail.

The window is a rolling 30 x 24 hour UTC window ending at generation time.
Both events must arrive within it.
"""

import re
from datetime import datetime, timedelta, timezone

_ID = re.compile(r"^[0-9a-f]{32}$")


def _time(value):
    if not isinstance(value, datetime) or value.tzinfo is None:
        return None
    return value.astimezone(timezone.utc)


def summarize(events, now=None):
    end = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    start = end - timedelta(days=30)
    displays = {}
    opens = {}
    for document_id, event in events:
        if not isinstance(event, dict) or event.get("platform") != "flutter":
            continue
        impression = event.get("impressionId")
        user = event.get("userId")
        recommendation = event.get("recommendationEventId")
        event_type = event.get("eventType")
        occurred = _time(event.get("createdAt"))
        if (not isinstance(impression, str) or not _ID.fullmatch(impression)
                or not isinstance(user, str) or not user
                or not isinstance(recommendation, str) or not recommendation
                or len(recommendation) > 128 or occurred is None
                or not start <= occurred <= end):
            continue
        suffix = {"card_displayed": "display", "detail_opened": "open"}.get(event_type)
        if suffix is None or document_id != f"{impression}_{suffix}":
            continue
        target = displays if event_type == "card_displayed" else opens
        # Duplicate imports are resolved deterministically to the earliest event.
        old = target.get(impression)
        if old is None or occurred < old[0]:
            target[impression] = (occurred, user, recommendation)
    numerator = sum(
        1 for impression, (opened_at, user, recommendation) in opens.items()
        if impression in displays
        and displays[impression][0] <= opened_at
        and displays[impression][1:] == (user, recommendation)
    )
    denominator = len(displays)
    return {
        "schemaVersion": 1,
        "periodStart": start.isoformat(),
        "periodEnd": end.isoformat(),
        "numerator": numerator,
        "denominator": denominator,
        "percentage": round(numerator / denominator * 100, 1) if denominator else None,
    }


def compute_from_firestore(db, params):
    return summarize((doc.id, doc.to_dict() or {}) for doc in db.collection("recommendationHomeEvents").stream())
