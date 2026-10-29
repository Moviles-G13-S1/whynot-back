"""Jerónimo's Type 1 BQ: captured technical app errors per Bogotá calendar week."""

import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

ZONE = ZoneInfo("America/Bogota")
FEATURES = {"auth", "home", "profile", "runtime"}
CODES = {"network", "permission", "unauthenticated", "not_found", "rate_limited", "timeout", "unexpected"}
SOURCES = {"operation", "framework", "platform"}
PLATFORMS = {"ios", "android", "web"}
ID = re.compile(r"^[0-9a-f]{32}$")
OPERATION = re.compile(r"^[a-z_]{1,48}$")


def _allowed(value, choices):
    return isinstance(value, str) and value in choices


def window(now=None, weeks=8):
    if type(weeks) is not int or weeks not in (4, 8, 12):
        raise ValueError("weeks must be 4, 8, or 12")
    end = now or datetime.now(timezone.utc)
    if end.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    local = end.astimezone(ZONE)
    monday = (local - timedelta(days=local.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    return monday - timedelta(weeks=weeks - 1), end.astimezone(ZONE)


def summarize(events, now=None, weeks=8):
    start, end = window(now, weeks)
    counts = [0] * weeks
    features, codes, platforms, sources = Counter(), Counter(), Counter(), Counter()
    seen = set()
    ignored = 0
    for document_id, event in events:
        if not isinstance(event, dict):
            ignored += 1
            continue
        occurred = event.get("occurredAt")
        if (not isinstance(document_id, str) or not ID.fullmatch(document_id)
                or event.get("eventId") != document_id
                or type(event.get("schemaVersion")) is not int or event["schemaVersion"] != 1
                or not _allowed(event.get("feature"), FEATURES) or not _allowed(event.get("code"), CODES)
                or not _allowed(event.get("platform"), PLATFORMS) or not _allowed(event.get("source"), SOURCES)
                or not isinstance(event.get("operation"), str) or not OPERATION.fullmatch(event["operation"])
                or not isinstance(event.get("userId"), str) or not event["userId"]
                or not isinstance(occurred, datetime) or occurred.tzinfo is None):
            ignored += 1
            continue
        occurred = occurred.astimezone(ZONE)
        if not start <= occurred <= end or document_id in seen:
            continue
        seen.add(document_id)
        index = (occurred.date() - start.date()).days // 7
        counts[index] += 1
        features[event["feature"]] += 1
        codes[event["code"]] += 1
        platforms[event["platform"]] += 1
        sources[event["source"]] += 1
    maximum = max(counts, default=0)

    def breakdown(counter):
        return [{"key": key, "count": count} for key, count in sorted(counter.items(), key=lambda item: (-item[1], item[0]))]

    return {
        "schemaVersion": 1, "timezone": "America/Bogota", "windowWeeks": weeks,
        "periodStart": start.isoformat(), "periodEnd": end.isoformat(),
        "totalErrors": sum(counts), "currentWeekErrors": counts[-1],
        "previousWeekErrors": counts[-2], "ignoredInvalidRecords": ignored,
        "weeks": [{
            "weekStart": (start + timedelta(weeks=i)).date().isoformat(),
            "label": (start + timedelta(weeks=i)).strftime("%d %b"),
            "count": count, "barPercent": round(count * 100 / maximum, 2) if maximum else 0,
            "partial": i == weeks - 1,
        } for i, count in enumerate(counts)],
        "byFeature": breakdown(features), "byCode": breakdown(codes),
        "byPlatform": breakdown(platforms), "bySource": breakdown(sources),
    }


def compute_from_firestore(db, params):
    from google.cloud.firestore_v1.base_query import FieldFilter
    from firebase_functions import https_fn

    weeks = params.get("weeks", 8)
    now = datetime.now(timezone.utc)
    try:
        start, end = window(now, weeks)
    except ValueError as error:
        raise https_fn.HttpsError(https_fn.FunctionsErrorCode.INVALID_ARGUMENT, str(error)) from error
    query = db.collection("applicationErrorEvents").where(filter=FieldFilter("occurredAt", ">=", start))
    query = query.where(filter=FieldFilter("occurredAt", "<=", end))
    return summarize(((doc.id, doc.to_dict() or {}) for doc in query.stream()), now=now, weeks=weeks)
