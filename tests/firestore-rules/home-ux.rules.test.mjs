import { readFileSync } from 'node:fs';
import { assertFails, assertSucceeds, initializeTestEnvironment } from '@firebase/rules-unit-testing';
import { doc, setDoc, getDoc, updateDoc, deleteDoc, serverTimestamp, Timestamp } from 'firebase/firestore';

describe('Martin Home UX events', function () {
  let environment;
  const record = (overrides = {}) => ({
    userId: 'martin-test', eventName: 'home_empty_state_clicked',
    source: 'home_empty_state', platform: 'android', createdAt: serverTimestamp(), ...overrides,
  });
  const target = (db) => doc(db, 'uxEvents', 'martin-event');
  const userDb = () => environment.authenticatedContext('martin-test').firestore();

  before(async function () {
    environment = await initializeTestEnvironment({
      projectId: 'demo-whynot', firestore: { rules: readFileSync('firestore.rules', 'utf8') },
    });
  });
  beforeEach(async function () { await environment.clearFirestore(); });
  after(async function () { await environment.cleanup(); });

  it('allows each supported event for its signed-in owner', async function () {
    const db = userDb();
    for (const eventName of ['home_empty_state_viewed', 'home_empty_state_clicked', 'add_product_navigation']) {
      await assertSucceeds(setDoc(doc(db, 'uxEvents', eventName), record({ eventName })));
    }
  });
  it('rejects signed-out writes', async function () {
    await assertFails(setDoc(target(environment.unauthenticatedContext().firestore()), record()));
  });
  it('rejects a forged user id', async function () {
    await assertFails(setDoc(target(userDb()), record({ userId: 'someone-else' })));
  });
  it('rejects unsupported fields, events, platforms and timestamps', async function () {
    for (const overrides of [{ extra: true }, { eventName: 'fake' }, { source: 'fake' },
      { platform: 'web' }, { createdAt: Timestamp.fromMillis(0) }]) {
      await assertFails(setDoc(target(userDb()), record(overrides)));
    }
  });
  it('rejects missing fields', async function () {
    const data = record();
    delete data.source;
    await assertFails(setDoc(target(userDb()), data));
  });
  it('prevents ordinary users from reading, updating or deleting events', async function () {
    const ref = target(userDb());
    await assertSucceeds(setDoc(ref, record()));
    await assertFails(getDoc(ref));
    await assertFails(updateDoc(ref, { source: 'home_bottom_bar' }));
    await assertFails(deleteDoc(ref));
  });
  it('allows admin reads', async function () {
    await assertSucceeds(setDoc(target(userDb()), record()));
    const adminDb = environment.authenticatedContext('admin-test', { admin: true }).firestore();
    await assertSucceeds(getDoc(target(adminDb)));
  });
});
