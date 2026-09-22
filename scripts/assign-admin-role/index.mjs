#!/usr/bin/env node

import { applicationDefault, initializeApp } from 'firebase-admin/app';
import { getAuth } from 'firebase-admin/auth';

function usage() {
  return [
    'Usage:',
    '  npm run assign-admin -- --project <project-id> (--uid <uid> | --email <email>) (--grant | --revoke) [--dry-run]',
  ].join('\n');
}

function parseArguments(argumentsList) {
  const options = {
    projectId: null,
    uid: null,
    email: null,
    action: null,
    dryRun: false,
  };

  for (let index = 0; index < argumentsList.length; index += 1) {
    const argument = argumentsList[index];

    if (argument === '--project') {
      options.projectId = argumentsList[index + 1] ?? null;
      index += 1;
    } else if (argument === '--uid') {
      options.uid = argumentsList[index + 1] ?? null;
      index += 1;
    } else if (argument === '--email') {
      options.email = argumentsList[index + 1] ?? null;
      index += 1;
    } else if (argument === '--grant' || argument === '--revoke') {
      if (options.action) {
        throw new Error('Choose exactly one of --grant or --revoke.');
      }
      options.action = argument.slice(2);
    } else if (argument === '--dry-run') {
      options.dryRun = true;
    } else if (argument === '--help' || argument === '-h') {
      console.log(usage());
      process.exit(0);
    } else {
      throw new Error(`Unknown argument: ${argument}`);
    }
  }

  if (!options.projectId) {
    throw new Error(`--project is required.\n\n${usage()}`);
  }
  if (Boolean(options.uid) === Boolean(options.email)) {
    throw new Error('Choose exactly one of --uid or --email.');
  }
  if (!options.action) {
    throw new Error('Choose exactly one of --grant or --revoke.');
  }
  return options;
}

async function main() {
  const options = parseArguments(process.argv.slice(2));
  const usingEmulator = Boolean(process.env.FIREBASE_AUTH_EMULATOR_HOST);
  const app = initializeApp({
    projectId: options.projectId,
    ...(usingEmulator ? {} : { credential: applicationDefault() }),
  });
  const auth = getAuth(app);
  const user = options.uid
    ? await auth.getUser(options.uid)
    : await auth.getUserByEmail(options.email);

  const currentClaims = { ...(user.customClaims ?? {}) };
  const nextClaims = { ...currentClaims };

  if (options.action === 'grant') {
    nextClaims.admin = true;
  } else {
    delete nextClaims.admin;
  }

  console.log(`Project: ${options.projectId}`);
  console.log(`User: ${user.uid} (${user.email ?? 'no email'})`);
  console.log(`Action: ${options.action} admin role`);
  console.log(`Claims before: ${JSON.stringify(currentClaims)}`);
  console.log(`Claims after:  ${JSON.stringify(nextClaims)}`);

  if (options.dryRun) {
    console.log('Dry run complete; custom claims were not changed.');
    return;
  }

  await auth.setCustomUserClaims(user.uid, nextClaims);
  console.log('Custom claims updated. The user must refresh their ID token.');
}

main().catch((error) => {
  console.error(error.message);
  process.exitCode = 1;
});
