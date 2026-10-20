#!/usr/bin/env node

process.env.FIRESTORE_EMULATOR_HOST = '127.0.0.1:8080';
process.env.FIREBASE_AUTH_EMULATOR_HOST = '127.0.0.1:9099';

import { initializeApp as initializeAdminApp } from 'firebase-admin/app';
import { getAuth as getAdminAuth } from 'firebase-admin/auth';
import { getFirestore } from 'firebase-admin/firestore';

import { initializeApp as initializeClientApp } from 'firebase/app';
import {
  connectAuthEmulator,
  getAuth,
  signInWithEmailAndPassword,
} from 'firebase/auth';
import {
  connectFunctionsEmulator,
  getFunctions,
  httpsCallable,
} from 'firebase/functions';


const projectId = 'demo-whynot';

const currentUid = 'current-user';
const similarUid = 'similar-user';
const adminUid = 'analytics-admin';

const currentEmail = 'current@example.com';
const similarEmail = 'similar@example.com';
const adminEmail = 'analytics-admin@example.com';

const password = 'Test123456!';

let adminFirestore;


async function ensureAuthUser(auth, uid, email) {
  try {
    await auth.getUser(uid);
  } catch {
    await auth.createUser({
      uid,
      email,
      password,
    });
  }
}


async function seedData() {
  const adminApp = initializeAdminApp({
    projectId,
  });

  const auth = getAdminAuth(adminApp);
  adminFirestore = getFirestore(adminApp);

  await ensureAuthUser(
    auth,
    currentUid,
    currentEmail,
  );

  await ensureAuthUser(
    auth,
    similarUid,
    similarEmail,
  );

  await ensureAuthUser(auth, adminUid, adminEmail);
  await auth.setCustomUserClaims(adminUid, { admin: true });

  await adminFirestore
    .collection('categories')
    .doc('fashion')
    .set({
      name: 'Fashion',
    });

  await adminFirestore
    .collection('users')
    .doc(currentUid)
    .set({
      name: 'Current User',
      email: currentEmail,
      gender: 'Female',
      age: 22,
      preferredCategoryId: 'fashion',
    });

  await adminFirestore
    .collection('users')
    .doc(similarUid)
    .set({
      name: 'Similar User',
      email: similarEmail,
      gender: 'Female',
      age: 23,
      preferredCategoryId: 'fashion',
    });

  await adminFirestore
    .collection('wishlists')
    .doc('current-fashion')
    .set({
      ownerId: currentUid,
      categoryId: 'fashion',
      imageUrl: '',
    });

  await adminFirestore
    .collection('wishlists')
    .doc('similar-fashion')
    .set({
      ownerId: similarUid,
      categoryId: 'fashion',
      imageUrl: '',
    });

  await adminFirestore
    .collection('products')
    .doc('current-product')
    .set({
      ownerId: currentUid,
      wishlistId: 'current-fashion',
      categoryId: 'fashion',
      name: 'Basic Shirt',
      brand: 'Example',
      price: 100000,
      imageUrl: '',
      productUrl: 'https://example.com/basic-shirt',
      purchased: false,
      purchasedAt: null,
    });

  await adminFirestore
    .collection('products')
    .doc('recommended-product')
    .set({
      ownerId: similarUid,
      wishlistId: 'similar-fashion',
      categoryId: 'fashion',
      name: 'Black Jacket',
      brand: 'Example Brand',
      price: 250000,
      imageUrl: '',
      productUrl: 'https://example.com/black-jacket',
      purchased: true,
      purchasedAt: new Date(),
    });

  // The closest store overall belongs to another category. The nearby-store
  // function must still prefer the closest store in the user's preferred
  // category instead of returning this one.
  await adminFirestore
    .collection('stores')
    .doc('technology-closer')
    .set({
      name: 'Technology Store',
      address: 'Test address 1',
      latitude: 4.6669,
      longitude: -74.0531,
      categoryIds: ['technology'],
      websiteUrl: 'https://example.com/technology',
      imageUrl: '',
    });

  await adminFirestore
    .collection('stores')
    .doc('fashion-near')
    .set({
      name: 'Fashion Store Near',
      address: 'Test address 2',
      latitude: 4.6670,
      longitude: -74.0532,
      categoryIds: ['fashion'],
      websiteUrl: 'https://example.com/fashion-near',
      imageUrl: '',
    });

  await adminFirestore
    .collection('stores')
    .doc('fashion-far')
    .set({
      name: 'Fashion Store Far',
      address: 'Test address 3',
      latitude: 4.7022,
      longitude: -74.0415,
      categoryIds: ['fashion'],
      websiteUrl: 'https://example.com/fashion-far',
      imageUrl: '',
    });

  console.log('Local test data seeded.');
}


async function testRecommendationSave(
  recommendation,
  functions,
) {
  const eventId = recommendation.recommendationEventId;

  if (!eventId) {
    throw new Error(
      'Recommendation did not include recommendationEventId.',
    );
  }

  const eventBeforeSave = await adminFirestore
    .collection('productEvents')
    .doc(eventId)
    .get();

  if (!eventBeforeSave.exists) {
    throw new Error(
      'Recommendation event was not created in productEvents.',
    );
  }

  const saveRecommendedProduct = httpsCallable(
    functions,
    'save_recommended_product',
  );

  const firstSaveResult = await saveRecommendedProduct({
    recommendationEventId: eventId,
    wishlistId: 'current-fashion',
  });

  console.log(
    '\nFirst recommendation save:',
    firstSaveResult.data,
  );

  if (!firstSaveResult.data.saved) {
    throw new Error('Recommended product was not saved.');
  }

  if (firstSaveResult.data.alreadySaved) {
    throw new Error(
      'First recommendation save was incorrectly marked as duplicate.',
    );
  }

  const secondSaveResult = await saveRecommendedProduct({
    recommendationEventId: eventId,
    wishlistId: 'current-fashion',
  });

  console.log(
    '\nRepeated recommendation save:',
    secondSaveResult.data,
  );

  if (!secondSaveResult.data.alreadySaved) {
    throw new Error(
      'Repeated save should be idempotent and report alreadySaved.',
    );
  }

  const eventAfterSave = await adminFirestore
    .collection('productEvents')
    .doc(eventId)
    .get();

  if (!eventAfterSave.data().savedAt) {
    throw new Error(
      'Recommendation event was not marked as saved.',
    );
  }

  if (!eventAfterSave.data().savedProductId) {
    throw new Error(
      'Recommendation event has no savedProductId.',
    );
  }

  const savedProduct = await adminFirestore
    .collection('products')
    .doc(eventAfterSave.data().savedProductId)
    .get();

  if (!savedProduct.exists) {
    throw new Error(
      'Saved recommendation product document does not exist.',
    );
  }

  if (savedProduct.data().ownerId !== currentUid) {
    throw new Error(
      'Saved recommendation product has the wrong owner.',
    );
  }

  if (savedProduct.data().purchased !== false) {
    throw new Error(
      'A recommended save must create the new product as unpurchased.',
    );
  }

  const events = await adminFirestore.collection('productEvents').get();
  const saved = events.docs.filter(doc =>
    doc.data().eventType === 'recommendation_shown' &&
    doc.data().savedAt && doc.data().savedProductId);
  if (saved.length !== 1) {
    throw new Error(`Expected one successful BQ3 event, got ${saved.length}.`);
  }
}


async function testFunctions() {
  const clientApp = initializeClientApp(
    {
      apiKey: 'demo-api-key',
      projectId,
      appId: 'demo-app-id',
    },
    'smart-feature-test',
  );

  const auth = getAuth(clientApp);

  connectAuthEmulator(
    auth,
    'http://127.0.0.1:9099',
    {
      disableWarnings: true,
    },
  );

  await signInWithEmailAndPassword(
    auth,
    currentEmail,
    password,
  );

  const functions = getFunctions(
    clientApp,
    'us-central1',
  );

  connectFunctionsEmulator(
    functions,
    '127.0.0.1',
    5001,
  );

  const getRecommendation = httpsCallable(
    functions,
    'get_recommendation',
  );

  const recommendationResult =
    await getRecommendation();

  console.log(
    '\nRecommendation result:',
    recommendationResult.data,
  );

  const recommendation = recommendationResult
    .data
    .recommendation;

  if (!recommendation) {
    throw new Error('No recommendation was returned.');
  }

  await testRecommendationSave(
    recommendation,
    functions,
  );

  const analytics = httpsCallable(functions, 'get_admin_analytics');
  try {
    await analytics({ metric: 'recommended' });
    throw new Error('Regular user was allowed to read analytics.');
  } catch (error) {
    if (error.code !== 'functions/permission-denied') throw error;
  }

  const adminApp = initializeClientApp(
    { apiKey: 'demo-api-key', projectId, appId: 'admin-test-app' },
    'analytics-admin-test',
  );
  const adminClientAuth = getAuth(adminApp);
  connectAuthEmulator(adminClientAuth, 'http://127.0.0.1:9099', { disableWarnings: true });
  await signInWithEmailAndPassword(adminClientAuth, adminEmail, password);
  const adminFunctions = getFunctions(adminApp, 'us-central1');
  connectFunctionsEmulator(adminFunctions, '127.0.0.1', 5001);
  const bq3 = await httpsCallable(adminFunctions, 'get_admin_analytics')({ metric: 'recommended' });
  if (bq3.data.data.total !== 1) {
    throw new Error(`Expected BQ3 total 1, got ${bq3.data.data.total}.`);
  }
  const adminAnalytics = httpsCallable(adminFunctions, 'get_admin_analytics');
  const saved = await adminAnalytics({ metric: 'saved' });
  if (saved.data.data.totalProducts !== 3 || saved.data.data.activeUsers !== 2) {
    throw new Error('Saved-products summary did not match seeded products.');
  }
  const purchased = await adminAnalytics({ metric: 'purchased', params: { months: 6 } });
  if (purchased.data.data.currentMonthCount !== 1) {
    throw new Error('Purchase summary did not match seeded purchase.');
  }
  const demographic = await adminAnalytics({ metric: 'demographic', params: { categoryId: 'fashion' } });
  if (demographic.data.data.userCount !== 2 || demographic.data.data.categories[0].name !== 'Fashion') {
    throw new Error('Demographic summary did not match seeded users.');
  }
  console.log('\nAll four admin analytics views returned processed results.');

  const getNearestStore = httpsCallable(
    functions,
    'get_nearest_store',
  );

  const storeResult = await getNearestStore({
    latitude: 4.6669,
    longitude: -74.0531,
  });

  console.log(
    '\nNearest store result:',
    storeResult.data,
  );

  const store = storeResult.data.store;

  if (!store) {
    throw new Error('No nearby store was returned.');
  }

  if (store.id !== 'fashion-near') {
    throw new Error(
      `Expected fashion-near, got ${store.id}.`,
    );
  }

  if (!store.categoryIds.includes('fashion')) {
    throw new Error(
      'Nearby store did not match the preferred category.',
    );
  }

  if (typeof store.distanceKm !== 'number') {
    throw new Error(
      'Nearby store did not include a numeric distanceKm.',
    );
  }
}


async function main() {
  await seedData();
  await testFunctions();
}


main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
