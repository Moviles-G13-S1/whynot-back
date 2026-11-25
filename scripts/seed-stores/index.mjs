#!/usr/bin/env node

import { applicationDefault, initializeApp } from 'firebase-admin/app';
import { getFirestore } from 'firebase-admin/firestore';


const stores = new Map([
  // -------------------------------------------------------------------------
  // Fashion
  // -------------------------------------------------------------------------

  [
    'zara-andino',
    {
      name: 'ZARA - Andino',
      address: 'Calle 82 #12-22, Bogotá',
      latitude: 4.66691,
      longitude: -74.05312,
      categoryIds: [
        'fashion',
      ],
      websiteUrl: 'https://www.zara.com/co/',
      imageUrl: '',
    },
  ],

  [
    'hm-mallplaza-nqs',
    {
      name: 'H&M - Mallplaza NQS',
      address: 'Avenida Carrera 30 #19, Bogotá',
      latitude: 4.61815,
      longitude: -74.08599,
      categoryIds: [
        'fashion',
      ],
      websiteUrl: 'https://www2.hm.com/es_co/index.html',
      imageUrl: '',
    },
  ],

  [
    'arturo-calle-titan-plaza',
    {
      name: 'Arturo Calle - Titán Plaza',
      address: 'Avenida Boyacá #80-94, Bogotá',
      latitude: 4.69450,
      longitude: -74.08660,
      categoryIds: [
        'fashion',
      ],
      websiteUrl: 'https://www.arturocalle.com/',
      imageUrl: '',
    },
  ],

  [
    'studio-f-santafe',
    {
      name: 'Studio F - Santafé',
      address: 'Calle 185 #45-03, Bogotá',
      latitude: 4.76260,
      longitude: -74.04590,
      categoryIds: [
        'fashion',
      ],
      websiteUrl: 'https://www.studiof.com.co/',
      imageUrl: '',
    },
  ],

  [
    'bershka-gran-estacion',
    {
      name: 'Bershka - Gran Estación',
      address: 'Avenida Calle 26 #62-47, Bogotá',
      latitude: 4.64760,
      longitude: -74.10180,
      categoryIds: [
        'fashion',
      ],
      websiteUrl: 'https://www.bershka.com/co/',
      imageUrl: '',
    },
  ],

  [
    'adidas-centro-mayor',
    {
      name: 'adidas - Centro Mayor',
      address: 'Calle 38A Sur #34D-50, Bogotá',
      latitude: 4.59270,
      longitude: -74.12440,
      categoryIds: [
        'fashion',
      ],
      websiteUrl: 'https://www.adidas.co/',
      imageUrl: '',
    },
  ],

  [
    'golden-goose-andino',
    {
      name: 'Golden Goose - Andino',
      address: 'Carrera 11 #82-71, Bogotá',
      latitude: 4.66691,
      longitude: -74.05312,
      categoryIds: [
        'fashion',
      ],
      websiteUrl: 'https://www.goldengoose.com/',
      imageUrl: '',
    },
  ],

  [
    'massimo-dutti-andino',
    {
      name: 'Massimo Dutti - Andino',
      address: 'Carrera 11 #82-71, Bogotá',
      latitude: 4.66691,
      longitude: -74.05312,
      categoryIds: [
        'fashion',
      ],
      websiteUrl: 'https://www.massimodutti.com/co/',
      imageUrl: '',
    },
  ],

  [
    'mango-unicentro',
    {
      name: 'Mango - Unicentro',
      address: 'Avenida Carrera 15 #124-30, Bogotá',
      latitude: 4.70220,
      longitude: -74.04150,
      categoryIds: [
        'fashion',
      ],
      websiteUrl: 'https://shop.mango.com/co/',
      imageUrl: '',
    },
  ],

  [
    'tennis-plaza-americas',
    {
      name: 'Tennis - Plaza de las Américas',
      address: 'Carrera 71D #6-94 Sur, Bogotá',
      latitude: 4.61850,
      longitude: -74.13550,
      categoryIds: [
        'fashion',
      ],
      websiteUrl: 'https://www.tennis.com.co/',
      imageUrl: '',
    },
  ],

  [
    'koaj-centro-mayor',
    {
      name: 'Koaj - Centro Mayor',
      address: 'Calle 38A Sur #34D-50, Bogotá',
      latitude: 4.59270,
      longitude: -74.12440,
      categoryIds: [
        'fashion',
      ],
      websiteUrl: 'https://www.koaj.co/',
      imageUrl: '',
    },
  ],

  // -------------------------------------------------------------------------
  // Beauty
  // -------------------------------------------------------------------------

  [
    'loto-del-sur-andino',
    {
      name: 'Loto del Sur - Andino',
      address: 'Carrera 11 #82-71, Bogotá',
      latitude: 4.66691,
      longitude: -74.05312,
      categoryIds: [
        'beauty',
      ],
      websiteUrl: 'https://www.lotodelsur.com/',
      imageUrl: '',
    },
  ],

  [
    'loto-del-sur-unicentro',
    {
      name: 'Loto del Sur - Unicentro',
      address: 'Avenida Carrera 15 #124-30, Bogotá',
      latitude: 4.70220,
      longitude: -74.04150,
      categoryIds: [
        'beauty',
      ],
      websiteUrl: 'https://www.lotodelsur.com/',
      imageUrl: '',
    },
  ],

  [
    'mac-cosmetics-andino',
    {
      name: 'MAC Cosmetics - Andino',
      address: 'Carrera 11 #82-71, Bogotá',
      latitude: 4.66691,
      longitude: -74.05312,
      categoryIds: [
        'beauty',
      ],
      websiteUrl: 'https://www.maccosmetics.com.co/',
      imageUrl: '',
    },
  ],

  [
    'cruz-verde-titan-plaza',
    {
      name: 'Cruz Verde - Titán Plaza',
      address: 'Avenida Boyacá #80-94, Bogotá',
      latitude: 4.69450,
      longitude: -74.08660,
      categoryIds: [
        'beauty',
      ],
      websiteUrl: 'https://www.cruzverde.com.co/',
      imageUrl: '',
    },
  ],

  [
    'farmatodo-colina',
    {
      name: 'Farmatodo - Parque La Colina',
      address: 'Carrera 58D #146-51, Bogotá',
      latitude: 4.73300,
      longitude: -74.06600,
      categoryIds: [
        'beauty',
      ],
      websiteUrl: 'https://www.farmatodo.com.co/',
      imageUrl: '',
    },
  ],

  [
    'loto-del-sur-santafe',
    {
      name: 'Loto del Sur - Santafé',
      address: 'Calle 185 #45-03, Bogotá',
      latitude: 4.76260,
      longitude: -74.04590,
      categoryIds: [
        'beauty',
      ],
      websiteUrl: 'https://www.lotodelsur.com/',
      imageUrl: '',
    },
  ],

  [
    'loccitane-andino',
    {
      name: 'L\'Occitane - Andino',
      address: 'Carrera 11 #82-71, Bogotá',
      latitude: 4.66691,
      longitude: -74.05312,
      categoryIds: [
        'beauty',
      ],
      websiteUrl: 'https://www.loccitane.com/',
      imageUrl: '',
    },
  ],

  [
    'bath-and-body-works-santafe',
    {
      name: 'Bath & Body Works - Santafé',
      address: 'Calle 185 #45-03, Bogotá',
      latitude: 4.76260,
      longitude: -74.04590,
      categoryIds: [
        'beauty',
      ],
      websiteUrl: 'https://www.bathandbodyworks.com/',
      imageUrl: '',
    },
  ],

  [
    'cruz-verde-plaza-americas',
    {
      name: 'Cruz Verde - Plaza de las Américas',
      address: 'Carrera 71D #6-94 Sur, Bogotá',
      latitude: 4.61850,
      longitude: -74.13550,
      categoryIds: [
        'beauty',
      ],
      websiteUrl: 'https://www.cruzverde.com.co/',
      imageUrl: '',
    },
  ],

  // -------------------------------------------------------------------------
  // Technology
  // -------------------------------------------------------------------------

  [
    'ktronix-unicentro',
    {
      name: 'Ktronix Unicentro',
      address: 'Avenida Carrera 15 #122-59, Bogotá',
      latitude: 4.70220,
      longitude: -74.04150,
      categoryIds: [
        'technology',
      ],
      websiteUrl: 'https://www.ktronix.com/',
      imageUrl: '',
    },
  ],

  [
    'ktronix-mallplaza-nqs',
    {
      name: 'Ktronix Mallplaza NQS',
      address: 'Mallplaza NQS, Avenida Ciudad de Lima #28-80, Bogotá',
      latitude: 4.61815,
      longitude: -74.08599,
      categoryIds: [
        'technology',
      ],
      websiteUrl: 'https://www.ktronix.com/',
      imageUrl: '',
    },
  ],

  [
    'samsung-titan-plaza',
    {
      name: 'Samsung - Titán Plaza',
      address: 'Avenida Boyacá #80-94, Bogotá',
      latitude: 4.69450,
      longitude: -74.08660,
      categoryIds: [
        'technology',
      ],
      websiteUrl: 'https://www.samsung.com/co/',
      imageUrl: '',
    },
  ],

  [
    'ktronix-santafe',
    {
      name: 'Ktronix - Santafé',
      address: 'Calle 185 #45-03, Bogotá',
      latitude: 4.76260,
      longitude: -74.04590,
      categoryIds: [
        'technology',
      ],
      websiteUrl: 'https://www.ktronix.com/',
      imageUrl: '',
    },
  ],

  [
    'ktronix-gran-estacion',
    {
      name: 'Ktronix - Gran Estación',
      address: 'Avenida Calle 26 #62-47, Bogotá',
      latitude: 4.64760,
      longitude: -74.10180,
      categoryIds: [
        'technology',
      ],
      websiteUrl: 'https://www.ktronix.com/',
      imageUrl: '',
    },
  ],

  [
    'alkomprar-centro-mayor',
    {
      name: 'Alkomprar - Centro Mayor',
      address: 'Calle 38A Sur #34D-50, Bogotá',
      latitude: 4.59270,
      longitude: -74.12440,
      categoryIds: [
        'technology',
      ],
      websiteUrl: 'https://www.alkomprar.com/',
      imageUrl: '',
    },
  ],

  [
    'ishop-andino',
    {
      name: 'iShop - Andino',
      address: 'Carrera 11 #82-71, Bogotá',
      latitude: 4.66691,
      longitude: -74.05312,
      categoryIds: [
        'technology',
      ],
      websiteUrl: '',
      imageUrl: '',
    },
  ],

  [
    'xiaomi-gran-estacion',
    {
      name: 'Xiaomi - Gran Estación',
      address: 'Avenida Calle 26 #62-47, Bogotá',
      latitude: 4.64760,
      longitude: -74.10180,
      categoryIds: [
        'technology',
      ],
      websiteUrl: 'https://www.mi.com/co/',
      imageUrl: '',
    },
  ],

  [
    'alkomprar-plaza-americas',
    {
      name: 'Alkomprar - Plaza de las Américas',
      address: 'Carrera 71D #6-94 Sur, Bogotá',
      latitude: 4.61850,
      longitude: -74.13550,
      categoryIds: [
        'technology',
      ],
      websiteUrl: 'https://www.alkomprar.com/',
      imageUrl: '',
    },
  ],

  // -------------------------------------------------------------------------
  // Home
  // -------------------------------------------------------------------------

  [
    'homecenter-cedritos',
    {
      name: 'Homecenter Cedritos',
      address: 'Avenida Carrera 9 #152A-23, Bogotá',
      latitude: 4.7305689,
      longitude: -74.0327445,
      categoryIds: [
        'home',
      ],
      websiteUrl: 'https://www.homecenter.com.co/',
      imageUrl: '',
    },
  ],

  [
    'ikea-nqs',
    {
      name: 'IKEA NQS',
      address: 'Mallplaza NQS, Avenida Carrera 30 #19, Bogotá',
      latitude: 4.61815,
      longitude: -74.08599,
      categoryIds: [
        'home',
      ],
      websiteUrl: 'https://www.ikea.com/co/es/',
      imageUrl: '',
    },
  ],

  [
    'tugo-titan-plaza',
    {
      name: 'Tugó - Titán Plaza',
      address: 'Avenida Boyacá #80-94, Bogotá',
      latitude: 4.69450,
      longitude: -74.08660,
      categoryIds: [
        'home',
      ],
      websiteUrl: 'https://www.tugo.com.co/',
      imageUrl: '',
    },
  ],

  [
    'tugo-santafe',
    {
      name: 'Tugó - Santafé',
      address: 'Calle 185 #45-03, Bogotá',
      latitude: 4.76260,
      longitude: -74.04590,
      categoryIds: [
        'home',
      ],
      websiteUrl: 'https://www.tugo.com.co/',
      imageUrl: '',
    },
  ],

  [
    'tugo-gran-estacion',
    {
      name: 'Tugó - Gran Estación',
      address: 'Avenida Calle 26 #62-47, Bogotá',
      latitude: 4.64760,
      longitude: -74.10180,
      categoryIds: [
        'home',
      ],
      websiteUrl: 'https://www.tugo.com.co/',
      imageUrl: '',
    },
  ],

  [
    'home-sentry-andino',
    {
      name: 'Home Sentry - Andino',
      address: 'Carrera 11 #82-71, Bogotá',
      latitude: 4.66691,
      longitude: -74.05312,
      categoryIds: [
        'home',
      ],
      websiteUrl: '',
      imageUrl: '',
    },
  ],

  [
    'zara-home-andino',
    {
      name: 'Zara Home - Andino',
      address: 'Carrera 11 #82-71, Bogotá',
      latitude: 4.66691,
      longitude: -74.05312,
      categoryIds: [
        'home',
      ],
      websiteUrl: 'https://www.zarahome.com/co/',
      imageUrl: '',
    },
  ],

  [
    'home-sentry-santafe',
    {
      name: 'Home Sentry - Santafé',
      address: 'Calle 185 #45-03, Bogotá',
      latitude: 4.76260,
      longitude: -74.04590,
      categoryIds: [
        'home',
      ],
      websiteUrl: '',
      imageUrl: '',
    },
  ],

  [
    'tugo-plaza-americas',
    {
      name: 'Tugó - Plaza de las Américas',
      address: 'Carrera 71D #6-94 Sur, Bogotá',
      latitude: 4.61850,
      longitude: -74.13550,
      categoryIds: [
        'home',
      ],
      websiteUrl: 'https://www.tugo.com.co/',
      imageUrl: '',
    },
  ],

  // -------------------------------------------------------------------------
  // Accessories
  // -------------------------------------------------------------------------

  [
    'tous-andino',
    {
      name: 'TOUS C.C. Andino',
      address: 'Carrera 11 #82-71, Bogotá',
      latitude: 4.66691,
      longitude: -74.05312,
      categoryIds: [
        'accessories',
      ],
      websiteUrl: 'https://www.tous.com/co-es/',
      imageUrl: '',
    },
  ],

  [
    'pandora-unicentro',
    {
      name: 'Pandora Unicentro',
      address: 'Avenida Carrera 15 #124-30, Bogotá',
      latitude: 4.70220,
      longitude: -74.04150,
      categoryIds: [
        'accessories',
      ],
      websiteUrl: 'https://co.pandora.net/',
      imageUrl: '',
    },
  ],

  [
    'swarovski-andino',
    {
      name: 'Swarovski - Andino',
      address: 'Carrera 11 #82-71, Bogotá',
      latitude: 4.66691,
      longitude: -74.05312,
      categoryIds: [
        'accessories',
      ],
      websiteUrl: 'https://www.swarovski.com/',
      imageUrl: '',
    },
  ],

  [
    'pandora-santafe',
    {
      name: 'Pandora - Santafé',
      address: 'Calle 185 #45-03, Bogotá',
      latitude: 4.76260,
      longitude: -74.04590,
      categoryIds: [
        'accessories',
      ],
      websiteUrl: 'https://co.pandora.net/',
      imageUrl: '',
    },
  ],

  [
    'velez-titan-plaza',
    {
      name: 'Vélez - Titán Plaza',
      address: 'Avenida Boyacá #80-94, Bogotá',
      latitude: 4.69450,
      longitude: -74.08660,
      categoryIds: [
        'accessories',
      ],
      websiteUrl: 'https://www.velez.com.co/',
      imageUrl: '',
    },
  ],

  [
    'velez-centro-mayor',
    {
      name: 'Vélez - Centro Mayor',
      address: 'Calle 38A Sur #34D-50, Bogotá',
      latitude: 4.59270,
      longitude: -74.12440,
      categoryIds: [
        'accessories',
      ],
      websiteUrl: 'https://www.velez.com.co/',
      imageUrl: '',
    },
  ],

  [
    'michael-kors-andino',
    {
      name: 'Michael Kors - Andino',
      address: 'Carrera 11 #82-71, Bogotá',
      latitude: 4.66691,
      longitude: -74.05312,
      categoryIds: [
        'accessories',
      ],
      websiteUrl: '',
      imageUrl: '',
    },
  ],

  [
    'swatch-unicentro',
    {
      name: 'Swatch - Unicentro',
      address: 'Avenida Carrera 15 #124-30, Bogotá',
      latitude: 4.70220,
      longitude: -74.04150,
      categoryIds: [
        'accessories',
      ],
      websiteUrl: 'https://www.swatch.com/',
      imageUrl: '',
    },
  ],

  [
    'pandora-titan-plaza',
    {
      name: 'Pandora - Titán Plaza',
      address: 'Avenida Boyacá #80-94, Bogotá',
      latitude: 4.69450,
      longitude: -74.08660,
      categoryIds: [
        'accessories',
      ],
      websiteUrl: 'https://co.pandora.net/',
      imageUrl: '',
    },
  ],

  // -------------------------------------------------------------------------
  // Travel
  // -------------------------------------------------------------------------

  [
    'roncato-andino',
    {
      name: 'Roncato C.C. Andino',
      address: 'Carrera 11 #82-71, Local 229, Bogotá',
      latitude: 4.66691,
      longitude: -74.05312,
      categoryIds: [
        'travel',
      ],
      websiteUrl: '',
      imageUrl: '',
    },
  ],

  [
    'samsonite-unicentro',
    {
      name: 'Samsonite Unicentro',
      address: 'Avenida Carrera 15 #124-30, Local 1-037, Bogotá',
      latitude: 4.70220,
      longitude: -74.04150,
      categoryIds: [
        'travel',
      ],
      websiteUrl: 'https://www.samsonite.com.co/',
      imageUrl: '',
    },
  ],

  [
    'totto-gran-estacion',
    {
      name: 'Totto - Gran Estación',
      address: 'Avenida Calle 26 #62-47, Bogotá',
      latitude: 4.64760,
      longitude: -74.10180,
      categoryIds: [
        'travel',
      ],
      websiteUrl: 'https://www.totto.com/',
      imageUrl: '',
    },
  ],

  [
    'totto-plaza-americas',
    {
      name: 'Totto - Plaza de las Américas',
      address: 'Carrera 71D #6-94 Sur, Bogotá',
      latitude: 4.61850,
      longitude: -74.13550,
      categoryIds: [
        'travel',
      ],
      websiteUrl: 'https://www.totto.com/',
      imageUrl: '',
    },
  ],

  [
    'samsonite-santafe',
    {
      name: 'Samsonite - Santafé',
      address: 'Calle 185 #45-03, Bogotá',
      latitude: 4.76260,
      longitude: -74.04590,
      categoryIds: [
        'travel',
      ],
      websiteUrl: 'https://www.samsonite.com.co/',
      imageUrl: '',
    },
  ],

  [
    'samsonite-titan-plaza',
    {
      name: 'Samsonite - Titán Plaza',
      address: 'Avenida Boyacá #80-94, Bogotá',
      latitude: 4.69450,
      longitude: -74.08660,
      categoryIds: [
        'travel',
      ],
      websiteUrl: 'https://www.samsonite.com.co/',
      imageUrl: '',
    },
  ],

  [
    'tumi-andino',
    {
      name: 'TUMI - Andino',
      address: 'Carrera 11 #82-71, Bogotá',
      latitude: 4.66691,
      longitude: -74.05312,
      categoryIds: [
        'travel',
      ],
      websiteUrl: 'https://www.tumi.com/',
      imageUrl: '',
    },
  ],

  [
    'totto-unicentro',
    {
      name: 'Totto - Unicentro',
      address: 'Avenida Carrera 15 #124-30, Bogotá',
      latitude: 4.70220,
      longitude: -74.04150,
      categoryIds: [
        'travel',
      ],
      websiteUrl: 'https://www.totto.com/',
      imageUrl: '',
    },
  ],

  [
    'totto-hayuelos',
    {
      name: 'Totto - Hayuelos',
      address: 'Calle 20 #82-52, Bogotá',
      latitude: 4.66330,
      longitude: -74.13100,
      categoryIds: [
        'travel',
      ],
      websiteUrl: 'https://www.totto.com/',
      imageUrl: '',
    },
  ],

  // -------------------------------------------------------------------------
  // Gifts
  // -------------------------------------------------------------------------

  [
    'miniso-mallplaza-nqs',
    {
      name: 'Miniso Mallplaza NQS',
      address: 'Avenida Carrera 30 con Calle 19, Bogotá',
      latitude: 4.61815,
      longitude: -74.08599,
      categoryIds: [
        'gifts',
      ],
      websiteUrl: 'https://www.miniso.co/',
      imageUrl: '',
    },
  ],

  [
    'miniso-unicentro-occidente',
    {
      name: 'Miniso Unicentro de Occidente',
      address: 'Carrera 111C #86-05, Bogotá',
      latitude: 4.72333,
      longitude: -74.11448,
      categoryIds: [
        'gifts',
      ],
      websiteUrl: 'https://www.miniso.co/',
      imageUrl: '',
    },
  ],

  [
    'panamericana-unicentro',
    {
      name: 'Panamericana - Unicentro',
      address: 'Avenida Carrera 15 #124-30, Bogotá',
      latitude: 4.70220,
      longitude: -74.04150,
      categoryIds: [
        'gifts',
      ],
      websiteUrl: 'https://www.panamericana.com.co/',
      imageUrl: '',
    },
  ],

  [
    'panamericana-gran-estacion',
    {
      name: 'Panamericana - Gran Estación',
      address: 'Avenida Calle 26 #62-47, Bogotá',
      latitude: 4.64760,
      longitude: -74.10180,
      categoryIds: [
        'gifts',
      ],
      websiteUrl: 'https://www.panamericana.com.co/',
      imageUrl: '',
    },
  ],

  [
    'pepe-ganga-centro-mayor',
    {
      name: 'Pepe Ganga - Centro Mayor',
      address: 'Calle 38A Sur #34D-50, Bogotá',
      latitude: 4.59270,
      longitude: -74.12440,
      categoryIds: [
        'gifts',
      ],
      websiteUrl: 'https://www.pepeganga.com/',
      imageUrl: '',
    },
  ],

  [
    'miniso-titan-plaza',
    {
      name: 'Miniso - Titán Plaza',
      address: 'Avenida Boyacá #80-94, Bogotá',
      latitude: 4.69450,
      longitude: -74.08660,
      categoryIds: [
        'gifts',
      ],
      websiteUrl: 'https://www.miniso.co/',
      imageUrl: '',
    },
  ],

  [
    'miniso-gran-estacion',
    {
      name: 'Miniso - Gran Estación',
      address: 'Avenida Calle 26 #62-47, Bogotá',
      latitude: 4.64760,
      longitude: -74.10180,
      categoryIds: [
        'gifts',
      ],
      websiteUrl: 'https://www.miniso.co/',
      imageUrl: '',
    },
  ],

  [
    'panamericana-santafe',
    {
      name: 'Panamericana - Santafé',
      address: 'Calle 185 #45-03, Bogotá',
      latitude: 4.76260,
      longitude: -74.04590,
      categoryIds: [
        'gifts',
      ],
      websiteUrl: 'https://www.panamericana.com.co/',
      imageUrl: '',
    },
  ],

  [
    'pepe-ganga-titan-plaza',
    {
      name: 'Pepe Ganga - Titán Plaza',
      address: 'Avenida Boyacá #80-94, Bogotá',
      latitude: 4.69450,
      longitude: -74.08660,
      categoryIds: [
        'gifts',
      ],
      websiteUrl: 'https://www.pepeganga.com/',
      imageUrl: '',
    },
  ],

  // -------------------------------------------------------------------------
  // Other
  // -------------------------------------------------------------------------

  [
    'falabella-unicentro',
    {
      name: 'Falabella Unicentro',
      address: 'Avenida Carrera 15 #123-30, Bogotá',
      latitude: 4.70220,
      longitude: -74.04150,
      categoryIds: [
        'other',
      ],
      websiteUrl: 'https://www.falabella.com.co/',
      imageUrl: '',
    },
  ],

  [
    'exito-mallplaza-nqs',
    {
      name: 'Éxito Mallplaza NQS',
      address: 'Avenida Carrera 30 #19, Bogotá',
      latitude: 4.61815,
      longitude: -74.08599,
      categoryIds: [
        'other',
      ],
      websiteUrl: 'https://www.exito.com/',
      imageUrl: '',
    },
  ],
  [
    'exito-colina',
    {
      name: 'Éxito - Parque La Colina',
      address: 'Carrera 58D #146-51, Bogotá',
      latitude: 4.73300,
      longitude: -74.06600,
      categoryIds: [
        'other',
      ],
      websiteUrl: 'https://www.exito.com/',
      imageUrl: '',
    },
  ],

  [
    'falabella-santafe',
    {
      name: 'Falabella - Santafé',
      address: 'Calle 185 #45-03, Bogotá',
      latitude: 4.76260,
      longitude: -74.04590,
      categoryIds: [
        'other',
      ],
      websiteUrl: 'https://www.falabella.com.co/',
      imageUrl: '',
    },
  ],

  [
    'falabella-titan-plaza',
    {
      name: 'Falabella - Titán Plaza',
      address: 'Avenida Boyacá #80-94, Bogotá',
      latitude: 4.69450,
      longitude: -74.08660,
      categoryIds: [
        'other',
      ],
      websiteUrl: 'https://www.falabella.com.co/',
      imageUrl: '',
    },
  ],

  [
    'jumbo-hayuelos',
    {
      name: 'Jumbo - Hayuelos',
      address: 'Calle 20 #82-52, Bogotá',
      latitude: 4.66330,
      longitude: -74.13100,
      categoryIds: [
        'other',
      ],
      websiteUrl: 'https://www.tiendasjumbo.co/',
      imageUrl: '',
    },
  ],
  [
    'falabella-andino',
    {
      name: 'Falabella - Andino',
      address: 'Carrera 11 #82-71, Bogotá',
      latitude: 4.66691,
      longitude: -74.05312,
      categoryIds: [
        'other',
      ],
      websiteUrl: 'https://www.falabella.com.co/',
      imageUrl: '',
    },
  ],

  [
    'exito-centro-mayor',
    {
      name: 'Éxito - Centro Mayor',
      address: 'Calle 38A Sur #34D-50, Bogotá',
      latitude: 4.59270,
      longitude: -74.12440,
      categoryIds: [
        'other',
      ],
      websiteUrl: 'https://www.exito.com/',
      imageUrl: '',
    },
  ],

  [
    'jumbo-titan-plaza',
    {
      name: 'Jumbo - Titán Plaza',
      address: 'Avenida Boyacá #80-94, Bogotá',
      latitude: 4.69450,
      longitude: -74.08660,
      categoryIds: [
        'other',
      ],
      websiteUrl: 'https://www.tiendasjumbo.co/',
      imageUrl: '',
    },
  ],
]);


function usage() {
  return [
    'Usage:',
    '  npm run seed:stores -- --project <project-id> [--dry-run]',
  ].join('\n');
}


function parseArguments(argumentsList) {
  const options = {
    projectId: null,
    dryRun: false,
  };

  for (let index = 0; index < argumentsList.length; index += 1) {
    const argument = argumentsList[index];

    if (argument === '--project') {
      options.projectId = argumentsList[index + 1] ?? null;
      index += 1;
    } else if (argument === '--dry-run') {
      options.dryRun = true;
    } else if (argument === '--help' || argument === '-h') {
      console.log(usage());
      process.exit(0);
    } else {
      throw new Error(`Unknown argument: ${argument}`);
    }
  }

  if (!options.projectId) {
    throw new Error(`--project is required.\n\n${usage()}`);
  }

  return options;
}


async function main() {
  const options = parseArguments(process.argv.slice(2));

  const usingEmulator = Boolean(
    process.env.FIRESTORE_EMULATOR_HOST,
  );

  const app = initializeApp({
    projectId: options.projectId,
    ...(usingEmulator
      ? {}
      : { credential: applicationDefault() }),
  });

  const firestore = getFirestore(app);
  const batch = firestore.batch();

  console.log(
    `${
      options.dryRun ? 'Would seed' : 'Seeding'
    } ${stores.size} stores in ${options.projectId}`,
  );

  for (const [storeId, store] of stores) {
    const reference = firestore
      .collection('stores')
      .doc(storeId);

    console.log(
      `- ${storeId} [${store.categoryIds.join(', ')}]`,
    );

    if (!options.dryRun) {
      batch.set(
        reference,
        store,
        { merge: true },
      );
    }
  }

  if (options.dryRun) {
    console.log(
      'Dry run complete; no documents were changed.',
    );
    return;
  }

  await batch.commit();

  console.log('Store seed complete.');
}


main().catch((error) => {
  console.error(error.message);
  process.exitCode = 1;
});