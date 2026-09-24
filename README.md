# WhyNot shared Firebase backend

`whynot-back` is the source of truth for the Firebase backend shared by the
Flutter/iOS and Kotlin/Android applications. It versions the Firestore data
contract, Security Rules, indexes, emulator setup, tests, and privileged
maintenance scripts.

There is no custom REST server. Mobile clients use the Firebase SDKs and the
same Firebase project:

```text
Project name: WhyNot
Project ID: whynot-f4ae6
```

Do not create a platform-specific Firebase project and never commit service
account keys or other credentials.

## Implemented foundation

```text
docs/data-model.md                         Shared Firestore contract
docs/authentication.md                     Admin role and provisioning contract
firestore.rules                           Client authorization and validation
firestore.indexes.json                    Versioned index manifest
firebase.json                             Emulator and deployment configuration
tests/firestore-rules/                    Emulator-backed rules tests
scripts/seed-categories/                  Idempotent canonical category seed
scripts/seed-cities/                      Idempotent canonical city seed
scripts/assign-admin-role/                Privileged custom-claim management
```

The current user-facing collections are `users`, `categories`, `cities`,
`wishlists`, and `products`. Administrators with the `admin: true` custom claim may read
aggregate documents under `adminMetrics`; no client may write those documents.
`productEvents` and `processedEvents` remain backend-only.

Phase 1 was deployed to the default Firestore database in `whynot-f4ae6` on
2026-09-21 after all 17 Security Rules tests passed.

See [docs/data-model.md](docs/data-model.md) before changing any field,
collection, or allowed operation.
See [docs/authentication.md](docs/authentication.md) for administrator
provisioning, revocation, token refresh, and authorization boundaries.

## Prerequisites

- Node.js 22 or 24
- Java 21 or newer for the Firestore emulator
- Firebase access only for production deployment or privileged production
  scripts

The Firebase CLI is installed as a project dependency, so a global install is
not required.

On macOS with Homebrew, install and expose Java with:

```bash
brew install openjdk@21
export JAVA_HOME="/opt/homebrew/opt/openjdk@21"
export PATH="$JAVA_HOME/bin:$PATH"
```

Use `/usr/local/opt/openjdk@21` instead on an Intel Homebrew installation.

## Install

```bash
npm ci
```

## Local emulators

Start Authentication, Firestore, and the Emulator Suite UI:

```bash
npm run emulators
```

Fixed local endpoints:

| Service | Endpoint |
|---|---|
| Emulator UI | `http://127.0.0.1:4000` |
| Firestore | `127.0.0.1:8080` |
| Authentication | `127.0.0.1:9099` |
| Functions | `127.0.0.1:5001` |

Local commands use the non-live `demo-whynot` project. A demo project fails
closed if code tries to reach a Firebase service that is not emulated.

## Security Rules tests

Run the complete suite with:

```bash
npm test
```

The command starts a Firestore emulator, runs the tests, and stops the
emulator. Tests cover unauthenticated access, owner isolation, exact schemas,
field types, immutable fields, document relationships, internal collections,
and the query shapes currently used by Flutter.

The Firestore emulator does not enforce composite indexes. The current client
uses equality-only queries and needs no manual composite index; production
query behavior must still be checked before a release.

The purchase metric counts existing purchased products. Deleting a product
deletes its document and removes it from that count. No purchase trigger or
separate purchase-history test is needed.

## Smart feature tests

Run the recommendation and nearby-store flows against isolated Authentication,
Firestore, and Functions emulators:

```bash
npm run test:smart-features
```

The test creates an authenticated user, recommendation data, and stores in
multiple categories. It verifies that `get_nearest_store` returns the closest
store in the user's preferred category.

## Seed categories

The seed uses stable document IDs and merge writes, so it is repeatable and
does not delete unrelated fields or documents.

With a running local Firestore emulator:

```bash
FIRESTORE_EMULATOR_HOST=127.0.0.1:8080 \
  npm run seed:categories -- --project demo-whynot --dry-run

FIRESTORE_EMULATOR_HOST=127.0.0.1:8080 \
  npm run seed:categories -- --project demo-whynot
```

To seed the shared project, authenticate with Application Default Credentials
and optionally review a dry run first:

```bash
gcloud auth application-default login

npm run seed:categories -- \
  --project whynot-f4ae6 \
  --dry-run

npm run seed:categories -- \
  --project whynot-f4ae6
```

The seed prints counts for documents that are created, updated, or unchanged.

## Seed cities

The city seed creates the canonical `cities` catalog used by registration and
profile editing. It is repeatable and does not delete unrelated documents.
Use the same credentials and `--project` option as the category seed:

```bash
npm run seed:cities -- --project whynot-f4ae6 --dry-run
npm run seed:cities -- --project whynot-f4ae6
```

The initial list is based on [DANE's main cities and metropolitan areas](https://microdatos.dane.gov.co/index.php/catalog/832/variable/F1/V5?name=AREA),
with an additional `other` option.

## Assign or revoke the administrator role

The script manages the Firebase Authentication custom claim `admin: true`.
It accepts exactly one user selector and preserves unrelated custom claims.

Dry-run a grant by UID:

```bash
npm run assign-admin -- \
  --project whynot-f4ae6 \
  --uid <firebase-auth-uid> \
  --grant \
  --dry-run
```

Apply a grant by email:

```bash
npm run assign-admin -- \
  --project whynot-f4ae6 \
  --email user@example.com \
  --grant
```

Revoke the claim:

```bash
npm run assign-admin -- \
  --project whynot-f4ae6 \
  --uid <firebase-auth-uid> \
  --revoke
```

The user must sign out and sign back in after a claim changes. The Flutter
login flow also forces an ID-token refresh before selecting the regular or
administrative destination.

Passwords, ID tokens, and credential JSON are not command arguments and must
not be placed in this repository.

## Deploy Firestore configuration

First authenticate the Firebase CLI and confirm project access:

```bash
npx firebase login
npx firebase projects:list
```

Then run the test-gated deployment with an explicit production target:

```bash
npm run deploy:firestore -- --project whynot-f4ae6
```

This deploys only `firestore.rules` and `firestore.indexes.json`. The initial
empty composite-index manifest has been deployed. Any future index created in
the Firebase Console must also be added to `firestore.indexes.json` before the
next deployment.

## Deploy the nearby-store function

Deploy the callable function with an explicit production target:

```bash
npm run deploy:functions:nearby -- --project whynot-f4ae6
```

The command first runs the smart-feature emulator test and deploys only
`get_nearest_store`. It does not modify Firestore data or redeploy unrelated
functions.

## Security decisions

- Client access is denied by default.
- Regular users can access only their own profiles, wishlists, and products.
  Administrators may list profiles for the demographic chart; this also
  exposes profile names and emails to admin clients.
- Categories are readable by authenticated users and writable only by trusted
  Admin SDK code.
- Cities are readable by authenticated users and writable only by trusted
  Admin SDK code. New profiles must reference an existing city.
- Aggregate metrics are readable only with the Firebase Authentication custom
  claim `admin: true` and are never client-writable.
- Product events and processed-event markers remain inaccessible to every
  client, including administrators.
- Wishlist update/delete remains denied until cascade behavior is defined.
- One-wishlist-per-category is currently a UI behavior, not an enforceable
  backend invariant, because wishlists use random document IDs.
- `purchasedAt` records the purchase month while a product exists. Purchase is
  a one-way transition, and deletion removes the product from metrics.
- `saveMethod` and the automatic-versus-manual metric remain deferred because
  the clients currently support only manual product creation.
- Admin SDK operations bypass Firestore Security Rules; privileged scripts
  must therefore preserve the documented contract themselves.

## Change workflow

For every contract or authorization change:

1. Update `docs/data-model.md`.
2. Update `firestore.rules`.
3. Add allowed and denied test cases.
4. Update indexes if a new query requires them.
5. Run `npm test`.
6. Coordinate the contract change with both mobile teams.
7. Deploy only after review.
