import { readFileSync } from 'node:fs';
import { assertFails, assertSucceeds, initializeTestEnvironment } from '@firebase/rules-unit-testing';
import { doc, setDoc, getDoc, updateDoc, deleteDoc, serverTimestamp, Timestamp } from 'firebase/firestore';

describe('Sprint 4 nearby store detail opened events', function () {
  let environment;
  const record = (overrides = {}) => ({
    userId: 'jf-test', eventName: 'nearby_store_detail_opened',
    source: 'home_nearby_store', platform: 'android', createdAt: serverTimestamp(), ...overrides,
  });
  const target = (db) => doc(db, 'uxEvents', 'nearby-event');
  const userDb = () => environment.authenticatedContext('jf-test').firestore();

  before(async function () {
    environment = await initializeTestEnvironment({
      projectId: 'demo-whynot', firestore: { rules: readFileSync('firestore.rules', 'utf8') },
    });
  });
  beforeEach(async function () { await environment.clearFirestore(); });
  after(async function () { await environment.cleanup(); });

  it('allows the event from both apps for its signed-in owner', async function () {
    const db = userDb();
    await assertSucceeds(setDoc(doc(db, 'uxEvents', 'android'), record()));
    await assertSucceeds(setDoc(doc(db, 'uxEvents', 'ios'), record({ platform: 'ios' })));
  });
  it('rejects signed-out writes and forged user ids', async function () {
    await assertFails(setDoc(target(environment.unauthenticatedContext().firestore()), record()));
    await assertFails(setDoc(target(userDb()), record({ userId: 'someone-else' })));
  });
  it('rejects other sources, platforms, extra fields and client timestamps', async function () {
    for (const overrides of [{ source: 'home_empty_state' }, { platform: 'web' }, { extra: true },
      { createdAt: Timestamp.fromMillis(0) }]) {
      await assertFails(setDoc(target(userDb()), record(overrides)));
    }
  });
  it('keeps the Home empty-state events Android only', async function () {
    await assertFails(setDoc(target(userDb()), record({
      eventName: 'home_empty_state_clicked', source: 'home_empty_state', platform: 'ios',
    })));
  });
  it('is write-once and only admins can read it', async function () {
    const ref = target(userDb());
    await assertSucceeds(setDoc(ref, record()));
    await assertFails(getDoc(ref));
    await assertFails(updateDoc(ref, { platform: 'ios' }));
    await assertFails(deleteDoc(ref));
    const adminDb = environment.authenticatedContext('admin-test', { admin: true }).firestore();
    await assertSucceeds(getDoc(target(adminDb)));
  });
});
