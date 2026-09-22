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

## Phase 1 contents

```text
docs/data-model.md                         Shared Firestore contract
firestore.rules                           Client authorization and validation
firestore.indexes.json                    Versioned index manifest
firebase.json                             Emulator and deployment configuration
tests/firestore-rules/                    Emulator-backed rules tests
scripts/seed-categories/                  Idempotent canonical category seed
scripts/assign-admin-role/                Privileged custom-claim management
```

The current collections are `users`, `categories`, `wishlists`, and
`products`. Future internal collections (`adminMetrics`, `productEvents`, and
`processedEvents`) are explicitly inaccessible to clients until their phases
are implemented.

Phase 1 was deployed to the default Firestore database in `whynot-f4ae6` on
2026-09-21 after all 17 Security Rules tests passed.

See [docs/data-model.md](docs/data-model.md) before changing any field,
collection, or allowed operation.

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

The user must refresh their Firebase ID token after a claim changes. Phase 1
does not grant admins client access to Firestore; admin-specific rules and
route guards belong to Phase 2.

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

## Security decisions

- Client access is denied by default.
- Users can access only their own profiles, wishlists, and products.
- Categories are readable by authenticated users and writable only by trusted
  Admin SDK code.
- Wishlist update/delete remains denied until cascade behavior is defined.
- One-wishlist-per-category is currently a UI behavior, not an enforceable
  backend invariant, because wishlists use random document IDs.
- `saveMethod`, `purchasedAt`, analytics events, and aggregate metrics are
  reserved for Phase 4 and are rejected by the current schema.
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
