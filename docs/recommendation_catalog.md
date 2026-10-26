# Recommendation catalog callable

`get_recommendation_catalog` requires Firebase authentication. It returns `recommendations`, an array of distinct unseen products in the signed-in user's preferred category. Candidates come from users with valid demographics, ordered by similarity score, age difference, user ID, and bought-before-saved products. The response includes `sourceProductId`, product details, and a reason. It creates **no** `productEvents` record: fetching the catalog does not imply every row was seen.

When a person opens a catalog row, Flutter calls the existing `get_recommendation` callable with `{ "sourceProductId": "..." }`. The backend rechecks current eligibility, creates one `recommendation_shown` event, and returns the usual `recommendation` object with `recommendationEventId`. That event can be used by `save_recommended_product`. The original parameterless top-pick call remains available.

This implementation gathers every eligible row in one response. It fits the current small project dataset; a larger collection needs pagination and an explicit response-size policy. The Flutter catalog can use a short-lived in-memory copy but cannot display it after an app restart. Deploy the callable before enabling the new Flutter screen in production.
