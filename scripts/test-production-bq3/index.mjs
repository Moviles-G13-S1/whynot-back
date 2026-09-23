import { initializeApp } from 'firebase/app';

import {
  getAuth,
  signInWithEmailAndPassword,
} from 'firebase/auth';

import {
  getFirestore,
  collection,
  query,
  where,
  getDocs,
} from 'firebase/firestore';


const apiKey = process.env.WHYNOT_API_KEY;
const email = process.env.WHYNOT_EMAIL;
const password = process.env.WHYNOT_PASSWORD;


if (!apiKey || !email || !password) {
  throw new Error(
    'Missing WHYNOT_API_KEY, WHYNOT_EMAIL or WHYNOT_PASSWORD.'
  );
}


const app = initializeApp({
  apiKey,
  authDomain: 'whynot-f4ae6.firebaseapp.com',
  projectId: 'whynot-f4ae6',
});


const auth = getAuth(app);
const firestore = getFirestore(app);


async function callFirebaseFunction(
  functionName,
  idToken,
  data = {}
) {

  const url =
    `https://us-central1-whynot-f4ae6.cloudfunctions.net/${functionName}`;

  const response = await fetch(
    url,
    {
      method: 'POST',

      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${idToken}`,
      },

      body: JSON.stringify({
        data,
      }),
    }
  );


  const body = await response.json();


  if (!response.ok || body.error) {

    console.error(
      `\nFunction ${functionName} failed:`,
      body
    );

    throw new Error(
      body?.error?.message ??
      `HTTP ${response.status}`
    );
  }


  return body.result;
}


async function main() {

  console.log('\n1. Signing in...');


  const credential =
    await signInWithEmailAndPassword(
      auth,
      email,
      password
    );


  console.log(
    'Logged in as:',
    credential.user.uid
  );


  console.log(
    '\n2. Getting Firebase ID token...'
  );


  const idToken =
    await credential.user.getIdToken(
      true
    );


  console.log(
    'Authentication token obtained.'
  );


  console.log(
    '\n3. Requesting recommendation...'
  );


  const recommendationResult =
    await callFirebaseFunction(
      'get_recommendation',
      idToken
    );


  const recommendation =
    recommendationResult?.recommendation;


  if (!recommendation) {
    throw new Error(
      'Backend returned no recommendation.'
    );
  }


  console.log(
    'Recommendation:',
    recommendation
  );


  console.log(
    '\n4. Looking for compatible wishlist...'
  );


  const wishlistQuery =
    query(
      collection(
        firestore,
        'wishlists'
      ),

      where(
        'ownerId',
        '==',
        credential.user.uid
      )
    );


  const wishlistSnapshot =
    await getDocs(
      wishlistQuery
    );


  const wishlist =
    wishlistSnapshot.docs
      .map(document => ({
        id: document.id,
        ...document.data(),
      }))
      .find(
        item =>
          item.categoryId ===
          recommendation.categoryId
      );


  if (!wishlist) {
    throw new Error(
      `No wishlist found for category ${recommendation.categoryId}.`
    );
  }


  console.log(
    'Wishlist:',
    wishlist.id
  );


  console.log(
    '\n5. Saving recommendation...'
  );


  const saveResult =
    await callFirebaseFunction(
      'save_recommended_product',
      idToken,
      {
        recommendationEventId:
          recommendation.recommendationEventId,

        wishlistId:
          wishlist.id,
      }
    );


  console.log(
    '\nSAVE RESULT:',
    saveResult
  );


  if (!saveResult?.saved) {
    throw new Error(
      'Recommendation was not saved.'
    );
  }


  console.log(
    '\n✅ PRODUCTION BQ3 FLOW WORKED'
  );


  console.log(
    '\nCheck Firestore now:'
  );


  console.log(
    'adminMetrics/recommendedProductSaves'
  );
}


main().catch(error => {

  console.error(
    '\n❌ TEST FAILED'
  );

  console.error(error);

  process.exitCode = 1;
});