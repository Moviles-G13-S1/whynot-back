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

const currentEmail = 'current@example.com';
const similarEmail = 'similar@example.com';

const password = 'Test123456!';


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
  const firestore = getFirestore(adminApp);

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

  await firestore
    .collection('users')
    .doc(currentUid)
    .set({
      name: 'Current User',
      email: currentEmail,
      gender: 'Female',
      age: 22,
      preferredCategoryId: 'fashion',
    });

  await firestore
    .collection('users')
    .doc(similarUid)
    .set({
      name: 'Similar User',
      email: similarEmail,
      gender: 'Female',
      age: 23,
      preferredCategoryId: 'fashion',
    });

  await firestore
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
    });

  await firestore
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
    });

  console.log('Local test data seeded.');
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
}


async function main() {
  await seedData();
  await testFunctions();
}


main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});