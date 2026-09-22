#!/usr/bin/env node

import { applicationDefault, initializeApp } from 'firebase-admin/app';
import { getFirestore } from 'firebase-admin/firestore';

// Initial catalog based on DANE's list of main Colombian cities.
const cities = new Map([
  ['armenia', 'Armenia'],
  ['barranquilla', 'Barranquilla'],
  ['bogota', 'Bogotá'],
  ['bucaramanga', 'Bucaramanga'],
  ['cali', 'Cali'],
  ['cartagena', 'Cartagena'],
  ['cucuta', 'Cúcuta'],
  ['florencia', 'Florencia'],
  ['ibague', 'Ibagué'],
  ['manizales', 'Manizales'],
  ['medellin', 'Medellín'],
  ['monteria', 'Montería'],
  ['neiva', 'Neiva'],
  ['pasto', 'Pasto'],
  ['pereira', 'Pereira'],
  ['popayan', 'Popayán'],
  ['quibdo', 'Quibdó'],
  ['riohacha', 'Riohacha'],
  ['san-andres', 'San Andrés'],
  ['santa-marta', 'Santa Marta'],
  ['sincelejo', 'Sincelejo'],
  ['tunja', 'Tunja'],
  ['valledupar', 'Valledupar'],
  ['villavicencio', 'Villavicencio'],
  ['other', 'Other'],
]);

const argumentsList = process.argv.slice(2);
const projectIndex = argumentsList.indexOf('--project');
const projectId = projectIndex >= 0 ? argumentsList[projectIndex + 1] : null;
const dryRun = argumentsList.includes('--dry-run');
if (!projectId) {
  throw new Error('Usage: npm run seed:cities -- --project <project-id> [--dry-run]');
}

const usingEmulator = Boolean(process.env.FIRESTORE_EMULATOR_HOST);
const app = initializeApp({
  projectId,
  ...(usingEmulator ? {} : { credential: applicationDefault() }),
});
const firestore = getFirestore(app);
const batch = firestore.batch();
let created = 0;
let updated = 0;
let unchanged = 0;

for (const [cityId, name] of cities) {
  const reference = firestore.collection('cities').doc(cityId);
  const snapshot = await reference.get();
  if (!snapshot.exists) {
    created += 1;
    batch.set(reference, { name }, { merge: true });
  } else if (snapshot.data()?.name !== name) {
    updated += 1;
    batch.set(reference, { name }, { merge: true });
  } else {
    unchanged += 1;
  }
}

console.log(`${dryRun ? 'Would seed' : 'Seeding'} cities in ${projectId}`);
console.log(`created=${created} updated=${updated} unchanged=${unchanged}`);
if (!dryRun && (created > 0 || updated > 0)) await batch.commit();
console.log(dryRun ? 'Dry run complete.' : 'City seed complete.');
