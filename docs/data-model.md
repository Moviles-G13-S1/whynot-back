# WhyNot Firestore data contract

This document defines the current contract shared by all WhyNot clients. The
Security Rules in `firestore.rules` are authoritative for client access and
validation. Firebase Admin SDK code bypasses those rules and must enforce the
same contract deliberately.

## General conventions

- Firebase Authentication UIDs identify users and owners.
- Timestamps are Firestore `timestamp` values written with a server timestamp.
- Unknown fields are rejected.
- Document ownership and `createdAt` cannot be changed by a client.
- Category IDs are stable identifiers rather than display names.
- External image/product links remain strings; Firebase Storage is not used.
- Passwords and roles are never stored in user documents.

## `users/{uid}`

The document ID must equal the authenticated user's UID.

| Field | Type | Validation |
|---|---|---|
| `name` | string | 1–120 characters |
| `email` | string | 1–320 characters; equals the authenticated email; immutable |
| `gender` | string | `Female`, `Male`, or `Other` |
| `age` | integer | 13–120 inclusive |
| `preferredCategoryId` | string | Must reference an existing category |
| `createdAt` | timestamp | Server timestamp on create; immutable |
| `updatedAt` | timestamp | Server timestamp on every write |

Clients may create, get, and update their own profile. Profile collection
listing and client deletion are denied. Updates are limited to `name`,
`gender`, `age`, `preferredCategoryId`, and `updatedAt`.

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
| `purchased` | boolean | Must be `false` on create |
| `createdAt` | timestamp | Server timestamp on create; immutable |
| `updatedAt` | timestamp | Server timestamp on every write |

Owners may create, get, query, update, and delete products. A product can move
only to another wishlist owned by the same user, and `categoryId` must be
updated to match the destination wishlist.

`saveMethod` and `purchasedAt` belong to Phase 4. They are deliberately
rejected by the Phase 1 rules until rules, tests, documentation, existing data,
and both clients migrate together.

## Administrative and internal collections

### `adminMetrics/{document=**}`

Authenticated users whose Firebase ID token contains the custom claim
`admin: true` may read aggregate metric documents at any depth. Regular users
and unauthenticated clients cannot read them. All client writes are denied;
trusted backend code writes these documents with the Admin SDK.

The metric schemas and generation pipeline belong to Phase 4. Phase 2 opens
only the least-privilege read boundary so the future dashboard integration
does not require another authorization redesign.

### Backend-only collections

Client reads and writes are denied for these collections, including when the
caller has the administrator claim:

- `productEvents`
- `processedEvents`

All other undocumented paths are denied by default.
