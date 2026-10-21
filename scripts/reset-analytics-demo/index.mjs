#!/usr/bin/env node

import { createHash } from 'node:crypto';
import { readFile, stat } from 'node:fs/promises';
import { isAbsolute } from 'node:path';
import { applicationDefault, initializeApp } from 'firebase-admin/app';
import { getAuth } from 'firebase-admin/auth';
import { getFirestore } from 'firebase-admin/firestore';
import { getStorage } from 'firebase-admin/storage';

const appCollections = [
  'users', 'wishlists', 'products', 'productEvents', 'productSaveEvents',
  'processedEvents', 'adminMetrics',
];
const preservedCollections = ['categories', 'cities', 'stores'];

function parseArguments(args) {
  const options = {
    projectId: null, execute: false, confirmation: null, inventoryDigest: null,
    firestoreBackup: null, authBackup: null,
  };
  for (let index = 0; index < args.length; index += 1) {
    const arg = args[index];
    if (arg === '--project') options.projectId = args[++index];
    else if (arg === '--execute') options.execute = true;
    else if (arg === '--confirm-project') options.confirmation = args[++index];
    else if (arg === '--inventory-digest') options.inventoryDigest = args[++index];
    else if (arg === '--firestore-backup') options.firestoreBackup = args[++index];
    else if (arg === '--auth-backup') options.authBackup = args[++index];
    else throw new Error(`Unknown argument: ${arg}`);
  }
  if (!options.projectId) throw new Error('--project is required.');
  if (options.execute && (
    options.confirmation !== options.projectId ||
    !/^[a-f0-9]{64}$/.test(options.inventoryDigest ?? '') ||
    !options.firestoreBackup?.startsWith('gs://') ||
    !isAbsolute(options.authBackup ?? '')
  )) {
    throw new Error('--execute requires matching project, inventory digest, Firestore export URI, and absolute Auth export path.');
  }
  return options;
}

async function inventory(db, auth) {
  const collectionNames = (await db.listCollections()).map(ref => ref.id).sort();
  const unexpectedCollections = collectionNames.filter(name =>
    !appCollections.includes(name) && !preservedCollections.includes(name));
  const documentIds = {};
  const documentVersions = {};
  for (const name of appCollections) {
    const refs = (await db.collection(name).listDocuments()).sort((a, b) => a.id.localeCompare(b.id));
    documentIds[name] = refs.map(ref => ref.id);
    documentVersions[name] = [];
    for (let offset = 0; offset < refs.length; offset += 100) {
      const snapshots = await db.getAll(...refs.slice(offset, offset + 100));
      documentVersions[name].push(...snapshots.map(snapshot => [
        snapshot.id,
        snapshot.updateTime?.seconds ?? null,
        snapshot.updateTime?.nanoseconds ?? null,
      ]));
    }
  }
  const users = [];
  let pageToken;
  do {
    const page = await auth.listUsers(1000, pageToken);
    users.push(...page.users.map(user => ({ uid: user.uid, admin: user.customClaims?.admin === true })));
    pageToken = page.pageToken;
  } while (pageToken);
  users.sort((a, b) => a.uid.localeCompare(b.uid));
  const digest = createHash('sha256').update(JSON.stringify({ collectionNames, documentVersions, users })).digest('hex');
  return { collectionNames, unexpectedCollections, documentIds, users, digest };
}

async function verifyBackups(app, options, current) {
  if (((await stat(options.authBackup)).mode & 0o077) !== 0) {
    throw new Error('Auth export must be readable only by its owner (mode 0600).');
  }
  const authExport = JSON.parse(await readFile(options.authBackup, 'utf8'));
  const exportedIds = new Set((authExport.users ?? []).map(user => user.localId));
  if (current.users.some(user => !exportedIds.has(user.uid))) {
    throw new Error('Auth export does not contain every current Auth UID.');
  }

  const match = options.firestoreBackup.match(/^gs:\/\/([^/]+)\/(.+)$/);
  if (!match) throw new Error('Firestore backup must name a specific gs://bucket/export-prefix.');
  const [, bucketName, prefix] = match;
  const [files] = await getStorage(app).bucket(bucketName).getFiles({ prefix: `${prefix}/` });
  if (!files.some(file => file.name.endsWith('.overall_export_metadata'))) {
    throw new Error('No completed Firestore export metadata found at the backup URI.');
  }
}

async function main() {
  const options = parseArguments(process.argv.slice(2));
  const usingFirestoreEmulator = Boolean(process.env.FIRESTORE_EMULATOR_HOST);
  const usingAuthEmulator = Boolean(process.env.FIREBASE_AUTH_EMULATOR_HOST);
  if (usingFirestoreEmulator !== usingAuthEmulator) throw new Error('Auth and Firestore must both use emulators, or both use production.');
  const app = initializeApp({
    projectId: options.projectId,
    ...(usingFirestoreEmulator ? {} : { credential: applicationDefault() }),
  });
  const db = getFirestore(app);
  const auth = getAuth(app);
  const current = await inventory(db, auth);
  const adminUsers = current.users.filter(user => user.admin);
  const otherUsers = current.users.filter(user => !user.admin);
  console.log(JSON.stringify({
    projectId: options.projectId,
    collectionsToClear: Object.fromEntries(appCollections.map(name => [name, current.documentIds[name].length])),
    catalogCollectionsPreserved: preservedCollections.filter(name => current.collectionNames.includes(name)),
    unexpectedCollections: current.unexpectedCollections,
    adminSignInsPreserved: adminUsers.length,
    otherAuthUsersToDelete: otherUsers.length,
    inventoryDigest: current.digest,
  }, null, 2));
  if (!options.execute) {
    console.log('Inventory only. No data was changed.');
    return;
  }
  if (!adminUsers.length) throw new Error('No admin sign-ins found; refusing to reset the project.');
  if (current.unexpectedCollections.length) throw new Error('Unexpected top-level collections found; inspect them before resetting.');
  if (current.digest !== options.inventoryDigest) throw new Error('Inventory changed since review; run the plan again.');
  await verifyBackups(app, options, current);

  for (const name of appCollections) {
    await db.recursiveDelete(db.collection(name));
    console.log(`Cleared ${name}.`);
  }
  for (let offset = 0; offset < otherUsers.length; offset += 1000) {
    const result = await auth.deleteUsers(otherUsers.slice(offset, offset + 1000).map(user => user.uid));
    if (result.failureCount) throw new Error(`${result.failureCount} Auth users could not be deleted; inspect the project before retrying.`);
  }
  console.log(`Deleted ${otherUsers.length} non-admin Auth users. Admin sign-ins remain.`);
}

main().catch(error => {
  console.error(error.message);
  process.exitCode = 1;
});
