#!/usr/bin/env node
import assert from 'node:assert/strict';
import { initializeApp as initializeAdminApp } from 'firebase-admin/app';
import { getAuth as getAdminAuth } from 'firebase-admin/auth';
import { getFirestore } from 'firebase-admin/firestore';
import { initializeApp } from 'firebase/app';
import { connectAuthEmulator, getAuth, signInWithEmailAndPassword } from 'firebase/auth';
import { connectFunctionsEmulator, getFunctions, httpsCallable } from 'firebase/functions';
import { connectFirestoreEmulator, doc, getFirestore as getClientFirestore, serverTimestamp, writeBatch } from 'firebase/firestore';

process.env.FIRESTORE_EMULATOR_HOST = '127.0.0.1:8080';
process.env.FIREBASE_AUTH_EMULATOR_HOST = '127.0.0.1:9099';
const projectId = 'demo-whynot';
const adminApp = initializeAdminApp({ projectId });
const db = getFirestore(adminApp);
const adminAuth = getAdminAuth(adminApp);
await adminAuth.createUser({ uid: 'alice', email: 'alice@example.com', password: 'Test123456!' });
await adminAuth.createUser({ uid: 'admin', email: 'admin@example.com', password: 'Test123456!' });
await adminAuth.setCustomUserClaims('admin', { admin: true });
await db.doc('categories/fashion').set({ name: 'Fashion' });
for (const id of ['full', 'empty', 'foreign']) {
  await db.doc(`wishlists/${id}`).set({ ownerId: id === 'foreign' ? 'admin' : 'alice', categoryId: 'fashion', imageUrl: '', createdAt: new Date(), updatedAt: new Date() });
}
await db.doc('products/item').set({ ownerId: 'alice', wishlistId: 'full', categoryId: 'fashion' });

function client(name, email) {
  const app = initializeApp({ apiKey: 'demo-api-key', projectId, appId: name }, name);
  const auth = getAuth(app);
  connectAuthEmulator(auth, 'http://127.0.0.1:9099', { disableWarnings: true });
  const functions = getFunctions(app, 'us-central1');
  connectFunctionsEmulator(functions, '127.0.0.1', 5001);
  const firestore = getClientFirestore(app);
  connectFirestoreEmulator(firestore, '127.0.0.1', 8080);
  return { auth, firestore, callable: httpsCallable(functions, 'delete_empty_wishlist'), analytics: httpsCallable(functions, 'get_admin_analytics'), email };
}
const alice = client('alice-client', 'alice@example.com');
await signInWithEmailAndPassword(alice.auth, alice.email, 'Test123456!');
const edit = writeBatch(alice.firestore);
edit.update(doc(alice.firestore, 'wishlists/full'), { imageUrl: 'https://example.com/new.jpg', emoji: '🎁', updatedAt: serverTimestamp() });
edit.set(doc(alice.firestore, 'wishlistInteractionEvents/edit-op'), {
  action: 'edit', outcome: 'success', reason: 'none', userId: 'alice',
  wishlistId: 'full', categoryId: 'fashion', platform: 'web',
  operationId: 'edit-op', schemaVersion: 1, createdAt: serverTimestamp(),
});
await edit.commit();
assert.equal((await db.doc('wishlists/full').get()).data().emoji, '🎁');
const blocked = (await alice.callable({ wishlistId: 'full', operationId: 'blocked-op', platform: 'web' })).data;
assert.deepEqual(blocked, { outcome: 'blocked', reason: 'nonempty' });
assert.equal((await db.doc('products/item').get()).exists, true);
assert.equal((await db.doc('wishlists/full').get()).exists, true);
const deleted = (await alice.callable({ wishlistId: 'empty', operationId: 'delete-op', platform: 'web' })).data;
assert.deepEqual(deleted, { outcome: 'success', reason: 'none' });
assert.equal((await db.doc('wishlists/empty').get()).exists, false);
assert.deepEqual((await alice.callable({ wishlistId: 'empty', operationId: 'delete-op', platform: 'web' })).data, deleted);
assert.equal((await db.collection('wishlistInteractionEvents').get()).size, 3);
assert.deepEqual((await alice.callable({ wishlistId: 'foreign', operationId: 'foreign-op', platform: 'web' })).data, { outcome: 'failure', reason: 'not_found' });
assert.equal((await db.doc('wishlists/foreign').get()).exists, true);
const admin = client('admin-client', 'admin@example.com');
await signInWithEmailAndPassword(admin.auth, admin.email, 'Test123456!');
const metric = (await admin.analytics({ metric: 'wishlist_interactions' })).data.data;
assert.equal(metric.actions.delete.outcomes.success, 1);
assert.equal(metric.actions.delete.outcomes.blocked, 1);
assert.equal(metric.actions.delete.outcomes.failure, 1);
assert.equal(metric.actions.edit.outcomes.success, 1);
console.log('Wishlist edit, delete callable, and analytics emulator integration passed.');
process.exit(0);
