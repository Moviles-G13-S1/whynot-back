# WhyNot Firestore data contract

This document defines the current contract shared by all WhyNot clients. The
Security Rules in `firestore.rules` are authoritative for client access and
validation. Firebase Admin SDK code bypasses those rules and must enforce the
same contract deliberately.

## General conventions

- Firebase Authentication UIDs identify users and owners.
- Timestamps are Firestore `timestamp` values written with a server timestamp.
- Unknown fields are rejected for client-writable user-facing documents.
- Document ownership and `createdAt` cannot be changed by a client.
- Category IDs are stable identifiers rather than display names.
- External image/product links remain strings; Firebase Storage is not used.
- Passwords and roles are never stored in user documents.
- Recommendation events can be read by accounts with the `admin: true` claim
  for the web dashboard's BQ3 calculation; no client can write them.

## `users/{uid}`

The document ID must equal the authenticated user's UID.

| Field | Type | Validation |
|---|---|---|
| `name` | string | 1–120 characters |
| `email` | string | 1–320 characters; equals the authenticated email; immutable |
| `gender` | string | `Female`, `Male`, or `Other` |
| `age` | integer | 13–120 inclusive |
| `preferredCategoryId` | string | Must reference an existing category |
| `cityId` | string | Must reference an existing city; required for new profiles |
| `createdAt` | timestamp | Server timestamp on create; immutable |
| `updatedAt` | timestamp | Server timestamp on every write |

Clients may create, get, and update their own profile. Only an administrator
with the `admin: true` claim may list profiles for demographic figures.
Regular users cannot list profiles, and client deletion is denied. Updates
are limited to `name`, `gender`, `age`, `preferredCategoryId`, `cityId`, and
`updatedAt`. Older profiles may lack `cityId` until their next profile edit.

## `cities/{cityId}`

| Field | Type | Validation |
|---|---|---|
| `name` | string | Canonical display name |

The initial catalog contains 24 main Colombian cities from DANE and `other`.
IDs are stable, lowercase, and omit accents (for example, `bogota` has the
display name `Bogotá`). The client searches this catalog and stores only the
selected ID in the user profile. It does not store free-text city names or
device location. Anyone may read cities so the catalog works before sign-in;
only a privileged seed script may change them.

## `categories/{categoryId}`

| Field | Type | Validation |
|---|---|---|
| `name` | string | Non-empty canonical display name |

Canonical documents:

| ID | Name |
|---|---|
| `fashion` | Fashion |
| `beauty` | Beauty |
| `technology` | Technology |
| `home` | Home |
| `accessories` | Accessories |
| `travel` | Travel |
| `gifts` | Gifts |
| `other` | Other |

Authenticated clients may get or list categories. All client writes are
denied. Run the privileged category seed to create or repair these documents.

## `wishlists/{wishlistId}`

| Field | Type | Validation |
|---|---|---|
| `ownerId` | string | Authenticated UID; immutable |
| `categoryId` | string | Must reference an existing category |
| `imageUrl` | string | Up to 2,048 characters; may be empty |
| `createdAt` | timestamp | Server timestamp on create; immutable |
| `updatedAt` | timestamp | Server timestamp on create |

Clients may create, get, and query their own wishlists. Updates and deletes
are denied until their semantics and product cascade behavior are defined.

The UI currently tries to maintain one wishlist per owner/category pair, but
that uniqueness is not a backend invariant. Auto-generated wishlist IDs make
it impossible for Security Rules to enforce the check atomically. A later
change must use a deterministic ID or a transactional callable function.

## `products/{productId}`

| Field | Type | Validation |
|---|---|---|
| `ownerId` | string | Authenticated UID; immutable |
| `wishlistId` | string | Must reference a wishlist owned by the same user |
| `categoryId` | string | Must match the referenced wishlist category |
| `name` | string | 1–200 characters |
| `brand` | string | 1–200 characters |
| `price` | number | Greater than or equal to zero |
| `imageUrl` | string | Up to 2,048 characters; may be empty |
| `productUrl` | string | Up to 2,048 characters; may be empty |
| `purchased` | boolean | Must be `false` on create; may only transition to `true` |
| `purchasedAt` | timestamp or null | `null` until purchase; server timestamp on the one-way purchase transition |
| `createdAt` | timestamp | Server timestamp on create; immutable |
| `updatedAt` | timestamp | Server timestamp on every write |

Owners may create, get, query, update, and delete products. A product can move
only to another wishlist owned by the same user, and `categoryId` must be
updated to match the destination wishlist.

Marking a product as purchased is irreversible while it exists. Deleting a
product deletes its document and removes it from product-based admin metrics.
There is no retained purchase history in this version.

### Manual product save

The existing manual product flow remains unchanged. A mobile client creates a
valid `products/{productId}` document through the normal product repository and
Firestore Security Rules.

A manual save does not create a recommendation event and is excluded from BQ3.

`saveMethod` is still not part of the product contract. The distinction needed
for BQ3 is represented by the backend recommendation-save flow rather than by
adding a required field to every product.

### Product-save attempts (`productSaveEvents/{eventId}`)

Every attempt to save a product from a mobile client also records one event,
for BQ Type 2. It is written by the client right after the attempt and never
blocks or changes the product save itself.

| Field | Type | Validation |
|---|---|---|
| `userId` | string | Authenticated UID |
| `platform` | string | `android` or `ios` |
| `outcome` | string | `success` or `failure` |
| `reason` | string or null | `null` on success; 1–64 characters on failure |
| `createdAt` | timestamp | Server timestamp on create |

Users may only create their own events; nobody may update or delete them, and
only administrators may read them. The reason codes in use are
`missing_name`, `missing_brand`, `invalid_price`, `negative_price`,
`missing_wishlist` and `backend_error`. `get_admin_analytics({metric:
"save_attempts"})` summarizes the collection (see
[admin-analytics.md](admin-analytics.md)).

### Product saved from a recommendation

Saving from the Smart Recommendation screen uses the callable Cloud Function:

```text
save_recommended_product(recommendationEventId, wishlistId)
```

The function writes a copy to `products` and marks the existing
`productEvents/{recommendationEventId}` record with `savedAt` and
`savedProductId` in one transaction. BQ3 counts those successful events in
`get_admin_analytics({view: "recommended"})`. Repeated saves are idempotent.
The count remains historical if a saved product is later deleted. The legacy
`adminMetrics/recommendedProductSaves` document is not read or updated by the
new dashboard.
