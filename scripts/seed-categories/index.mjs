#!/usr/bin/env node

import { applicationDefault, initializeApp } from 'firebase-admin/app';
import { getFirestore } from 'firebase-admin/firestore';

const categories = new Map([
  ['fashion', 'Fashion'],
  ['beauty', 'Beauty'],
  ['technology', 'Technology'],
  ['home', 'Home'],
  ['accessories', 'Accessories'],
  ['travel', 'Travel'],
  ['gifts', 'Gifts'],
  ['other', 'Other'],
]);

function usage() {
  return [
    'Usage:',
    '  npm run seed:categories -- --project <project-id> [--dry-run]',
  ].join('\n');
}

function parseArguments(argumentsList) {
  const options = {
    projectId: null,
    dryRun: false,
  };

  for (let index = 0; index < argumentsList.length; index += 1) {
    const argument = argumentsList[index];

    if (argument === '--project') {
      options.projectId = argumentsList[index + 1] ?? null;
      index += 1;
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

  return options;
}

async function main() {
  const options = parseArguments(process.argv.slice(2));
  const usingEmulator = Boolean(process.env.FIRESTORE_EMULATOR_HOST);

  const app = initializeApp({
    projectId: options.projectId,
    ...(usingEmulator ? {} : { credential: applicationDefault() }),
  });
  const firestore = getFirestore(app);
  const batch = firestore.batch();
  const summary = { created: 0, updated: 0, unchanged: 0 };

  for (const [categoryId, name] of categories) {
    const reference = firestore.collection('categories').doc(categoryId);
    const snapshot = await reference.get();

    if (!snapshot.exists) {
      summary.created += 1;
      batch.set(reference, { name }, { merge: true });
    } else if (snapshot.data()?.name !== name) {
      summary.updated += 1;
      batch.set(reference, { name }, { merge: true });
    } else {
      summary.unchanged += 1;
    }
  }

  console.log(
    `${options.dryRun ? 'Would seed' : 'Seeding'} categories in ${options.projectId}`,
  );
  console.log(
    `created=${summary.created} updated=${summary.updated} unchanged=${summary.unchanged}`,
  );

  if (!options.dryRun && (summary.created > 0 || summary.updated > 0)) {
    await batch.commit();
  }

  if (options.dryRun) {
    console.log('Dry run complete; no documents were changed.');
  } else {
    console.log('Category seed complete.');
  }
}

main().catch((error) => {
  console.error(error.message);
  process.exitCode = 1;
});
