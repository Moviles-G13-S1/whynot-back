import test from 'node:test';
import assert from 'node:assert/strict';

import { buildDemoDataset, DEMO_PREFIX, describeDemoDataset } from '../scripts/seed-analytics-demo/fixture.mjs';

test('demo records answer BQ1–BQ6 with consistent references', () => {
  const dataset = buildDemoDataset(new Date('2026-10-21T12:00:00Z'));
  const summary = describeDemoDataset(dataset);
  assert.deepEqual(summary, {
    users: 24,
    zeroProductUsers: 5,
    repeatSavers: 12,
    products: 77,
    purchasedProducts: 25,
    recommendationEvents: 72,
    recommendedSaves: 28,
    recommendationSaveRatePercent: 38.9,
    distinctRecommendationSavers: 14,
    productSaveEvents: 48,
  });

  const users = new Map(dataset.users.map(record => [record.id, record.data]));
  const wishlists = new Map(dataset.wishlists.map(record => [record.id, record.data]));
  const products = new Map(dataset.products.map(record => [record.id, record.data]));
  for (const [name, records] of Object.entries(dataset)) {
    assert.equal(new Set(records.map(record => record.id)).size, records.length, `${name} IDs must be unique`);
    assert.ok(records.every(record => record.id.startsWith(DEMO_PREFIX)));
  }
  for (const product of products.values()) {
    assert.ok(users.has(product.ownerId));
    assert.equal(wishlists.get(product.wishlistId)?.ownerId, product.ownerId);
    assert.equal(wishlists.get(product.wishlistId)?.categoryId, product.categoryId);
    assert.equal(product.purchased, product.purchasedAt instanceof Date);
  }
  assert.equal(new Set(dataset.products.filter(product => product.data.purchased).map(product =>
    product.data.purchasedAt.toISOString().slice(0, 7))).size, 6);
  for (const event of dataset.productEvents) {
    assert.ok(users.has(event.data.userId));
    assert.ok(products.has(event.data.sourceProductId));
    if (event.data.savedAt) {
      assert.equal(products.get(event.data.savedProductId)?.ownerId, event.data.userId);
      assert.ok(event.data.createdAt <= event.data.savedAt);
    } else {
      assert.equal(event.data.savedProductId, null);
    }
  }
  assert.deepEqual(buildDemoDataset(new Date('2026-10-21T12:00:00Z')), dataset);
});
