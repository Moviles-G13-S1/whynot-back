import { readFileSync } from 'node:fs';
import { assertFails, assertSucceeds, initializeTestEnvironment } from '@firebase/rules-unit-testing';
import { doc, setDoc, getDoc, updateDoc, deleteDoc, serverTimestamp, Timestamp } from 'firebase/firestore';

describe('Flutter Home recommendation events', function () {
  let environment;
  const impressionId = 'a'.repeat(32);
  const data = (overrides = {}) => ({ userId: 'santiago-test', platform: 'flutter', eventType: 'card_displayed',
    impressionId, recommendationEventId: 'recommendation-1', createdAt: serverTimestamp(), ...overrides });
  const db = () => environment.authenticatedContext('santiago-test').firestore();
  const ref = (database, suffix = 'display') => doc(database, 'recommendationHomeEvents', `${impressionId}_${suffix}`);

  before(async () => { environment = await initializeTestEnvironment({ projectId: 'demo-whynot', firestore: { rules: readFileSync('firestore.rules', 'utf8') } }); });
  beforeEach(async () => {
    await environment.clearFirestore();
    await environment.withSecurityRulesDisabled(async context => {
      await setDoc(doc(context.firestore(), 'productEvents', 'recommendation-1'), { userId: 'santiago-test', eventType: 'recommendation_shown' });
      await setDoc(doc(context.firestore(), 'productEvents', 'other-recommendation'), { userId: 'other', eventType: 'recommendation_shown' });
    });
  });
  after(async () => { await environment.cleanup(); });

  it('allows one owner-bound display and open with paired IDs', async () => {
    await assertSucceeds(setDoc(ref(db()), data()));
    await assertSucceeds(setDoc(ref(db(), 'open'), data({ eventType: 'detail_opened' })));
    await assertFails(setDoc(ref(db()), data()));
  });
  it('rejects anonymous, forged, malformed, and extra-field writes', async () => {
    await assertFails(setDoc(ref(environment.unauthenticatedContext().firestore()), data()));
    for (const overrides of [{ userId: 'other' }, { platform: 'android' }, { eventType: 'fake' },
      { impressionId: 'short' }, { recommendationEventId: '' }, { recommendationEventId: 'missing' },
      { recommendationEventId: 'other-recommendation' }, { createdAt: Timestamp.fromMillis(0) }, { extra: true }]) {
      await assertFails(setDoc(ref(db()), data(overrides)));
    }
    await assertFails(setDoc(ref(db(), 'open'), data()));
  });
  it('keeps events admin-read and immutable', async () => {
    await assertSucceeds(setDoc(ref(db()), data()));
    await assertFails(getDoc(ref(db())));
    await assertFails(updateDoc(ref(db()), { platform: 'android' }));
    await assertFails(deleteDoc(ref(db())));
    await assertSucceeds(getDoc(ref(environment.authenticatedContext('admin', { admin: true }).firestore())));
  });
});
