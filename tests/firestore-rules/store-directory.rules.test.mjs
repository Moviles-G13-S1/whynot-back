import { readFileSync } from 'node:fs';
import { assertFails, assertSucceeds, initializeTestEnvironment } from '@firebase/rules-unit-testing';
import { collection, doc, getDocs, setDoc } from 'firebase/firestore';

describe('Store directory access', function () {
  let env;
  before(async function () {
    env = await initializeTestEnvironment({
      projectId: 'demo-whynot', firestore: { rules: readFileSync('firestore.rules', 'utf8') },
    });
  });
  after(async function () { await env.cleanup(); });
  it('allows signed-in catalog reads and reserves writes to the backend', async function () {
    const db = env.authenticatedContext('directory-reader').firestore();
    await assertSucceeds(getDocs(collection(db, 'stores')));
    await assertFails(getDocs(collection(env.unauthenticatedContext().firestore(), 'stores')));
    await assertFails(setDoc(doc(db, 'stores', 'directory-test'), { name: 'Example' }));
  });
});
