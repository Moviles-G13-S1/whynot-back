import { readFileSync } from 'node:fs';

import {
  assertFails,
  assertSucceeds,
  initializeTestEnvironment,
} from '@firebase/rules-unit-testing';
import {
  collection,
  deleteDoc,
  doc,
  getDoc,
  getDocs,
  query,
  serverTimestamp,
  setDoc,
  Timestamp,
  updateDoc,
  where,
} from 'firebase/firestore';

const projectId = 'demo-whynot';
const aliceUid = 'alice-uid';
const bobUid = 'bob-uid';
const aliceEmail = 'alice@example.com';
const bobEmail = 'bob@example.com';

let testEnvironment;

function firestoreFor(uid, email, extraClaims = {}) {
  return testEnvironment
    .authenticatedContext(uid, { email, ...extraClaims })
    .firestore();
}

function unauthenticatedFirestore() {
  return testEnvironment.unauthenticatedContext().firestore();
}

function validUser(overrides = {}) {
  return {
    name: 'Alice',
    email: aliceEmail,
    gender: 'Female',
    age: 22,
    preferredCategoryId: 'fashion',
    cityId: 'bogota',
    createdAt: serverTimestamp(),
    updatedAt: serverTimestamp(),
    ...overrides,
  };
}

function validWishlist(overrides = {}) {
  return {
    ownerId: aliceUid,
    categoryId: 'fashion',
    imageUrl: '',
    createdAt: serverTimestamp(),
    updatedAt: serverTimestamp(),
    ...overrides,
  };
}

function validProduct(overrides = {}) {
  return {
    ownerId: aliceUid,
    wishlistId: 'alice-fashion',
    categoryId: 'fashion',
    name: 'Jacket',
    brand: 'Example',
    price: 279000,
    imageUrl: 'https://example.com/jacket.jpg',
    productUrl: 'https://example.com/jacket',
    purchased: false,
    purchasedAt: null,
    createdAt: serverTimestamp(),
    updatedAt: serverTimestamp(),
    ...overrides,
  };
}

async function seedFixtures({ includeUsers = false, includeProducts = false } = {}) {
  await testEnvironment.withSecurityRulesDisabled(async (context) => {
    const firestore = context.firestore();
    const timestamp = Timestamp.fromMillis(1_700_000_000_000);

    await Promise.all([
      setDoc(doc(firestore, 'categories/fashion'), { name: 'Fashion' }),
      setDoc(doc(firestore, 'categories/beauty'), { name: 'Beauty' }),
      setDoc(doc(firestore, 'cities/bogota'), { name: 'Bogotá' }),
      setDoc(doc(firestore, 'cities/medellin'), { name: 'Medellín' }),
      setDoc(doc(firestore, 'cities/other'), { name: 'Other' }),
      setDoc(doc(firestore, 'wishlists/alice-fashion'), {
        ownerId: aliceUid,
        categoryId: 'fashion',
        imageUrl: '',
        createdAt: timestamp,
        updatedAt: timestamp,
      }),
      setDoc(doc(firestore, 'wishlists/alice-beauty'), {
        ownerId: aliceUid,
        categoryId: 'beauty',
        imageUrl: '',
        createdAt: timestamp,
        updatedAt: timestamp,
      }),
      setDoc(doc(firestore, 'wishlists/bob-fashion'), {
        ownerId: bobUid,
        categoryId: 'fashion',
        imageUrl: '',
        createdAt: timestamp,
        updatedAt: timestamp,
      }),
    ]);

    if (includeUsers) {
      await Promise.all([
        setDoc(doc(firestore, `users/${aliceUid}`), {
          name: 'Alice',
          email: aliceEmail,
          gender: 'Female',
          age: 22,
          preferredCategoryId: 'fashion',
          createdAt: timestamp,
          updatedAt: timestamp,
        }),
        setDoc(doc(firestore, `users/${bobUid}`), {
          name: 'Bob',
          email: bobEmail,
          gender: 'Male',
          age: 24,
          preferredCategoryId: 'fashion',
          createdAt: timestamp,
          updatedAt: timestamp,
        }),
      ]);
    }

    if (includeProducts) {
      await Promise.all([
        setDoc(doc(firestore, 'products/alice-product'), {
          ownerId: aliceUid,
          wishlistId: 'alice-fashion',
          categoryId: 'fashion',
          name: 'Jacket',
          brand: 'Example',
          price: 279000,
          imageUrl: '',
          productUrl: '',
          purchased: false,
          purchasedAt: null,
          createdAt: timestamp,
          updatedAt: timestamp,
        }),
        setDoc(doc(firestore, 'products/bob-product'), {
          ownerId: bobUid,
          wishlistId: 'bob-fashion',
          categoryId: 'fashion',
          name: 'Shoes',
          brand: 'Example',
          price: 100,
          imageUrl: '',
          productUrl: '',
          purchased: false,
          purchasedAt: null,
          createdAt: timestamp,
          updatedAt: timestamp,
        }),
      ]);
    }

    await Promise.all([
      setDoc(doc(firestore, 'adminMetrics/overview'), {
        totalUsers: 2,
        totalProducts: includeProducts ? 2 : 0,
      }),
      setDoc(doc(firestore, 'adminMetrics/purchases/2026/09'), {
        total: 1,
      }),
      setDoc(doc(firestore, 'productEvents/event-1'), {
        eventType: 'saved',
      }),
      setDoc(doc(firestore, 'processedEvents/event-1'), {
        processedAt: timestamp,
      }),
    ]);
  });
}

before(async () => {
  testEnvironment = await initializeTestEnvironment({
    projectId,
    firestore: {
      rules: readFileSync('firestore.rules', 'utf8'),
    },
  });
});
beforeEach(async () => {
  await testEnvironment.clearFirestore();
  await seedFixtures();
});

after(async () => {
  await testEnvironment.cleanup();
});

describe('default and category access', () => {
  it('denies unauthenticated reads and writes', async () => {
    const firestore = unauthenticatedFirestore();

    await assertFails(getDoc(doc(firestore, 'categories/fashion')));
    await assertFails(getDoc(doc(firestore, 'adminMetrics/overview')));
    await assertFails(setDoc(doc(firestore, 'products/product-1'), validProduct()));
  });

  it('allows authenticated category reads and denies category writes', async () => {
    const alice = firestoreFor(aliceUid, aliceEmail);
    const forgedAdmin = firestoreFor(aliceUid, aliceEmail, { admin: true });

    await assertSucceeds(getDoc(doc(alice, 'categories/fashion')));
    await assertSucceeds(getDocs(collection(alice, 'categories')));
    await assertFails(setDoc(doc(alice, 'categories/new'), { name: 'New' }));
    await assertFails(updateDoc(doc(forgedAdmin, 'categories/fashion'), { name: 'Changed' }));
  });

  it('allows anyone to read cities but not edit them', async () => {
    const visitor = unauthenticatedFirestore();
    const alice = firestoreFor(aliceUid, aliceEmail);
    await assertSucceeds(getDocs(collection(visitor, 'cities')));
    await assertSucceeds(getDoc(doc(visitor, 'cities/bogota')));
    await assertFails(setDoc(doc(visitor, 'cities/new'), { name: 'New' }));
    await assertSucceeds(getDocs(collection(alice, 'cities')));
    await assertSucceeds(getDoc(doc(alice, 'cities/bogota')));
    await assertFails(setDoc(doc(alice, 'cities/new'), { name: 'New' }));
  });

  it('allows only administrators to read aggregate metrics', async () => {
    const regularUser = firestoreFor(aliceUid, aliceEmail);
    const admin = firestoreFor(aliceUid, aliceEmail, { admin: true });

    await assertFails(getDoc(doc(regularUser, 'adminMetrics/overview')));
    await assertFails(getDocs(collection(regularUser, 'adminMetrics')));
    await assertSucceeds(getDoc(doc(admin, 'adminMetrics/overview')));
    await assertSucceeds(getDocs(collection(admin, 'adminMetrics')));
    await assertSucceeds(
      getDoc(doc(admin, 'adminMetrics/purchases/2026/09')),
    );
  });

  it('denies metric writes and event access even to administrators', async () => {
    const admin = firestoreFor(aliceUid, aliceEmail, { admin: true });

    await assertFails(setDoc(doc(admin, 'adminMetrics/new'), { value: true }));
    await assertFails(updateDoc(doc(admin, 'adminMetrics/overview'), {
      totalUsers: 99,
    }));
    await assertFails(deleteDoc(doc(admin, 'adminMetrics/overview')));

    for (const path of [
      'productEvents/event-1',
      'processedEvents/event-1',
      'unknown/document-1',
    ]) {
      await assertFails(getDoc(doc(admin, path)));
      await assertFails(setDoc(doc(admin, path), { value: true }));
    }
  });
});

describe('users', () => {
  it('allows a user to create and read a valid own profile', async () => {
    const alice = firestoreFor(aliceUid, aliceEmail);

    await assertSucceeds(setDoc(doc(alice, `users/${aliceUid}`), validUser()));
    await assertSucceeds(getDoc(doc(alice, `users/${aliceUid}`)));
  });

  it('denies access to another user profile and collection listing', async () => {
    await seedFixtures({ includeUsers: true });
    const bob = firestoreFor(bobUid, bobEmail);

    await assertFails(getDoc(doc(bob, `users/${aliceUid}`)));
    await assertFails(updateDoc(doc(bob, `users/${aliceUid}`), {
      name: 'Changed',
      updatedAt: serverTimestamp(),
    }));
    await assertFails(getDocs(collection(bob, 'users')));
  });

  it('allows an administrator to list profiles for demographics', async () => {
    await seedFixtures({ includeUsers: true });
    const admin = firestoreFor(aliceUid, aliceEmail, { admin: true });
    await assertSucceeds(getDocs(collection(admin, 'users')));
  });

  it('rejects invalid, missing, extra, and mismatched profile data', async () => {
    const alice = firestoreFor(aliceUid, aliceEmail);
    const ownProfile = doc(alice, `users/${aliceUid}`);

    await assertFails(setDoc(ownProfile, validUser({ age: 12 })));
    await assertFails(setDoc(ownProfile, validUser({ age: '22' })));
    await assertFails(setDoc(ownProfile, validUser({ gender: 'Unknown' })));
    await assertFails(setDoc(ownProfile, validUser({ preferredCategoryId: 'missing' })));
    await assertFails(setDoc(ownProfile, validUser({ cityId: 'missing' })));
    await assertFails(setDoc(ownProfile, validUser({ cityId: '' })));
    await assertFails(setDoc(ownProfile, validUser({ email: 'other@example.com' })));
    await assertFails(setDoc(ownProfile, validUser({ role: 'admin' })));

    const missingName = validUser();
    delete missingName.name;
    await assertFails(setDoc(ownProfile, missingName));

    const missingCity = validUser();
    delete missingCity.cityId;
    await assertFails(setDoc(ownProfile, missingCity));
  });

  it('allows documented edits and keeps email and createdAt immutable', async () => {
    await seedFixtures({ includeUsers: true });
    const alice = firestoreFor(aliceUid, aliceEmail);
    const ownProfile = doc(alice, `users/${aliceUid}`);

    // Older profiles without cityId remain editable.
    await assertSucceeds(updateDoc(ownProfile, {
      name: 'Alice Before City',
      updatedAt: serverTimestamp(),
    }));

    await assertSucceeds(updateDoc(ownProfile, {
      name: 'Alice Updated',
      gender: 'Other',
      age: 23,
      preferredCategoryId: 'beauty',
      cityId: 'medellin',
      updatedAt: serverTimestamp(),
    }));
    await assertFails(updateDoc(ownProfile, {
      cityId: 'missing',
      updatedAt: serverTimestamp(),
    }));
    await assertFails(updateDoc(ownProfile, {
      email: 'changed@example.com',
      updatedAt: serverTimestamp(),
    }));
    await assertFails(updateDoc(ownProfile, {
      createdAt: serverTimestamp(),
      updatedAt: serverTimestamp(),
    }));
    await assertFails(deleteDoc(ownProfile));
  });
});

describe('wishlists', () => {
  it('allows valid creation and owner-scoped reads', async () => {
    const alice = firestoreFor(aliceUid, aliceEmail);

    await assertSucceeds(
      setDoc(doc(alice, 'wishlists/new-wishlist'), validWishlist()),
    );
    await assertSucceeds(getDoc(doc(alice, 'wishlists/alice-fashion')));
    await assertSucceeds(
      getDocs(
        query(
          collection(alice, 'wishlists'),
          where('ownerId', '==', aliceUid),
        ),
      ),
    );
  });

  it('rejects foreign ownership, invalid categories, malformed fields, and extra fields', async () => {
    const alice = firestoreFor(aliceUid, aliceEmail);
    const target = doc(alice, 'wishlists/new-wishlist');

    await assertFails(setDoc(target, validWishlist({ ownerId: bobUid })));
    await assertFails(setDoc(target, validWishlist({ categoryId: 'missing' })));
    await assertFails(setDoc(target, validWishlist({ imageUrl: 42 })));
    await assertFails(setDoc(target, validWishlist({ unexpected: true })));
  });

  it('denies foreign reads, updates, and deletes', async () => {
    const alice = firestoreFor(aliceUid, aliceEmail);
    const bob = firestoreFor(bobUid, bobEmail);

    await assertFails(getDoc(doc(bob, 'wishlists/alice-fashion')));
    await assertFails(
      getDocs(
        query(
          collection(bob, 'wishlists'),
          where('ownerId', '==', aliceUid),
        ),
      ),
    );
    await assertFails(updateDoc(doc(alice, 'wishlists/alice-fashion'), {
      imageUrl: 'https://example.com/new.jpg',
      updatedAt: serverTimestamp(),
    }));
    await assertFails(deleteDoc(doc(alice, 'wishlists/alice-fashion')));
  });
});

describe('products', () => {
  beforeEach(async () => {
    await seedFixtures({ includeProducts: true });
  });

  it('allows a valid product in an owned wishlist', async () => {
    const alice = firestoreFor(aliceUid, aliceEmail);

    await assertSucceeds(
      setDoc(doc(alice, 'products/new-product'), validProduct()),
    );
  });

  it('rejects invalid relationships and invalid product fields', async () => {
    const alice = firestoreFor(aliceUid, aliceEmail);
    const target = doc(alice, 'products/new-product');

    await assertFails(setDoc(target, validProduct({ wishlistId: 'bob-fashion' })));
    await assertFails(setDoc(target, validProduct({ wishlistId: 'missing' })));
    await assertFails(setDoc(target, validProduct({ categoryId: 'beauty' })));
    await assertFails(setDoc(target, validProduct({ purchased: true })));
    await assertFails(setDoc(target, validProduct({ price: -1 })));
    await assertFails(setDoc(target, validProduct({ price: '100' })));
    await assertFails(setDoc(target, validProduct({ name: '' })));
    await assertFails(setDoc(target, validProduct({ saveMethod: 'manual' })));

    const missingBrand = validProduct();
    delete missingBrand.brand;
    await assertFails(setDoc(target, missingBrand));

    const missingPurchasedAt = validProduct();
    delete missingPurchasedAt.purchasedAt;
    await assertFails(setDoc(target, missingPurchasedAt));
  });

  it('supports current owner and wishlist query shapes', async () => {
    const alice = firestoreFor(aliceUid, aliceEmail);

    await assertSucceeds(getDoc(doc(alice, 'products/alice-product')));
    await assertSucceeds(
      getDocs(
        query(
          collection(alice, 'products'),
          where('ownerId', '==', aliceUid),
        ),
      ),
    );
    await assertSucceeds(
      getDocs(
        query(
          collection(alice, 'products'),
          where('wishlistId', '==', 'alice-fashion'),
        ),
      ),
    );
  });

  it('allows an admin to count products but not a regular user', async () => {
    const admin = firestoreFor(aliceUid, aliceEmail, { admin: true });
    const regularUser = firestoreFor(aliceUid, aliceEmail);

    await assertSucceeds(getDocs(collection(admin, 'products')));
    await assertFails(getDocs(collection(regularUser, 'products')));
  });

  it('denies another user equivalent product reads', async () => {
    const bob = firestoreFor(bobUid, bobEmail);

    await assertFails(getDoc(doc(bob, 'products/alice-product')));
    await assertFails(
      getDocs(
        query(
          collection(bob, 'products'),
          where('ownerId', '==', aliceUid),
        ),
      ),
    );
    await assertFails(
      getDocs(
        query(
          collection(bob, 'products'),
          where('wishlistId', '==', 'alice-fashion'),
        ),
      ),
    );
  });

  it('allows documented edits and a one-way purchase transition', async () => {
    const alice = firestoreFor(aliceUid, aliceEmail);
    const product = doc(alice, 'products/alice-product');

    await assertSucceeds(updateDoc(product, {
      name: 'Updated Jacket',
      brand: 'Updated Brand',
      price: 300,
      imageUrl: 'https://example.com/new.jpg',
      productUrl: 'https://example.com/new',
      updatedAt: serverTimestamp(),
    }));
    await assertSucceeds(updateDoc(product, {
      purchased: true,
      purchasedAt: serverTimestamp(),
      updatedAt: serverTimestamp(),
    }));

    await assertFails(updateDoc(product, {
      purchased: false,
      purchasedAt: null,
      updatedAt: serverTimestamp(),
    }));

    await assertFails(updateDoc(product, {
      purchasedAt: serverTimestamp(),
      updatedAt: serverTimestamp(),
    }));
  });

  it('protects immutable fields and validates moves between wishlists', async () => {
    const alice = firestoreFor(aliceUid, aliceEmail);
    const product = doc(alice, 'products/alice-product');

    await assertFails(updateDoc(product, {
      ownerId: bobUid,
      updatedAt: serverTimestamp(),
    }));
    await assertFails(updateDoc(product, {
      createdAt: serverTimestamp(),
      updatedAt: serverTimestamp(),
    }));
    await assertFails(updateDoc(product, {
      wishlistId: 'alice-beauty',
      updatedAt: serverTimestamp(),
    }));
    await assertFails(updateDoc(product, {
      wishlistId: 'bob-fashion',
      categoryId: 'fashion',
      updatedAt: serverTimestamp(),
    }));
    await assertSucceeds(updateDoc(product, {
      wishlistId: 'alice-beauty',
      categoryId: 'beauty',
      updatedAt: serverTimestamp(),
    }));
  });

  it('allows only the owner to delete a product', async () => {
    const alice = firestoreFor(aliceUid, aliceEmail);
    const bob = firestoreFor(bobUid, bobEmail);

    await assertFails(deleteDoc(doc(bob, 'products/alice-product')));
    await assertSucceeds(deleteDoc(doc(alice, 'products/alice-product')));
  });
});
