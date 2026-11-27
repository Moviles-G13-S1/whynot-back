"""Sprint 4 BQ: What is the average loading time of the Home screen per platform?

Owner: Miguel Velandia. Type 1 (app telemetry): it measures how the app
performs, not what users do, and it is the number the Home micro-optimization
is judged by.

Data: each app writes one `screenLoadEvents` document every time Home finishes
loading while online: `screen == "home"`, `durationMs` (from opening Home until
its nearby store and recommendation finished loading, measured with a monotonic
clock), `platform` and the server `createdAt`.

Definitions:
- averageMs per platform is the answer to the BQ. medianMs and p90Ms are given
  because a few very slow loads (a cold Cloud Function, a slow GPS fix) pull the
  average up; the median shows the typical load.
- `days` limits the window to the last 7 or 30 days; without it, every event
  counts.

Limitations:
- Only loads that started online are recorded (offline, Home skips the network).
- A load recorded offline is sent when Firestore syncs again, with that time.
"""

from datetime import datetime, timedelta, timezone

SCREEN = "home"
PLATFORMS = ("android", "ios")
ALLOWED_DAYS = (7, 30)
MAX_DURATION_MS = 120_000


def _valid(event):
    duration = event.get("durationMs") if isinstance(event, dict) else None
    return (
        isinstance(event, dict)
        and event.get("screen") == SCREEN
        and event.get("platform") in PLATFORMS
        and type(duration) in (int, float)
        and 0 < duration <= MAX_DURATION_MS
    )


def _percentile(sorted_values, fraction):
    """Nearest-rank percentile of an already sorted, non-empty list."""
    rank = max(1, round(fraction * len(sorted_values) + 0.5 - 1e-9))
    return sorted_values[min(rank, len(sorted_values)) - 1]


def _stats(durations):
    if not durations:
        return {
            "loads": 0,
            "averageMs": None,
            "medianMs": None,
            "p90Ms": None,
            "fastestMs": None,
            "slowestMs": None,
        }
    ordered = sorted(durations)
    count = len(ordered)
    middle = count // 2
    median = ordered[middle] if count % 2 else (ordered[middle - 1] + ordered[middle]) / 2
    return {
        "loads": count,
        "averageMs": round(sum(ordered) / count, 1),
        "medianMs": round(median, 1),
        "p90Ms": _percentile(ordered, 0.9),
        "fastestMs": ordered[0],
        "slowestMs": ordered[-1],
    }


def compute_home_load_time(events, now=None, days=None):
    """Average Home load time per platform from `screenLoadEvents` dicts."""
    if days is not None and (type(days) is not int or days not in ALLOWED_DAYS):
        raise ValueError("days must be 7 or 30")

    since = None
    if days is not None:
        end = now or datetime.now(timezone.utc)
        since = end - timedelta(days=days)

    per_platform = {platform: [] for platform in PLATFORMS}
    ignored = 0
    for event in events:
        if not _valid(event):
            ignored += 1
            continue
        created_at = event.get("createdAt")
        if since is not None and (not isinstance(created_at, datetime) or created_at < since):
            continue
        per_platform[event["platform"]].append(event["durationMs"])

    platforms = [{"platform": platform, **_stats(per_platform[platform])} for platform in PLATFORMS]
    measured = [row for row in platforms if row["loads"]]
    fastest = min(measured, key=lambda row: row["averageMs"])["platform"] if len(measured) > 1 else None

    return {
        "screen": SCREEN,
        "days": days,
        "overall": _stats([duration for durations in per_platform.values() for duration in durations]),
        "platforms": platforms,
        "fastestPlatform": fastest,
        "ignoredEvents": ignored,
    }


def compute_from_firestore(db, params):
    """Read Home's load events and summarize them. `params.days` is optional (7 or 30)."""
    days = (params or {}).get("days")
    try:
        events = [
            doc.to_dict() or {}
            # Single-field equality filter: no composite index needed.
            for doc in db.collection("screenLoadEvents").where("screen", "==", SCREEN).stream()
        ]
        return compute_home_load_time(events, days=days)
    except ValueError as error:
        from firebase_functions import https_fn

        raise https_fn.HttpsError(
            code=https_fn.FunctionsErrorCode.INVALID_ARGUMENT,
            message=str(error),
        )
