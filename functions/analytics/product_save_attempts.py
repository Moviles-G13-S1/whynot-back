"""Product-save attempts recorded by the mobile clients (BQ Type 2).

Every time a user tries to save a product, the app writes one document to
`productSaveEvents`: `outcome` is `success`, or `failure` with a short
`reason` code (for example `invalid_price` or `backend_error`). This module
summarizes them so the admin dashboard can show how often saving works and
why it fails, per platform.
"""

PLATFORMS = ("android", "ios")


def _text(value):
    return value.strip() if isinstance(value, str) else ""


def compute_save_attempts(events):
    """Summarize save-attempt event dicts (`platform`, `outcome`, `reason`)."""
    per_platform = {platform: {"successes": 0, "failures": 0} for platform in PLATFORMS}
    reasons = {}

    for event in events:
        outcome = event.get("outcome")
        if outcome not in ("success", "failure"):
            continue

        platform = _text(event.get("platform"))
        counts = per_platform.setdefault(platform, {"successes": 0, "failures": 0})

        if outcome == "success":
            counts["successes"] += 1
        else:
            counts["failures"] += 1
            reason = _text(event.get("reason")) or "unknown"
            reasons[reason] = reasons.get(reason, 0) + 1

    successes = sum(counts["successes"] for counts in per_platform.values())
    failures = sum(counts["failures"] for counts in per_platform.values())
    total = successes + failures

    return {
        "totalAttempts": total,
        "successes": successes,
        "failures": failures,
        "successRate": successes * 100.0 / total if total else None,
        "platforms": [
            {"platform": platform, **counts}
            for platform, counts in per_platform.items()
        ],
        "failureReasons": [
            {"reason": reason, "count": count}
            for reason, count in sorted(reasons.items(), key=lambda item: (-item[1], item[0]))
        ],
    }


def compute_from_firestore(db, params):
    """Read every save attempt and summarize it. `params` is ignored."""
    events = [
        doc.to_dict() or {}
        for doc in db.collection("productSaveEvents").stream()
    ]
    return compute_save_attempts(events)
