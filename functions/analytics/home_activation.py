"""Martin's Home UX interactions; these counts are not the BQ5 answer."""

EVENTS = ("home_empty_state_viewed", "home_empty_state_clicked", "add_product_navigation")
SOURCES = ("home_empty_state", "home_bottom_bar")


def summarize_home_activation(events):
    counts = {name: 0 for name in EVENTS}
    users = {name: set() for name in EVENTS}
    for event in events:
        name = event.get("eventName")
        uid = event.get("userId")
        if (name not in counts or event.get("platform") != "android"
                or event.get("source") not in SOURCES
                or not isinstance(uid, str) or not uid):
            continue
        counts[name] += 1
        users[name].add(uid)
    return {
        "platform": "android",
        "events": [
            {"eventName": name, "count": counts[name], "distinctUsers": len(users[name])}
            for name in EVENTS
        ],
    }


def compute_from_firestore(db, params):
    events = (doc.to_dict() or {} for doc in db.collection("uxEvents").stream())
    return summarize_home_activation(events)
