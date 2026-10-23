"""Santiago's supporting Wishlist UX metric from intentional interactions."""

from collections import Counter, defaultdict


def summarize(events):
    # One operation ID contributes at most once, even if imported data repeats it.
    seen = set()
    actions = defaultdict(lambda: {"outcomes": Counter(), "users": set(), "failureReasons": Counter()})
    for _, event in events:
        if event.get("schemaVersion") != 1:
            continue
        operation = event.get("operationId")
        action = event.get("action")
        outcome = event.get("outcome")
        if not operation or operation in seen or action not in ("create_form_open", "create_form_cancel", "create", "open", "edit", "delete") or outcome not in ("intent", "success", "failure", "blocked"):
            continue
        seen.add(operation)
        row = actions[action]
        row["outcomes"][outcome] += 1
        if event.get("userId"):
            row["users"].add(event["userId"])
        if outcome in ("failure", "blocked"):
            row["failureReasons"][event.get("reason") or "unknown"] += 1
    result = {}
    for action, row in sorted(actions.items()):
        outcomes = dict(row["outcomes"])
        attempts = sum(outcomes.get(key, 0) for key in ("success", "failure", "blocked"))
        result[action] = {
            "outcomes": outcomes,
            "total": sum(outcomes.values()),
            "uniqueUsers": len(row["users"]),
            "successRate": round(100 * outcomes.get("success", 0) / attempts, 1) if attempts else None,
            "failureReasons": dict(row["failureReasons"]),
        }
    return {"schemaVersion": 1, "actions": result, "totalEvents": len(seen)}


def compute_from_firestore(db, params):
    return summarize((doc.id, doc.to_dict() or {}) for doc in db.collection("wishlistInteractionEvents").stream())
