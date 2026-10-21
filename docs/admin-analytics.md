# Admin analytics

The HTML dashboard calls `get_admin_analytics` for processed results. The
function requires the `admin: true` application claim, then reads Firestore
through the Admin SDK. BQ3 counts successful `productEvents`; it does not read
or write `adminMetrics`.

This second-generation Firebase function uses an underlying Cloud Run service.
Its invoker policy must allow requests to reach the callable; the callable then
checks the Firebase ID token before returning analytics. The deployed service
`get-admin-analytics` in `whynot-f4ae6/us-central1` grants `roles/run.invoker`
to `allUsers` for that transport step. An unauthenticated call still returns
Firebase `unauthenticated` (HTTP 401).

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
| `bq4` | `{ "months": 6 }` (6, 12, or 24) | Current purchased `products`: top category per month, matching the Kotlin BQ4 implementation |
| `demographic` | `{ "categoryId": "..." }` (optional) | Current product owners, profiles, categories, and cities, matching the Flutter screen |
| `bq6` | `{}` | Purchased-product buyers, matching the separate Kotlin BQ6 implementation |
| `save_attempts` | `{}` | `productSaveEvents`: product-save successes and failures per platform (BQ Type 2) |

The callable's four view calculators live in
`functions/analytics/dashboard_views.py`. The HTML dashboard renders the
processed `data` field returned by the callable.
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

## BQ4: category with the most purchased products per month

A purchase is a product that currently exists with `purchased == true`. Its
month is the calendar month of `purchasedAt` in `America/Bogota`. `params.months`
picks the window (6, 12, or 24 months, counting the current one; default 6).
Any other value is rejected with `invalid-argument`.

```json
{
  "months": [
    {
      "year": 2026,
      "month": 10,
      "label": "Oct 2026",
      "totalPurchases": 5,
      "topCategoryIds": ["beauty", "tech"],
      "topCategoryNames": ["Beauty", "Technology"],
      "topCategoryPurchases": 2,
      "byCategory": [
        { "categoryId": "beauty", "categoryName": "Beauty", "purchases": 2 },
        { "categoryId": "tech", "categoryName": "Technology", "purchases": 2 },
        { "categoryId": "home", "categoryName": "Home", "purchases": 1 }
      ]
    }
  ],
  "totalPurchases": 5,
  "undatedPurchases": 1,
  "overallTopCategoryIds": ["beauty", "tech"],
  "overallTopCategoryNames": ["Beauty", "Technology"],
  "monthsWindow": 6
}
```

- `months` lists only months in the window that have purchases, newest first.
- `topCategoryIds` holds every category tied at the highest count, sorted, so
  a tie is reported as a tie. `topCategoryPurchases` is that highest count.
- `byCategory` is sorted by `purchases` (descending), then `categoryId`.
  `categoryName` falls back to the id.
- `totalPurchases` and `overallTopCategoryIds` cover the whole window, with the
  same tie rule.
- `undatedPurchases` counts purchased products without `purchasedAt` (bought
  before the field existed). They have no month, so they are reported here
  instead of being dropped.

The logic lives in `compute_purchases_by_category()` in
`functions/analytics/bq4_purchases_by_category.py`. It uses plain dictionaries
and is the calculation the Kotlin admin dashboard ran in
`AdminInsightsController`, moved to the backend. The Firestore read uses the
same single-field equality query as BQ6 (`purchased == true`), so it needs no
composite index.

## Product-save attempts (BQ Type 2)

Each mobile client writes one `productSaveEvents` document per attempt to save
a product (see [data-model.md](data-model.md)). `save_attempts` summarizes them:

```json
{
  "totalAttempts": 40,
  "successes": 36,
  "failures": 4,
  "successRate": 90.0,
  "platforms": [
    { "platform": "android", "successes": 20, "failures": 3 },
    { "platform": "ios", "successes": 16, "failures": 1 }
  ],
  "failureReasons": [
    { "reason": "invalid_price", "count": 3 },
    { "reason": "backend_error", "count": 1 }
  ]
}
```

- `successRate` is a percentage of all attempts, not rounded, and `null` when
  there are none.
- `platforms` always lists `android` and `ios`.
- `failureReasons` is sorted by `count` (descending), then `reason`. A failure
  without a reason is counted as `unknown`.

The logic lives in `compute_save_attempts()` in
`functions/analytics/product_save_attempts.py`.

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
