// A deterministic, visibly synthetic data set for the six admin questions.
// The dates move with the chosen as-of month so recent-month charts stay useful.
export const DEMO_PREFIX = 'demo-analytics-';

const categories = ['fashion', 'beauty', 'technology', 'home', 'accessories', 'travel', 'gifts', 'other'];
const cities = ['bogota', 'medellin', 'cali', 'barranquilla', 'bucaramanga'];
const genders = ['Female', 'Male', 'Other'];
const ages = [17, 19, 22, 25, 28, 31, 35, 39, 43, 48, 54, 61];
const productsPerUser = [
  ...Array(7).fill(1),
  ...Array(6).fill(3),
  ...Array(4).fill(7),
  ...Array(2).fill(12),
  ...Array(5).fill(0),
];
const shownByMonth = [8, 10, 12, 13, 14, 15];
const savedByMonth = [2, 4, 3, 6, 5, 8];

function pad(value) {
  return String(value).padStart(2, '0');
}

export function buildDemoDataset(asOf = new Date()) {
  if (!(asOf instanceof Date) || Number.isNaN(asOf.valueOf())) throw new Error('Invalid as-of date.');
  const year = asOf.getUTCFullYear();
  const month = asOf.getUTCMonth();
  const currentDay = asOf.getUTCDate();
  const inMonth = (offset, day, hour = 12) => {
    const actualDay = offset === 0 ? Math.min(day, currentDay) : day;
    return new Date(Date.UTC(year, month - offset, actualDay, hour));
  };
  const baseDate = inMonth(8, 12);
  const users = [];
  const wishlists = [];
  const products = [];
  const wishlistIds = new Set();

  productsPerUser.forEach((count, userIndex) => {
    const ordinal = pad(userIndex + 1);
    const uid = `${DEMO_PREFIX}user-${ordinal}`;
    users.push({
      id: uid,
      data: {
        name: `Demo User ${ordinal}`,
        email: `demo.user${ordinal}@whynot.example`,
        gender: genders[userIndex % genders.length],
        age: ages[userIndex % ages.length],
        preferredCategoryId: categories[userIndex % categories.length],
        cityId: cities[userIndex % cities.length],
        createdAt: baseDate,
        updatedAt: baseDate,
      },
    });
    for (let slot = 0; slot < count; slot += 1) {
      const categoryId = categories[(userIndex + slot) % categories.length];
      const wishlistId = `${DEMO_PREFIX}wishlist-${ordinal}-${categoryId}`;
      if (!wishlistIds.has(wishlistId)) {
        wishlistIds.add(wishlistId);
        wishlists.push({ id: wishlistId, data: { ownerId: uid, categoryId, imageUrl: '', createdAt: baseDate, updatedAt: baseDate } });
      }
      const number = products.length + 1;
      const purchased = number % 3 === 0;
      const purchasedAt = purchased ? inMonth((number / 3) % 6, 15) : null;
      const product = {
        id: `${DEMO_PREFIX}product-${String(number).padStart(3, '0')}`,
        data: {
          ownerId: uid,
          wishlistId,
          categoryId,
          name: `Demo ${categoryId} item ${number}`,
          brand: `Demo Brand ${number % 5 + 1}`,
          price: 25000 + number * 3500,
          imageUrl: '',
          productUrl: '',
          purchased,
          purchasedAt,
          createdAt: baseDate,
          updatedAt: purchasedAt ?? baseDate,
        },
      };
      products.push(product);
    }
  });

  const productEvents = [];
  const savedProducts = products.slice(0, savedByMonth.reduce((sum, count) => sum + count, 0));
  let savedIndex = 0;
  for (let monthIndex = 0; monthIndex < 6; monthIndex += 1) {
    const offset = 5 - monthIndex;
    for (let eventIndex = 0; eventIndex < shownByMonth[monthIndex]; eventIndex += 1) {
      const savedProduct = eventIndex < savedByMonth[monthIndex] ? savedProducts[savedIndex++] : null;
      const user = savedProduct
        ? savedProduct.data.ownerId
        : users[(monthIndex * 7 + eventIndex) % users.length].id;
      const source = products.find(product => product.data.ownerId !== user && product.data.categoryId === (savedProduct?.data.categoryId ?? categories[eventIndex % categories.length])) ?? products[0];
      const number = productEvents.length + 1;
      productEvents.push({
        id: `${DEMO_PREFIX}recommendation-${String(number).padStart(3, '0')}`,
        data: {
          eventType: 'recommendation_shown',
          userId: user,
          sourceProductId: source.id,
          createdAt: inMonth(offset, 4 + eventIndex, 10),
          savedAt: savedProduct ? inMonth(offset, 4 + eventIndex, 12) : null,
          savedProductId: savedProduct?.id ?? null,
        },
      });
    }
  }

  const productSaveEvents = Array.from({ length: 48 }, (_, index) => ({
    id: `${DEMO_PREFIX}save-attempt-${String(index + 1).padStart(3, '0')}`,
    data: {
      userId: users[index % users.length].id,
      platform: index % 2 ? 'android' : 'ios',
      outcome: index % 5 ? 'success' : 'failure',
      reason: index % 5 ? null : 'missing_name',
      createdAt: inMonth(index % 6, 8 + index % 8),
    },
  }));

  return { users, wishlists, products, productEvents, productSaveEvents };
}

export function describeDemoDataset(dataset) {
  const activeOwners = new Set(dataset.products.map(product => product.data.ownerId));
  const saved = dataset.productEvents.filter(event => event.data.savedAt && event.data.savedProductId);
  return {
    users: dataset.users.length,
    zeroProductUsers: dataset.users.length - activeOwners.size,
    repeatSavers: [...activeOwners].filter(uid => dataset.products.filter(product => product.data.ownerId === uid).length >= 2).length,
    products: dataset.products.length,
    purchasedProducts: dataset.products.filter(product => product.data.purchased).length,
    recommendationEvents: dataset.productEvents.length,
    recommendedSaves: saved.length,
    recommendationSaveRatePercent: Math.round(saved.length * 1000 / dataset.productEvents.length) / 10,
    distinctRecommendationSavers: new Set(saved.map(event => event.data.userId)).size,
    productSaveEvents: dataset.productSaveEvents.length,
  };
}
