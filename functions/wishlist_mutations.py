"""Owner-scoped wishlist deletion with a product guard and one outcome event."""

from firebase_admin import firestore
from firebase_functions import https_fn
from datetime import datetime, timedelta, timezone


def delete_empty_wishlist(req):
    uid = getattr(getattr(req, "auth", None), "uid", None)
    if not uid:
        raise https_fn.HttpsError(https_fn.FunctionsErrorCode.UNAUTHENTICATED, "Sign in required.")
    data = req.data if isinstance(req.data, dict) else {}
    wishlist_id, operation_id, platform = (data.get(key) for key in ("wishlistId", "operationId", "platform"))
    if (not isinstance(wishlist_id, str) or not 0 < len(wishlist_id) <= 128
            or not isinstance(operation_id, str) or not 0 < len(operation_id) <= 128
            or platform not in ("android", "ios", "web")):
        raise https_fn.HttpsError(https_fn.FunctionsErrorCode.INVALID_ARGUMENT, "Invalid delete request.")

    db = firestore.client()
    wishlist = db.collection("wishlists").document(wishlist_id)
    event = db.collection("wishlistInteractionEvents").document(operation_id)

    @firestore.transactional
    def reserve(transaction):
        previous = event.get(transaction=transaction)
        if previous.exists:
            prior = previous.to_dict()
            if prior.get("userId") != uid or prior.get("action") != "delete" or prior.get("wishlistId") != wishlist_id:
                raise https_fn.HttpsError(https_fn.FunctionsErrorCode.ALREADY_EXISTS, "Operation ID already used.")
            return {"outcome": prior["outcome"], "reason": prior["reason"]}, None
        document = wishlist.get(transaction=transaction)
        if not document.exists or document.to_dict().get("ownerId") != uid:
            return None, None
        fields = document.to_dict()
        if fields.get("deleting") and fields.get("deleteOperationId") != operation_id:
            reserved_at = fields.get("deleteReservedAt")
            if reserved_at is not None and datetime.now(timezone.utc) - reserved_at < timedelta(minutes=2):
                raise https_fn.HttpsError(https_fn.FunctionsErrorCode.ABORTED, "Deletion in progress. Retry shortly.")
        transaction.update(wishlist, {"deleting": True, "deleteOperationId": operation_id, "deleteReservedAt": firestore.SERVER_TIMESTAMP})
        return None, fields.get("categoryId")

    previous, category_id = reserve(db.transaction())
    if previous:
        return previous

    @firestore.transactional
    def finish(transaction):
        existing = event.get(transaction=transaction)
        if existing.exists:
            fields = existing.to_dict()
            return {"outcome": fields["outcome"], "reason": fields["reason"]}
        document = wishlist.get(transaction=transaction)
        if category_id is None:
            outcome, reason = "failure", "not_found"
        elif not document.exists or document.to_dict().get("deleteOperationId") != operation_id:
            raise https_fn.HttpsError(https_fn.FunctionsErrorCode.ABORTED, "Deletion changed. Retry shortly.")
        else:
            # The committed marker blocks new product writes before this query.
            occupied = list(db.collection("products").where("wishlistId", "==", wishlist_id).limit(1).stream(transaction=transaction))
            outcome, reason = ("blocked", "nonempty") if occupied else ("success", "none")
            if occupied:
                transaction.update(wishlist, {"deleting": firestore.DELETE_FIELD, "deleteOperationId": firestore.DELETE_FIELD, "deleteReservedAt": firestore.DELETE_FIELD})
            else:
                transaction.delete(wishlist)
        payload = {
            "action": "delete", "outcome": outcome, "reason": reason,
            "userId": uid, "wishlistId": wishlist_id, "platform": platform,
            "operationId": operation_id, "schemaVersion": 1,
            "createdAt": firestore.SERVER_TIMESTAMP,
        }
        if category_id:
            payload["categoryId"] = category_id
        transaction.create(event, payload)
        return {"outcome": outcome, "reason": reason}

    return finish(db.transaction())
