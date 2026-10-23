# Wishlist CRUD and UX interaction trace

This is Santiago's supporting Type 2 Wishlist UX contribution. It does not replace or count Juliana's `productSaveEvents`, the onboarding `first_wishlist_created` event, or BQ1/BQ2/BQ5 product metrics.

## Event contract

`wishlistInteractionEvents/{operationId}` is append-only, schema version 1. Each event has `action`, `outcome`, short `reason`, `userId`, optional `wishlistId` and `categoryId`, `platform`, `operationId`, and server `createdAt`. It never includes picture URLs, emoji, user profile fields, or coordinates. Client writes are restricted to their own user ID, exact fields and enum values. Admins may read; nobody may update or delete through client rules. The delete callable writes delete outcomes with Admin SDK. `operationId` is the document ID, so a retry of the same operation cannot add a second event.

| Action | Meaning | Outcomes |
| --- | --- | --- |
| `create_form_open` | New Wishlist screen opened intentionally | `intent` |
| `create_form_cancel` | User tapped Cancel in the create form | `intent` |
| `create` | Submitted wishlist creation | `success` after atomic wishlist/event batch, or best-effort client `failure` |
| `open` | User tapped a wishlist card to open detail | `intent` |
| `edit` | Submitted picture URL or curated emoji change | `success` after atomic update/event batch, or best-effort client `failure` |
| `delete` | Confirmed deletion request | Backend `success`, `blocked`/`nonempty`, or `failure`/`not_found` |

`reason` is `none` for intent/success; failures use short codes such as `validation`, `network`, `permission`, `unknown`, or `not_found`. A blocked delete uses `nonempty`. No stream emission or widget rebuild logs an event. Create/edit write failures reuse their mutation operation ID, so a completed success cannot also become a failure event. Client failure events are best-effort: if the device cannot reach Firestore, the failure may remain unrecorded. A delete network timeout may leave the operation outcome uncertain until the same-ID retry returns.

## Data and control flow

1. Flutter view calls `WishlistController` for create, open, edit, or confirmed delete. The controller validates picture URLs and curated emoji before mutation. `WishlistRepository` is the injected contract; `FirebaseWishlistRepository` is its production adapter.
2. Create/edit commit the wishlist change and success event together in one Firestore batch. Firestore rules enforce owner identity, immutable `ownerId`, `categoryId`, and `createdAt`, curated emoji, the exact event schema, and a completed wishlist write for a client success event. Existing records without `emoji` remain readable.
3. Delete calls `delete_empty_wishlist`. It marks the owned wishlist as deleting in a transaction; product create/update rules and the recommendation-save callable then reject use of that wishlist. A second transaction checks for any product, deletes only an empty wishlist, clears the marker on a blocked delete, and writes exactly one outcome event. A repeated operation ID returns its previous result. A stale reservation can be taken over after two minutes. Product documents are never cascaded.
4. `get_admin_analytics({metric: "wishlist_interactions"})` requires the existing `admin: true` claim. It reads only `wishlistInteractionEvents`, deduplicates operation IDs, and returns per-action outcomes, unique users, failure reasons, and success rates. Intent-only actions have no success rate; blocked deletes count as attempts.
5. Local Admin Web's **Wishlist UX** supporting view calls that metric through its existing connector and displays the backend-calculated values. It does not recompute BQ1/BQ2/BQ5 or claim their ownership.

## Demonstration after deployment

Deploy backend rules and functions before using the new Flutter build, then update the local Admin Web. Sign in as a fresh user; open New Wishlist, choose a category and emoji, and save. Tap the wishlist card, edit its emoji, add a product, and confirm delete: the wishlist and product must remain, with a `blocked`/`nonempty` event. Create another category wishlist with no products and delete it: the list must update and the backend must report one successful delete. Sign in to local Admin Web as an admin, open **Wishlist UX**, and refresh to see create/open/edit, blocked delete, and successful delete counts. Verify the raw event IDs only if needed; the UI displays the callable's processed result.

Firestore rules and the wishlist-related Cloud Functions were deployed to `whynot-f4ae6` on 2026-10-23 with Santiago's approvals. The production delete callable is listed and returns HTTP 401 to an unsigned request. Santiago confirmed on 2026-10-23 that editing an existing wishlist's picture link or emoji and deleting an empty wishlist both work in the production-connected Flutter app. The blocked-nonempty delete and Admin Web before/after counts still need production evidence.
