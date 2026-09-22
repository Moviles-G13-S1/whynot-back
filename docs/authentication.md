# WhyNot authentication and administrator access

WhyNot uses Firebase Authentication with email and password for both regular
users and administrators. Authorization is determined by the signed Firebase
ID token, not by a field in `users/{uid}`.

## Administrator role

An administrator token must contain this custom claim:

```json
{ "admin": true }
```

Only a trusted operator using the Admin SDK may grant or revoke the claim.
The mobile client cannot assign its own role, and the Firestore user schema
rejects extra role fields.

## Provision an administrator

1. Create the email/password account through Firebase Authentication or the
   normal WhyNot account-creation flow. Never store the password in this
   repository or pass it to the role script.
2. Review the intended account and project with a dry run:

   ```bash
   npm run assign-admin -- \
     --project whynot-f4ae6 \
     --email administrator@example.com \
     --grant \
     --dry-run
   ```

3. Grant the role:

   ```bash
   npm run assign-admin -- \
     --project whynot-f4ae6 \
     --email administrator@example.com \
     --grant
   ```

4. Have the administrator sign out and sign back in. The Flutter login flow
   forces a token refresh and routes `admin: true` accounts to the dashboard.

Use a named individual account rather than a shared credential. Account
creation and claim assignment are operational actions: the real email and
password must be supplied outside source control.

## Revoke access

```bash
npm run assign-admin -- \
  --project whynot-f4ae6 \
  --email administrator@example.com \
  --revoke
```

The client rechecks a freshly issued token whenever an admin route is opened.
Existing Firestore requests are independently authorized by Security Rules.
Revocation therefore takes effect when Firebase issues the refreshed token;
the user should also be disabled or have sessions revoked in Firebase
Authentication when immediate incident response is required.

## Authorization boundaries

- Regular authenticated users may access only their owned application data.
- Administrators may read aggregate documents under `adminMetrics`.
- No client may write `adminMetrics`.
- No client, including an administrator, may read or write `productEvents` or
  `processedEvents`.
- Admin SDK code bypasses Firestore Security Rules and must be protected by
  IAM and trusted runtime credentials.
