# Admin analytics

The admin dashboards get their business-question (BQ) metrics from one
callable function, `get_admin_analytics`. It reads Firestore with the Admin
SDK, so clients never need broad read access to compute a metric.

## Contract

Request data:

```json
{ "metric": "saved", "params": {} }
```

- `metric` (string, required): a key of `METRICS` in
  `functions/analytics/endpoint.py`.
- `params` (object, optional): passed unchanged to the metric. BQ6 ignores it.

Response:

```json
{ "metric": "saved", "generatedAt": "2026-10-20T02:10:00.000000+00:00", "data": { } }
```

Errors:

| Code | When |
|---|---|
| `unauthenticated` | The caller is not signed in |
| `permission-denied` | The ID token lacks the `admin: true` custom claim |
| `invalid-argument` | `metric` is missing, not a string, or unknown, or `params` is not an object |

Authorization uses the same custom claim as `isAdmin()` in `firestore.rules`
(see [authentication.md](authentication.md)). A user who was just made admin
must refresh their ID token before the call succeeds.

The metric keys are:

| `metric` | `params` | Source |
|---|---|---|
| `saved` | `{}` | Current `products` and `users` (BQ1, BQ2, BQ5) |
| `recommended` | `{}` | Successful `productEvents` (BQ3) |
| `purchased` | `{ "months": 6 }` (6, 12, or 24) | Current purchased `products` (BQ4) |
| `demographic` | `{ "categoryId": "..." }` (optional) | Current product owners, profiles, categories, and cities, matching the Flutter screen |
| `bq6` | `{}` | Purchased-product buyers, matching the separate Kotlin BQ6 implementation |

The four web view calculators live in `functions/analytics/dashboard_views.py`.
The existing web dashboard can also send `{ "view": "saved" }` (with `months`
or `categoryId` at the top level) and receives the metric data directly. This
compatibility path uses the same admin check and calculators.
The web `demographic` view and `bq6` answer different questions because the
existing Flutter screen includes owners of current products whether or not a
product was purchased.

## Calling it

Web or Flutter (JavaScript SDK shown):

```js
import { getFunctions, httpsCallable } from "firebase/functions";

const functions = getFunctions(app, "us-central1");
const result = await httpsCallable(functions, "get_admin_analytics")({ metric: "bq6" });
console.log(result.data.data.categories);
```

Android (Kotlin):

```kotlin
FirebaseFunctions.getInstance("us-central1")
    .getHttpsCallable("get_admin_analytics")
    .call(mapOf("metric" to "bq6"))
    .await()
```

## BQ6: demographic profile of the average buyer per category

A buyer is the owner of a product with `purchased == true`, joined with their
`users/{uid}` profile. A user counts once per category however many products
they bought in it. Owners without a profile are skipped.

```json
{
  "categories": [
    {
      "categoryId": "tech",
      "categoryName": "Technology",
      "buyers": 12,
      "medianAge": 27,
      "ageGroups": [
        { "label": "13–17", "userCount": 0 },
        { "label": "18–24", "userCount": 4 },
        { "label": "25–34", "userCount": 6 },
        { "label": "35–44", "userCount": 2 },
        { "label": "45+", "userCount": 0 }
      ],
      "genders": [
        { "gender": "Female", "userCount": 7, "percentage": 58.33 },
        { "gender": "Male", "userCount": 5, "percentage": 41.67 }
      ],
      "topCities": [
        { "cityId": "bogota", "cityName": "Bogotá", "userCount": 6 },
        { "cityId": "unknown", "userCount": 2 },
        { "cityId": "other", "cityName": "Other cities", "userCount": 1 }
      ]
    }
  ],
  "totalBuyers": 20,
  "profilesWithoutCity": 3
}
```

- `categories` is sorted by `buyers` (descending), then `categoryId`.
  `categoryName` falls back to the id.
- `medianAge` uses ages above 0. With an even count it is the floor of the
  average of the two middle ages. It is `null` when no buyer has an age.
- `ageGroups` always lists all five groups.
- `genders` uses `Unknown` for a blank gender. `percentage` is the share of the
  category's buyers and is not rounded.
- `topCities` keeps the four largest cities and merges the rest into
  `cityId: "other"`. Buyers without a `cityId` are counted under `unknown`.
  `cityName` is present when the city is in the catalog.
- `totalBuyers` and `profilesWithoutCity` count distinct buyers across all
  categories.

The logic lives in `compute_demographic_profile()` in
`functions/analytics/bq6_demographics.py`. It uses plain dictionaries and
mirrors the Kotlin admin dashboard. The Firestore read uses a single-field
equality query (`purchased == true`), so it needs no composite index.

## Adding a BQ

1. Create `functions/analytics/bqN_<name>.py` with
   `compute_from_firestore(db, params)`. It must return JSON-serializable data
   (convert timestamps to strings). Keep the computation in a pure function so
   it can be unit-tested without Firestore.
2. Register it in `functions/analytics/endpoint.py`:

   ```python
   from . import bqN_name

   METRICS = {
       "bq6": bq6_demographics.compute_from_firestore,
       "bqN": bqN_name.compute_from_firestore,
   }
   ```

3. Add `tests/test_bqN_<name>.py`, then run
   `python -m unittest discover -s tests -p "test_*.py"`.

Authorization is already handled by `require_admin()` in the endpoint, so a
metric module never needs its own admin check.
