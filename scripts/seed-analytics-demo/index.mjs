#!/usr/bin/env node

import { randomBytes } from 'node:crypto';
import { readFile, stat, writeFile } from 'node:fs/promises';
import { isAbsolute } from 'node:path';
import { applicationDefault, initializeApp } from 'firebase-admin/app';
import { getAuth } from 'firebase-admin/auth';
import { getFirestore } from 'firebase-admin/firestore';
import { buildDemoDataset, DEMO_PREFIX, describeDemoDataset } from './fixture.mjs';

const collections = ['users', 'wishlists', 'products', 'productEvents', 'productSaveEvents'];

function parseArguments(args) {
  const options = { projectId: null, asOf: null, apply: false, confirmation: null, credentialsOut: null };
  for (let index = 0; index < args.length; index += 1) {
    const arg = args[index];
    if (arg === '--project') options.projectId = args[++index];
    else if (arg === '--as-of') options.asOf = args[++index];
    else if (arg === '--apply') options.apply = true;
    else if (arg === '--confirm-project') options.confirmation = args[++index];
    else if (arg === '--credentials-out') options.credentialsOut = args[++index];
    else throw new Error(`Unknown argument: ${arg}`);
  }
  if (!options.projectId) throw new Error('--project is required.');
  if (options.asOf && !/^\d{4}-\d{2}-\d{2}$/.test(options.asOf)) throw new Error('--as-of must be YYYY-MM-DD.');
  if (options.apply && (options.confirmation !== options.projectId || !isAbsolute(options.credentialsOut ?? ''))) {
    throw new Error('--apply requires --confirm-project <same project> and an absolute --credentials-out path.');
  }
  return options;
}

async function existingCredentials(path, dataset, asOf, requireExisting) {
  try {
    if (((await stat(path)).mode & 0o077) !== 0) {
      throw new Error('Existing demo credentials must be readable only by their owner (mode 0600).');
    }
    const stored = JSON.parse(await readFile(path, 'utf8'));
    const expected = dataset.users.map(user => user.id);
    if (stored.projectId !== asOf.projectId || stored.asOf !== asOf.date ||
        JSON.stringify(stored.accounts.map(account => account.uid)) !== JSON.stringify(expected)) {
      throw new Error('The existing credentials file belongs to another seed run.');
    }
    return stored;
  } catch (error) {
    if (error.code !== 'ENOENT') throw error;
    if (requireExisting) {
      throw new Error('Demo Auth users already exist; reuse their original credentials file to resume.');
    }
  }
  const stored = {
    projectId: asOf.projectId,
    asOf: asOf.date,
    accounts: dataset.users.map(user => ({
      uid: user.id,
      email: user.data.email,
      password: randomBytes(18).toString('base64url'),
    })),
  };
  await writeFile(path, JSON.stringify(stored, null, 2), { flag: 'wx', mode: 0o600 });
  return stored;
}

async function assertCleanTarget(db, auth, dataset) {
  for (const name of collections) {
    const snapshot = await db.collection(name).get();
    const expectedIds = new Set(dataset[name].map(record => record.id));
    if (snapshot.docs.some(doc => !expectedIds.has(doc.id))) {
      throw new Error(`${name} contains records outside this demo dataset. Back up and clear the target before seeding.`);
    }
  }
  const categories = new Set((await db.collection('categories').get()).docs.map(doc => doc.id));
  const cities = new Set((await db.collection('cities').get()).docs.map(doc => doc.id));
  for (const user of dataset.users) {
    if (!categories.has(user.data.preferredCategoryId) || !cities.has(user.data.cityId)) {
      throw new Error('Seed categories and cities before creating demo users.');
    }
  }
  let pageToken;
  let existingDemoUsers = 0;
  const expectedUids = new Set(dataset.users.map(user => user.id));
  do {
    const page = await auth.listUsers(1000, pageToken);
    for (const user of page.users) {
      if (expectedUids.has(user.uid)) existingDemoUsers += 1;
      else if (user.customClaims?.admin !== true) {
        throw new Error('Non-admin Auth users remain. Preserve admin sign-ins and clear other accounts before seeding.');
      }
    }
    pageToken = page.pageToken;
  } while (pageToken);
  return existingDemoUsers;
}

async function applyDataset(options, dataset) {
  const firestoreEmulator = Boolean(process.env.FIRESTORE_EMULATOR_HOST);
  const authEmulator = Boolean(process.env.FIREBASE_AUTH_EMULATOR_HOST);
  if (firestoreEmulator !== authEmulator) throw new Error('Auth and Firestore must both use emulators, or both use production.');
  const app = initializeApp({
    projectId: options.projectId,
    ...(firestoreEmulator ? {} : { credential: applicationDefault() }),
  });
  const db = getFirestore(app);
  const auth = getAuth(app);
  const existingDemoUsers = await assertCleanTarget(db, auth, dataset);
  const credentials = await existingCredentials(options.credentialsOut, dataset, { projectId: options.projectId, date: options.asOf }, existingDemoUsers > 0);

  for (const account of credentials.accounts) {
    try {
      const existing = await auth.getUser(account.uid);
      if (existing.email !== account.email) throw new Error(`UID ${account.uid} belongs to another email.`);
    } catch (error) {
      if (error.code !== 'auth/user-not-found') throw error;
      await auth.createUser(account);
    }
  }
  for (const name of collections) {
    const records = dataset[name];
    for (let offset = 0; offset < records.length; offset += 400) {
      const batch = db.batch();
      for (const record of records.slice(offset, offset + 400)) {
        batch.set(db.collection(name).doc(record.id), record.data);
      }
      await batch.commit();
    }
  }
  console.log(`Created or updated the demo dataset in ${options.projectId}.`);
  console.log(`Credentials are stored only in ${options.credentialsOut} (mode 0600).`);
}

async function main() {
  const options = parseArguments(process.argv.slice(2));
  const asOf = options.asOf ?? new Intl.DateTimeFormat('en-CA', {
    timeZone: 'America/Bogota', year: 'numeric', month: '2-digit', day: '2-digit',
  }).format(new Date());
  const dataset = buildDemoDataset(new Date(`${asOf}T12:00:00Z`));
  options.asOf = asOf;
  console.log(JSON.stringify({ projectId: options.projectId, asOf, ...describeDemoDataset(dataset) }, null, 2));
  if (!options.apply) {
    console.log('Dry run only. No Firebase data was read or changed.');
    return;
  }
  await applyDataset(options, dataset);
}

main().catch(error => {
  console.error(error.message);
  process.exitCode = 1;
});
