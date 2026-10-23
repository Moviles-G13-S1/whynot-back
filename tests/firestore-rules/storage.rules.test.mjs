import { readFileSync } from 'node:fs';
import { assertFails, assertSucceeds, initializeTestEnvironment } from '@firebase/rules-unit-testing';
import { ref, uploadBytes, getBytes, deleteObject } from 'firebase/storage';

let env;
const bucket = 'demo-whynot.appspot.com';
const path = 'profilePhotos/alice/123-456.jpg';
const jpeg = new Uint8Array([0xff, 0xd8, 0xff, 0xd9]);

before(async () => {
  env = await initializeTestEnvironment({
    projectId: 'demo-whynot',
    storage: { rules: readFileSync('storage.rules', 'utf8') },
  });
});

after(async () => { await env.cleanup(); });
beforeEach(async () => { await env.clearStorage(); });

// Santiago Casasbuenas: Resolve a test image in the emulator bucket.
function photo(context, target = path) {
  return ref(context.storage(bucket), target);
}

describe('profile photo storage', () => {
  // Santiago Casasbuenas: Check owner-only image access.
  it('lets only the owner upload, read, and delete', async () => {
    const alice = env.authenticatedContext('alice');
    const bob = env.authenticatedContext('bob');
    const guest = env.unauthenticatedContext();
    await assertFails(uploadBytes(photo(bob), jpeg, { contentType: 'image/jpeg' }));
    await assertFails(uploadBytes(photo(guest), jpeg, { contentType: 'image/jpeg' }));
    await assertSucceeds(uploadBytes(photo(alice), jpeg, { contentType: 'image/jpeg' }));
    await assertSucceeds(getBytes(photo(alice)));
    await assertFails(getBytes(photo(bob)));
    await assertFails(getBytes(photo(guest)));
    await assertSucceeds(deleteObject(photo(alice)));
  });

  // Santiago Casasbuenas: Check upload type, size, and path limits.
  it('rejects wrong MIME type, oversized files, and arbitrary paths', async () => {
    const alice = env.authenticatedContext('alice');
    await assertFails(uploadBytes(photo(alice), jpeg, { contentType: 'text/plain' }));
    await assertFails(uploadBytes(photo(alice), new Uint8Array(5 * 1024 * 1024 + 1), { contentType: 'image/jpeg' }));
    await assertFails(uploadBytes(photo(alice, 'profilePhotos/alice/invalid.jpg'), jpeg, { contentType: 'image/jpeg' }));
    await assertFails(uploadBytes(photo(alice, 'other/file.jpg'), jpeg, { contentType: 'image/jpeg' }));
    await assertSucceeds(uploadBytes(photo(alice), jpeg, { contentType: 'image/jpeg' }));
  });
});
