# Sprint 3 — Weekly application errors (Jerónimo, Type 1)

Question: **How many errors does the app produce weekly?**

The pipeline is Flutter → durable device outbox → Firestore
`applicationErrorEvents` → existing admin-only `get_admin_analytics` callable
(`metric: weekly_app_errors`) → the dashboard's **Sprint 3 / Weekly app errors**.
The dashboard uses the shared database and backend aggregation, without importing
downloaded data or calculating business metrics in the browser.

## Definition and coverage

One error is one captured technical failure with a stable random event ID.
Calendar weeks run Monday 00:00 through Sunday in `America/Bogota`. The selectable
window is 4, 8 (default), or 12 weeks, including the current partial week. The
backend returns weekly counts, bar proportions, current/previous-week totals,
and breakdowns by feature, category, platform and capture source.

The occurrence timestamp determines the week, not upload time. Late offline
delivery can therefore revise a previous week's count. Client clock errors can
affect attribution; rules reject timestamps more than five minutes in the
future, and the aggregate excludes timestamps later than its current time.

Current Flutter coverage:

- Authentication: sign-in, registration, sign-out, password change.
- Home/Profile: errors from instrumented live data sections.
- Profile: one-shot profile reads, photo URL reads, photo saves, profile updates.
- Runtime: uncaught Flutter framework and asynchronous platform errors after
  Firebase initialization, preserving existing error presentation/propagation.

Expected validation errors, incorrect credentials and actions blocked by the
existing offline guard are excluded. This is captured telemetry, not a census
of every failure: handled errors in other features, swallowed photo-cache
fallback failures, startup failures before handler installation and abruptly
terminated processes are not guaranteed to be recorded. Zero means no events
received in the selected period, not proof that no errors occurred.

## Delivery and data contract

`applicationErrorEvents/{eventId}` has exactly these fields:

| Field | Meaning |
| --- | --- |
| `eventId` | 32 lowercase hexadecimal characters; also the document ID |
| `schemaVersion` | Integer `1` |
| `userId` | Authenticated delivery owner |
| `occurredAt` | UTC client occurrence timestamp |
| `createdAt` | Firestore server timestamp |
| `platform` | `ios`, `android`, `web` |
| `feature` | `auth`, `home`, `profile`, `runtime` |
| `operation` | Controlled code identifier, lowercase letters/underscores, max 48 |
| `code` | `network`, `permission`, `unauthenticated`, `not_found`, `rate_limited`, `timeout`, `unexpected` |
| `source` | `operation`, `framework`, `platform` |

No exception message, stack trace, email, password or form contents is sent.
SQLite (IndexedDB-backed SQLite on web) retains at most 500 pending records,
dropping the oldest on overflow. A record is removed only after acknowledgment.
The same event ID is reused after a lost acknowledgment. Firestore transactions
create once; retries read the existing document and do not increment counts.
The same exception object reported by different capture sources within one
second is suppressed to avoid counting propagation twice. Independent attempts
from the same source remain distinct events.

Events captured without a session wait locally, then are bound to the first
authenticated delivery owner before sending. Previously owned records cannot
be delivered by another account. The UID identifies the delivery owner and
does not establish who caused an error captured before login. Flush occurs on
startup, successful sign-in/registration, reconnection or new captured events;
failure leaves records pending for the next trigger. Clearing browser/app data
also clears undelivered records. Telemetry failures do not alter user actions.

Rules allow authenticated creation for the caller only, exact schema, own
document reads (including missing documents for transactions), and admin reads.
Client updates/deletes and non-admin collection listing are denied. The admin
callable independently enforces `admin: true` before reading with Admin SDK.

## Validation and deployment

Local verification on October 28, 2026: 141 backend unit tests, 148 Flutter
tests, 31 dashboard tests, and 8 isolated Firestore emulator tests passed.
The latter include access rejection, immutable events, transaction retries,
and real emulator documents → Python admin endpoint → dashboard HTML. Flutter
static analysis passed. These checks do not constitute a production or iPhone
demonstration.

Backend unit tests:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p 'test_*.py'
```

Isolated emulator test (requires Java, backend Python dependencies, and for the
cross-repo test the sibling dashboard checkout):

```powershell
npx firebase emulators:exec --config firebase.weekly-errors.test.json --only firestore --project demo-whynot "node node_modules/mocha/bin/mocha.js --timeout 25000 tests/firestore-rules/application-errors.rules.test.mjs"
```

The Python endpoint helper explicitly refuses to run without the Firestore
emulator environment. Integration fixtures are emulator-only.

Deployment order: merge the three branches; deploy Firestore rules and the
updated `get_admin_analytics` callable; distribute/run the updated Flutter app;
run the updated dashboard and sign in as an admin. Existing Firebase client
configuration points to the shared project unless emulator mode is explicitly
enabled. No new callable or composite index is required.

### Shared-project deployment — October 28, 2026

After explicit user approval, `get_admin_analytics` and the rules for
`applicationErrorEvents` were published to `whynot-f4ae6`. The function update
completed at `2026-10-28T23:11:37Z` (18:11 Bogotá).

To preserve other BQs, the release was built from the downloaded production
source and active rules, adding only the new module, its endpoint registration,
and its collection rules. Accepted but unpublished money-savings changes in
the local main branch were deliberately excluded from this release. Other
functions were not deployed. The local branch retains those accepted changes.

Downloaded post-deployment source confirms every pre-existing Python module is
byte-identical except `analytics/endpoint.py`, whose only code additions are
the import and registration of `weekly_app_errors`. Published rules match the
tested isolated release. The exact release passed 9 metric tests and 53
applicable Firestore rules tests; the full local branch passed 141 backend
unit tests and 57 Firestore rules tests. The four tests for the unpublished
money-savings collection were excluded only from the isolated release run.

The shared dashboard successfully loaded the weekly metric. Saved products,
recommended saves, top purchased category, and buyer profile were refreshed
against the new backend and matched their pre-deployment displayed results.
The new metric initially returned zero received events; no synthetic errors
were written to production. An app-generated event demonstration remains
required. Before/after source and rules backups are stored locally in the
workspace's `.deployment-backups/weekly-app-errors*` folders.

For the final demonstration, trigger a reproducible technical failure in an
instrumented operation using a development environment, restore connectivity,
verify the event in Firestore and refresh **Sprint 3 / Weekly app errors** on
two dashboard sessions. Verify that retries keep the same ID and count, a
regular account cannot read analytics, and changing the window fetches a
different backend result. Do not use deliberately invalid credentials as an
error-generation test: those are intentionally excluded.
