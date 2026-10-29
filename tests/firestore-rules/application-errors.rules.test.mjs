import { readFileSync, existsSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { assertFails, assertSucceeds, initializeTestEnvironment } from '@firebase/rules-unit-testing';
import { collection, doc, getDoc, getDocs, setDoc, updateDoc, deleteDoc, serverTimestamp, Timestamp, runTransaction } from 'firebase/firestore';

describe('Application error telemetry', function () {
  let environment;
  const id = 'a'.repeat(32);
  const record = (overrides = {}) => ({ eventId: id, schemaVersion: 1, userId: 'alice', platform: 'ios',
    feature: 'profile', operation: 'load_profile', code: 'network', source: 'operation',
    occurredAt: Timestamp.now(), createdAt: serverTimestamp(), ...overrides });
  const db = () => environment.authenticatedContext('alice').firestore();
  const ref = client => doc(client, 'applicationErrorEvents', id);
  before(async () => { environment = await initializeTestEnvironment({ projectId: 'demo-whynot', firestore: { rules: readFileSync('firestore.rules', 'utf8') } }); });
  beforeEach(async () => environment.clearFirestore());
  after(async () => environment.cleanup());

  it('allows valid owner-created telemetry', async () => assertSucceeds(setDoc(ref(db()), record())));
  it('rejects anonymous or forged ownership', async () => {
    await assertFails(setDoc(ref(environment.unauthenticatedContext().firestore()), record()));
    await assertFails(setDoc(ref(db()), record({ userId: 'bob' })));
  });
  it('rejects raw messages, unsupported categories, IDs and timestamps', async () => {
    for (const extra of [{ message: 'private input' }, { stack: 'stack' }, { code: 'validation' },
      { platform: 'desktop' }, { operation: 'alice@example.com' }, { schemaVersion: 2 },
      { eventId: 'b'.repeat(32) }, { createdAt: Timestamp.fromMillis(0) },
      { occurredAt: Timestamp.fromMillis(Date.now() + 3600000) }]) {
      await assertFails(setDoc(ref(db()), record(extra)));
    }
    await assertFails(setDoc(doc(db(), 'applicationErrorEvents', 'invalid-id'), record()));
  });
  it('requires every schema field', async () => {
    for (const key of Object.keys(record())) {
      const data = record(); delete data[key];
      await assertFails(setDoc(ref(db()), data));
    }
  });
  it('allows exact owner reads but denies other owners and collection listing', async () => {
    await assertSucceeds(setDoc(ref(db()), record()));
    await assertSucceeds(getDoc(ref(db())));
    await assertFails(getDoc(ref(environment.authenticatedContext('bob').firestore())));
    await assertFails(getDocs(collection(db(), 'applicationErrorEvents')));
    await assertSucceeds(getDocs(collection(environment.authenticatedContext('admin', { admin: true }).firestore(), 'applicationErrorEvents')));
  });
  it('never permits clients to edit or remove recorded errors', async () => {
    await assertSucceeds(setDoc(ref(db()), record()));
    await assertFails(updateDoc(ref(db()), { code: 'unexpected' }));
    await assertFails(deleteDoc(ref(db())));
  });
  it('supports idempotent transaction retries including a missing document', async () => {
    const client = db(); const target = ref(client);
    const send = () => runTransaction(client, async tx => {
      if (!(await tx.get(target)).exists()) tx.set(target, record());
    });
    await assertSucceeds(send()); await assertSucceeds(send());
    const admin = environment.authenticatedContext('admin', { admin: true }).firestore();
    const records = await getDocs(collection(admin, 'applicationErrorEvents'));
    if (records.size !== 1) throw new Error('A retry duplicated the error event');
  });

  it('feeds real Firestore events through the backend metric into dashboard HTML', async function () {
    const python = process.env.WHYNOT_PYTHON ?? (process.platform === 'win32' ? '.venv/Scripts/python.exe' : '.venv/bin/python');
    const viewUrl = new URL('../../../whynot-analytics-dashboard/src/weekly-errors-view.js', import.meta.url);
    if (!existsSync(python) || !existsSync(viewUrl)) {
      this.skip(); return; // Cross-repo test requires the local Python env and dashboard checkout.
    }
    const client = db();
    for (let i = 1; i <= 3; i++) {
      const eventId = String(i).padStart(32, '0');
      const data = record({ eventId, occurredAt: Timestamp.fromMillis(Date.now() - (i === 3 ? 7 * 86400000 : 0)) });
      await assertSucceeds(setDoc(doc(client, 'applicationErrorEvents', eventId), data));
    }
    const request = { metric: 'weekly_app_errors', params: { weeks: 4 } };
    const envelope = JSON.parse(execFileSync(python, ['tests/run_weekly_errors_metric.py', JSON.stringify(request)], { encoding: 'utf8', timeout: 20000 }));
    if (envelope.metric !== request.metric || envelope.data.totalErrors !== 3 || envelope.data.currentWeekErrors !== 2 || envelope.data.previousWeekErrors !== 1) {
      throw new Error(`Unexpected pipeline result: ${JSON.stringify(envelope)}`);
    }
    const { renderWeeklyErrors } = await import(viewUrl);
    const html = renderWeeklyErrors(envelope.data);
    if (!html.includes('3 captured errors across 4 calendar weeks') || !html.includes('Week starting')) {
      throw new Error('The dashboard did not render the backend result');
    }
  });
});
