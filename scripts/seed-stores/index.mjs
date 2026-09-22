#!/usr/bin/env node

import { applicationDefault, initializeApp } from 'firebase-admin/app';
import { getFirestore } from 'firebase-admin/firestore';


const stores = new Map([
  // -------------------------------------------------------------------------
  // Fashion
  // -------------------------------------------------------------------------

  [
    'zara-andino',
    {
      name: 'ZARA - Andino',
      address: 'Calle 82 #12-22, Bogotá',
      latitude: 4.66691,
      longitude: -74.05312,
      categoryIds: [
        'fashion',
      ],
      websiteUrl: 'https://www.zara.com/co/',
      imageUrl: '',
    },
  ],

  [
    'hm-mallplaza-nqs',
    {
      name: 'H&M - Mallplaza NQS',
      address: 'Avenida Carrera 30 #19, Bogotá',
      latitude: 4.61815,
      longitude: -74.08599,
      categoryIds: [
        'fashion',
      ],
      websiteUrl: 'https://www2.hm.com/es_co/index.html',
      imageUrl: '',
    },
  ],

  // -------------------------------------------------------------------------
  // Beauty
  // -------------------------------------------------------------------------

  [
    'loto-del-sur-andino',
    {
      name: 'Loto del Sur - Andino',
      address: 'Carrera 11 #82-71, Bogotá',
      latitude: 4.66691,
      longitude: -74.05312,
      categoryIds: [
        'beauty',
      ],
      websiteUrl: 'https://www.lotodelsur.com/',
      imageUrl: '',
    },
  ],

  [
    'loto-del-sur-unicentro',
    {
      name: 'Loto del Sur - Unicentro',
      address: 'Avenida Carrera 15 #124-30, Bogotá',
      latitude: 4.70220,
      longitude: -74.04150,
      categoryIds: [
        'beauty',
      ],
      websiteUrl: 'https://www.lotodelsur.com/',
      imageUrl: '',
    },
  ],

  // -------------------------------------------------------------------------
  // Technology
  // -------------------------------------------------------------------------

  [
    'ktronix-unicentro',
    {
      name: 'Ktronix Unicentro',
      address: 'Avenida Carrera 15 #122-59, Bogotá',
      latitude: 4.70220,
      longitude: -74.04150,
      categoryIds: [
        'technology',
      ],
      websiteUrl: 'https://www.ktronix.com/',
      imageUrl: '',
    },
  ],

  [
    'ktronix-mallplaza-nqs',
    {
      name: 'Ktronix Mallplaza NQS',
      address: 'Mallplaza NQS, Avenida Ciudad de Lima #28-80, Bogotá',
      latitude: 4.61815,
      longitude: -74.08599,
      categoryIds: [
        'technology',
      ],
      websiteUrl: 'https://www.ktronix.com/',
      imageUrl: '',
    },
  ],

  // -------------------------------------------------------------------------
  // Home
  // -------------------------------------------------------------------------

  [
    'homecenter-cedritos',
    {
      name: 'Homecenter Cedritos',
      address: 'Avenida Carrera 9 #152A-23, Bogotá',
      latitude: 4.7305689,
      longitude: -74.0327445,
      categoryIds: [
        'home',
      ],
      websiteUrl: 'https://www.homecenter.com.co/',
      imageUrl: '',
    },
  ],

  [
    'ikea-nqs',
    {
      name: 'IKEA NQS',
      address: 'Mallplaza NQS, Avenida Carrera 30 #19, Bogotá',
      latitude: 4.61815,
      longitude: -74.08599,
      categoryIds: [
        'home',
      ],
      websiteUrl: 'https://www.ikea.com/co/es/',
      imageUrl: '',
    },
  ],

  // -------------------------------------------------------------------------
  // Accessories
  // -------------------------------------------------------------------------

  [
    'tous-andino',
    {
      name: 'TOUS C.C. Andino',
      address: 'Carrera 11 #82-71, Bogotá',
      latitude: 4.66691,
      longitude: -74.05312,
      categoryIds: [
        'accessories',
      ],
      websiteUrl: 'https://www.tous.com/co-es/',
      imageUrl: '',
    },
  ],

  [
    'pandora-unicentro',
    {
      name: 'Pandora Unicentro',
      address: 'Avenida Carrera 15 #124-30, Bogotá',
      latitude: 4.70220,
      longitude: -74.04150,
      categoryIds: [
        'accessories',
      ],
      websiteUrl: 'https://co.pandora.net/',
      imageUrl: '',
    },
  ],

  // -------------------------------------------------------------------------
  // Travel
  // -------------------------------------------------------------------------

  [
    'roncato-andino',
    {
      name: 'Roncato C.C. Andino',
      address: 'Carrera 11 #82-71, Local 229, Bogotá',
      latitude: 4.66691,
      longitude: -74.05312,
      categoryIds: [
        'travel',
      ],
      websiteUrl: '',
      imageUrl: '',
    },
  ],

  [
    'samsonite-unicentro',
    {
      name: 'Samsonite Unicentro',
      address: 'Avenida Carrera 15 #124-30, Local 1-037, Bogotá',
      latitude: 4.70220,
      longitude: -74.04150,
      categoryIds: [
        'travel',
      ],
      websiteUrl: 'https://www.samsonite.com.co/',
      imageUrl: '',
    },
  ],

  // -------------------------------------------------------------------------
  // Gifts
  // -------------------------------------------------------------------------

  [
    'miniso-mallplaza-nqs',
    {
      name: 'Miniso Mallplaza NQS',
      address: 'Avenida Carrera 30 con Calle 19, Bogotá',
      latitude: 4.61815,
      longitude: -74.08599,
      categoryIds: [
        'gifts',
      ],
      websiteUrl: 'https://www.miniso.co/',
      imageUrl: '',
    },
  ],

  [
    'miniso-unicentro-occidente',
    {
      name: 'Miniso Unicentro de Occidente',
      address: 'Carrera 111C #86-05, Bogotá',
      latitude: 4.72333,
      longitude: -74.11448,
      categoryIds: [
        'gifts',
      ],
      websiteUrl: 'https://www.miniso.co/',
      imageUrl: '',
    },
  ],

  // -------------------------------------------------------------------------
  // Other
  // -------------------------------------------------------------------------

  [
    'falabella-unicentro',
    {
      name: 'Falabella Unicentro',
      address: 'Avenida Carrera 15 #123-30, Bogotá',
      latitude: 4.70220,
      longitude: -74.04150,
      categoryIds: [
        'other',
      ],
      websiteUrl: 'https://www.falabella.com.co/',
      imageUrl: '',
    },
  ],

  [
    'exito-mallplaza-nqs',
    {
      name: 'Éxito Mallplaza NQS',
      address: 'Avenida Carrera 30 #19, Bogotá',
      latitude: 4.61815,
      longitude: -74.08599,
      categoryIds: [
        'other',
      ],
      websiteUrl: 'https://www.exito.com/',
      imageUrl: '',
    },
  ],
]);


function usage() {
  return [
    'Usage:',
    '  npm run seed:stores -- --project <project-id> [--dry-run]',
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

  const usingEmulator = Boolean(
    process.env.FIRESTORE_EMULATOR_HOST,
  );

  const app = initializeApp({
    projectId: options.projectId,
    ...(usingEmulator
      ? {}
      : { credential: applicationDefault() }),
  });

  const firestore = getFirestore(app);
  const batch = firestore.batch();

  console.log(
    `${
      options.dryRun ? 'Would seed' : 'Seeding'
    } ${stores.size} stores in ${options.projectId}`,
  );

  for (const [storeId, store] of stores) {
    const reference = firestore
      .collection('stores')
      .doc(storeId);

    console.log(
      `- ${storeId} [${store.categoryIds.join(', ')}]`,
    );

    if (!options.dryRun) {
      batch.set(
        reference,
        store,
        { merge: true },
      );
    }
  }

  if (options.dryRun) {
    console.log(
      'Dry run complete; no documents were changed.',
    );
    return;
  }

  await batch.commit();

  console.log('Store seed complete.');
}


main().catch((error) => {
  console.error(error.message);
  process.exitCode = 1;
});