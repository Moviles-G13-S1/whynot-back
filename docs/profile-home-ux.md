# BQ5 and Home UX analytics

## Users with zero products

BQ5 counts users who currently have no saved products. The calculation is in `analytics/bq5_zero_products.py` and is used by `saved_summary` in `analytics/dashboard_views.py`.

It compares Firestore `users` document IDs against product `ownerId` values. Multiple products from the same user count that owner once, and products belonging to nonexistent users do not affect the result.

Purchased products still count while their documents exist. If a user deletes their last product, they return to the zero-product group. This measures the current state, not whether someone has ever saved a product, and uses Firestore profiles rather than Firebase Authentication accounts.

The response field is `zeroProductUsers`. Both existing requests are supported:

- `get_admin_analytics({view: "saved"})` returns the result directly.
- `get_admin_analytics({metric: "saved"})` returns the result under `data`.

## Home interactions

`get_admin_analytics({metric: "home_activation"})` returns interaction counts for the Android Home screen. The response includes `platform: "android"` and an `events` list with `eventName`, `count`, and `distinctUsers`.

The tracked events are:

- `home_empty_state_viewed`
- `home_empty_state_clicked`
- `add_product_navigation`

Counts include all stored events, without a date filter. They measure interactions, not completed product saves or conversion rates.

## Firestore events

Events are stored in `uxEvents` with these required fields:

| Field | Value |
|---|---|
| `userId` | Authenticated user's UID |
| `eventName` | One of the three supported events |
| `source` | `home_empty_state` or `home_bottom_bar` |
| `platform` | `android` |
| `createdAt` | Server timestamp |

Users can create events only for their own UID. Only admins can read events, and client updates and deletes are denied. Authenticated clients can submit repeated events, so these counts should not be treated as tamper-proof.

## Integration

`dashboard_views.py` calls the BQ5 helper, and `endpoint.py` registers the `home_activation` metric. Both metrics use the existing admin authorization. The `uxEvents` rules are defined in `firestore.rules`.

Existing dashboard requests and other business-question calculations remain unchanged. BQ5 keeps its existing response field, while the Home metric is available for integration into the admin interface.

## Testing and deployment

All 77 Python tests passed, including 18 tests covering these additions. Seven Firestore rules tests are also included, but have not been verified in the emulator: the Firebase CLI requires Java 21 or newer, and the test environment had Java 17.

After local validation, deploy `firestore:rules` and `functions:get_admin_analytics` from the agreed branch. Live event storage, admin interface integration, and cross-platform behavior still need to be checked.