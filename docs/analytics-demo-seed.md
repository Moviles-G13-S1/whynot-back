# Replacing app data with an analytics demo dataset

The scripts in this repository can replace the app records in `whynot-f4ae6`
with a deterministic, synthetic dataset for BQ1–BQ6. These numbers demonstrate
the dashboard and backend calculations; they are **not measurements of real
WhyNot usage**. Keep that distinction clear when presenting results.

## Scope

The reset clears `users`, `wishlists`, `products`, `productEvents`,
`productSaveEvents`, `processedEvents`, and the obsolete `adminMetrics`
collection, including nested documents. It deletes non-admin Firebase
Authentication accounts. It retains Authentication accounts with the
`admin: true` custom claim and the `categories`, `cities`, and `stores`
catalogs. Admin user profiles under `users` are cleared with the other app
profiles. The reset refuses to run if it finds other top-level collections;
inspect those before extending its scope.

The seed creates 24 demo Authentication accounts and matching profiles, 77
products, 72 recommendation impressions, 28 recommendation saves, 25
purchases, and 48 product-save attempts. IDs begin with `demo-analytics-` and
emails use the reserved `.example` domain. Dates move with the chosen `as-of`
month so recent-month charts remain populated. It creates no `adminMetrics`
aggregate; BQ3 reads `productEvents` through the analytics backend.

## Prepare and review

Run from the `whynot-back` repository with Node 22 or 24 and dependencies
installed. Authenticate both Firebase CLI and Google Cloud Application Default
Credentials with an account authorized for the project. Store all backups and
generated passwords outside the repository in a private location.

```sh
npx firebase login
gcloud auth application-default login
npm run seed:analytics-demo -- --project whynot-f4ae6 --as-of 2026-10-21
npm run reset:analytics-demo -- --project whynot-f4ae6
```

The seed command above is offline and read-only. The reset command prints a
read-only inventory: collection counts, preserved admin sign-in count, other
Authentication account count, unexpected collections, and an inventory digest.
Review those numbers before continuing. Run the unit tests with
`node --test tests/seed-analytics-demo.test.mjs`.

## Back up before reset

Use a private Cloud Storage bucket in the Firestore database location. The
project must have billing enabled for managed Firestore export, and the
Firestore service agent needs access to the bucket. Export **all** Firestore
collections, wait for the operation to finish, and record its exact output URI
prefix. The command below is illustrative; replace the bucket name and date:

```sh
gcloud firestore export gs://PRIVATE_BUCKET/whynot-before-demo-2026-10-21 --database='(default)' --project=whynot-f4ae6
```

Export Firebase Authentication separately. This file includes sensitive user
account data and password hashes, so keep it private:

```sh
umask 077
npx firebase auth:export /ABSOLUTE/PRIVATE/PATH/whynot-auth-before-demo.json --format=json --project=whynot-f4ae6
chmod 600 /ABSOLUTE/PRIVATE/PATH/whynot-auth-before-demo.json
```

Inspect the export operation's completed status. Re-run the read-only reset
inventory after backups and use its current digest. Do not run the execute
command if the app is still writing data; a changed inventory stops it, but
document edits after the inventory change its digest and stop the reset.

## Execute after review

The two explicit project flags and inventory digest guard against applying the
reset to the wrong project or after its inventory changes. Replace every
placeholder with the values just reviewed:

```sh
npm run reset:analytics-demo -- \
  --project whynot-f4ae6 --execute --confirm-project whynot-f4ae6 \
  --inventory-digest DIGEST_FROM_LATEST_INVENTORY \
  --firestore-backup gs://PRIVATE_BUCKET/EXACT_COMPLETED_EXPORT_PREFIX \
  --auth-backup /ABSOLUTE/PRIVATE/PATH/whynot-auth-before-demo.json

npm run seed:categories -- --project whynot-f4ae6

npm run seed:analytics-demo -- \
  --project whynot-f4ae6 --as-of 2026-10-21 \
  --apply --confirm-project whynot-f4ae6 \
  --credentials-out /ABSOLUTE/PRIVATE/PATH/whynot-demo-accounts.json
```

The credentials file is created with owner-only permissions and lets the seed
resume after an interruption. Never commit or share it. Verify the dashboard
with an existing admin login and check that demo data is clearly identified as
sample data in any report or presentation.

For recovery, import the Firestore export and the Authentication export using
the official Firebase procedures. Firestore import does not automatically
remove demo records first, so plan the cleanup before restoring.

Official references: [Firestore export and import](https://firebase.google.com/docs/firestore/manage-data/export-import),
[Firebase Authentication export and import](https://firebase.google.com/docs/cli/auth).
