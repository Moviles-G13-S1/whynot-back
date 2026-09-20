# WhyNot — Shared Firebase Backend

## Overview

WhyNot uses Firebase as a shared serverless backend for all mobile clients.

Both the iOS and Android applications connect to the same Firebase project and therefore share:

- Authentication
- User profiles
- Categories
- Wishlists
- Products
- Purchase status

All backend-related changes must remain consistent across both platforms.

---

## Firebase Project

The shared Firebase project is:

```text
Project name: WhyNot
Project ID: whynot-f4ae6
```

All developers must connect their application to this project.

A separate Firebase project should not be created for Android or iOS.

Each platform has its own Firebase application configuration, but all clients use the same Authentication service and Firestore database.

```text
WhyNot Firebase Project
│
├── iOS application
├── Android application
└── Web development preview
        │
        ↓
Shared Firebase Backend
```

---

## Firebase Services

### Firebase Authentication

Firebase Authentication is used for:

- User registration
- Login
- Authenticated sessions
- Password changes
- Reauthentication for sensitive operations

The current authentication method is:

```text
Email / Password
```

Passwords are managed exclusively by Firebase Authentication and are never stored in Cloud Firestore.

---

### Cloud Firestore

Cloud Firestore stores the application's shared data.

The current collections are:

```text
users
categories
wishlists
products
```

Both Android and iOS must use the same collection names, field names, and data types.

---

### Firebase Storage

Firebase Storage is currently not used.

Product and wishlist images are stored as external URLs:

```text
imageUrl: "https://..."
```

The mobile applications display the image using this URL instead of uploading the image to Firebase.

If image uploads are introduced in the future, the backend model and documentation must be updated for both platforms.

---

# Firestore Data Model

## Users

Each Firebase Authentication user has a corresponding Firestore document:

```text
users/{uid}
```

The document ID is the Firebase Authentication UID.

| Field | Type | Description |
|---|---|---|
| `name` | String | User name |
| `email` | String | User email |
| `gender` | String | User gender |
| `age` | Number | User age |
| `preferredCategoryId` | String | User's preferred category |
| `createdAt` | Timestamp | Profile creation time |
| `updatedAt` | Timestamp | Last profile update |

Example:

```text
users/
└── firebaseUserUid/
    ├── name: "User Name"
    ├── email: "user@example.com"
    ├── gender: "Female"
    ├── age: 22
    ├── preferredCategoryId: "fashion"
    ├── createdAt: Timestamp
    └── updatedAt: Timestamp
```

Authentication credentials and passwords are not stored in this document.

---

## Categories

Categories are predefined by WhyNot and stored in:

```text
categories/{categoryId}
```

Current categories:

| ID | Category |
|---|---|
| `fashion` | Fashion |
| `beauty` | Beauty |
| `technology` | Technology |
| `home` | Home |
| `accessories` | Accessories |
| `travel` | Travel |
| `gifts` | Gifts |
| `other` | Other |

Users cannot create arbitrary categories.

These identifiers must remain consistent across Android, iOS, and Firestore.

Category IDs are currently used by:

- `users.preferredCategoryId`
- `wishlists.categoryId`
- `products.categoryId`

---

## Wishlists

Wishlists are stored in:

```text
wishlists/{wishlistId}
```

Each wishlist belongs to one user and one predefined category.

| Field | Type | Description |
|---|---|---|
| `ownerId` | String | Firebase UID of the wishlist owner |
| `categoryId` | String | Associated category ID |
| `imageUrl` | String | External image URL |
| `createdAt` | Timestamp | Wishlist creation time |
| `updatedAt` | Timestamp | Last wishlist update |

Example:

```text
wishlists/
└── wishlistId/
    ├── ownerId: "firebaseUserUid"
    ├── categoryId: "fashion"
    ├── imageUrl: "https://..."
    ├── createdAt: Timestamp
    └── updatedAt: Timestamp
```

The current application behavior prevents a user from creating more than one wishlist for the same category.

For example:

```text
User A
├── Fashion
├── Beauty
└── Fashion again -> not allowed
```

Different users may use the same category:

```text
User A -> Fashion
User B -> Fashion
```

---

## Products

Products are stored in:

```text
products/{productId}
```

| Field | Type | Description |
|---|---|---|
| `ownerId` | String | Firebase UID of the user who saved the product |
| `wishlistId` | String | Wishlist containing the product |
| `categoryId` | String | Category associated with the product |
| `name` | String | Product name |
| `brand` | String | Product brand |
| `price` | Number | Current product price entered manually |
| `imageUrl` | String | External image URL |
| `productUrl` | String | Original product page URL |
| `purchased` | Boolean | Indicates whether the item has been purchased |
| `createdAt` | Timestamp | Product creation time |
| `updatedAt` | Timestamp | Last product update |

Example:

```text
products/
└── productId/
    ├── ownerId: "firebaseUserUid"
    ├── wishlistId: "wishlistId"
    ├── categoryId: "fashion"
    ├── name: "Chaqueta punto manga ancha"
    ├── brand: "ZARA"
    ├── price: 279000
    ├── imageUrl: "https://..."
    ├── productUrl: "https://..."
    ├── purchased: false
    ├── createdAt: Timestamp
    └── updatedAt: Timestamp
```

Products are currently entered manually by the user.

The user provides:

```text
Name
Brand
Price
Picture link
Product link
Wishlist
```

WhyNot currently does not:

- Scrape product websites
- Automatically retrieve prices
- Automatically retrieve product names
- Automatically retrieve product images

---

## Purchased State

Every newly created product must start with:

```text
purchased: false
```

When the user marks the product as purchased:

```text
purchased: true
```

The value may later be changed back to:

```text
purchased: false
```

This value is stored directly in the product document and must use the same field name and Boolean type on both platforms.

The Purchases screen displays products belonging to the authenticated user whose:

```text
purchased == true
```

A separate `purchases` collection is currently not required.

---

## Product Editing

Editing a product updates the existing Firestore document.

The following fields may currently be changed:

```text
name
brand
price
imageUrl
productUrl
wishlistId
categoryId
updatedAt
```

If a product is moved to another wishlist, both:

```text
wishlistId
categoryId
```

must be updated consistently.

---

## Product Deletion

Deleting a product removes its Firestore document:

```text
products/{productId}
```

The client should request confirmation before permanently deleting an item.

---

# Data Relationships

The current model can be represented as:

```text
FIREBASE AUTH USER
        │
        │ uid
        ↓
      USER
        │
        ├──────── preferredCategoryId ──────────┐
        │                                       │
        ↓                                       ↓
    WISHLISTS                              CATEGORIES
        │                                       ↑
        │ wishlistId                            │
        ↓                                       │
     PRODUCTS ───────── categoryId ──────────────┘
        │
        └── purchased: true / false
```

A simplified user-centered representation is:

```text
USER
│
├── preferredCategoryId
│
├── WISHLIST
│   ├── categoryId
│   └── PRODUCTS
│       ├── categoryId
│       ├── name
│       ├── brand
│       ├── price
│       ├── imageUrl
│       ├── productUrl
│       └── purchased
│
└── additional wishlists
```

---

# Shared Backend Contract

Because Android and iOS use the same backend, both applications must use the same Firestore schema.

For example, one platform must not store:

```text
isPurchased
```

while the other stores:

```text
purchased
```

The agreed field name is:

```text
purchased
```

The same rule applies to all fields.

Current shared schema:

```text
users
├── name
├── email
├── gender
├── age
├── preferredCategoryId
├── createdAt
└── updatedAt

wishlists
├── ownerId
├── categoryId
├── imageUrl
├── createdAt
└── updatedAt

products
├── ownerId
├── wishlistId
├── categoryId
├── name
├── brand
├── price
├── imageUrl
├── productUrl
├── purchased
├── createdAt
└── updatedAt
```

Any schema change must be coordinated between the Android and iOS teams before implementation.

---

# Platform Configuration

Each client must register its own application inside the same Firebase project.

```text
WhyNot Firebase Project
│
├── iOS configuration
├── Android configuration
└── Web configuration
```

Platform configuration is separate, but all applications connect to the same backend.

The iOS and Web applications are already configured.

Android must also be configured using:

```text
Project ID: whynot-f4ae6
```

A separate Firebase project should not be created.

---

## FlutterFire Configuration

For Flutter applications, Firebase configuration can be generated with:

```bash
flutterfire configure --project=whynot-f4ae6
```

Select the required platform when prompted.

This command generates or updates:

```text
lib/firebase_options.dart
```

Firebase is initialized with:

```dart
await Firebase.initializeApp(
  options: DefaultFirebaseOptions.currentPlatform,
);
```

---

## Firebase Dependencies

The current Flutter Firebase dependencies are:

```yaml
firebase_core
firebase_auth
cloud_firestore
```

Install project dependencies with:

```bash
flutter pub get
```

---

# Real-Time Data

Firestore streams are used in several parts of the application.

This allows the interface to react automatically when backend data changes.

For example:

```text
Product
purchased: false
      │
      │ User marks item as purchased
      ↓
Firestore
purchased: true
      │
      ↓
Purchases screen updates
```

Real-time updates are currently used for:

- Wishlist products
- Wishlist item counts
- Product details
- Product edits
- Product deletion
- Purchase status
- User profile information

---

# Current Backend-Supported Features

The shared Firebase backend currently supports:

```text
AUTHENTICATION
├── Create account
├── Login
├── Authenticated sessions
└── Change password

USERS
├── Create profile
├── Read profile
└── Update profile

WISHLISTS
├── Create wishlist
├── Read user wishlists
├── Associate wishlist with category
└── Count products

PRODUCTS
├── Create product
├── Read product
├── Edit product
├── Delete product
├── Move product between wishlists
└── Mark/unmark as purchased

PURCHASES
└── Products where purchased == true
```

---

# Client-Side Filters

Filtering and ordering are currently handled by the mobile clients after retrieving the relevant products.

Wishlist Detail supports:

```text
Low to high
High to low
Show only unpurchased
```

Purchases supports:

```text
Low to high
High to low
```

The `price` field must remain numeric so that ordering and calculations can be performed correctly.

---

# Planned Features

The following backend-related functionality is not currently implemented:

- Nearby store recommendations
- Location-based recommendations
- Personalized product recommendations
- Recommendation logic based on demographics
- Recommendation logic based on saved products
- Recommendation logic based on preferred categories
- Store management
- Automatic product information extraction
- Firebase Storage image uploads

These features should not be assumed to exist in the current backend implementation.

---

## Stores — Planned Model

A `stores` collection may be introduced later to support location-based functionality.

A possible future structure is:

```text
stores/{storeId}
```

Possible fields:

| Field | Description |
|---|---|
| `name` | Store name |
| `location` | Geographic location |
| `categoryIds` | Categories associated with the store |
| `websiteUrl` | Store website |

This collection is planned and is not part of the currently implemented backend.

---

# Future Recommendation Model

The current database structure can later support recommendation logic using information such as:

```text
USER
├── preferred category
├── age
├── gender
├── saved products
├── purchased products
└── product brands

                ↓

      RECOMMENDATION LOGIC

                ↓

        PERSONALIZED PRODUCTS
```

A future location-based flow could use:

```text
USER LOCATION
      │
      ↓
    STORES
      │
      ↓
NEARBY STORE RECOMMENDATIONS
```

Recommendation functionality must use the same shared backend for both Android and iOS.

---

# Development Guidelines

When modifying the shared backend:

1. Do not rename Firestore fields independently on one platform.
2. Do not create platform-specific versions of the same collection.
3. Coordinate schema changes between the Android and iOS teams.
4. Continue using the shared Firebase project.
5. Use Firebase Authentication UIDs to associate users with their data.
6. Never store passwords in Firestore.
7. Keep `price` stored as a numeric value.
8. Keep `purchased` stored as a Boolean.
9. Keep category IDs consistent with the predefined categories.
10. Continue using external image URLs unless the team explicitly decides to introduce Firebase Storage.
11. Update this README whenever the shared backend schema changes.