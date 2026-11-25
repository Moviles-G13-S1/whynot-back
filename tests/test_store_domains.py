"""Santiago's Sprint 4 BQ: which online stores appear most in saved products."""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'functions'))
from analytics.store_domains import (  # noqa: E402
    compute_from_firestore,
    compute_store_domains,
    normalize_domain,
    store_names_by_domain,
)


def product(url, owner='u1', purchased=False, category='fashion'):
    return {'productUrl': url, 'ownerId': owner, 'purchased': purchased, 'categoryId': category}


class NormalizeDomainTest(unittest.TestCase):
    def test_strips_subdomains_scheme_path_and_case(self):
        self.assertEqual(normalize_domain('https://www2.hm.com/es_co/index.html'), 'hm.com')
        self.assertEqual(normalize_domain('HTTP://WWW.Zara.com/co/'), 'zara.com')
        self.assertEqual(normalize_domain('https://shop.mango.com/co/'), 'mango.com')
        self.assertEqual(normalize_domain('https://co.pandora.net/'), 'pandora.net')
        self.assertEqual(normalize_domain('zara.com/co/item?id=1'), 'zara.com')
        self.assertEqual(normalize_domain('https://www.amazon.com.:443/dp/1'), 'amazon.com')

    def test_keeps_three_labels_under_country_suffixes(self):
        self.assertEqual(normalize_domain('https://www.falabella.com.co/falabella-co/product/1'), 'falabella.com.co')
        self.assertEqual(normalize_domain('https://m.mercadolibre.com.co/p/1'), 'mercadolibre.com.co')
        self.assertEqual(normalize_domain('https://www.asos.co.uk/'), 'asos.co.uk')
        self.assertEqual(normalize_domain('https://www.koaj.co/'), 'koaj.co')

    def test_rejects_unusable_links(self):
        for url in (None, '', '   ', 'not a link', 'ftp://zara.com/file', 'https://localhost:5000/',
                    'http://192.168.0.1/item', 'mailto:someone@zara.com', 'https://zara/', 42):
            with self.subTest(url=url):
                self.assertIsNone(normalize_domain(url))


class StoreNamesTest(unittest.TestCase):
    def test_uses_brand_before_dash_or_shared_words(self):
        names = store_names_by_domain([
            {'name': 'Ktronix Unicentro', 'websiteUrl': 'https://www.ktronix.com/'},
            {'name': 'Ktronix - Santafé', 'websiteUrl': 'https://www.ktronix.com/'},
            {'name': 'Pandora Unicentro', 'websiteUrl': 'https://co.pandora.net/'},
            {'name': 'Pandora Santafé', 'websiteUrl': 'https://co.pandora.net/'},
            {'name': 'IKEA NQS', 'websiteUrl': 'https://www.ikea.com/co/es/'},
            {'name': 'Roncato C.C. Andino', 'websiteUrl': ''},
        ])
        self.assertEqual(names, {'ktronix.com': 'Ktronix', 'pandora.net': 'Pandora', 'ikea.com': 'IKEA NQS'})


class StoreDomainsTest(unittest.TestCase):
    def test_empty(self):
        result = compute_store_domains([])
        self.assertEqual(result['totalProducts'], 0)
        self.assertIsNone(result['linkCoverage'])
        self.assertEqual(result['stores'], [])
        self.assertEqual(result['otherStores'], {'stores': 0, 'products': 0})

    def test_ranks_domains_with_users_purchases_and_names(self):
        products = [
            product('https://www.zara.com/co/a', 'u1', True),
            product('https://zara.com/co/b', 'u2'),
            product('https://www.zara.com/co/c', 'u2'),
            product('https://www.falabella.com.co/x', 'u3', True, 'technology'),
            product('https://www.amazon.com/dp/1', 'u1', False, 'technology'),
            product(''),
            product('not a link'),
        ]
        stores = [{'name': 'ZARA - Andino', 'websiteUrl': 'https://www.zara.com/co/'},
                  {'name': 'Falabella Unicentro', 'websiteUrl': 'https://www.falabella.com.co/'}]
        result = compute_store_domains(products, stores, {'fashion': 'Fashion'})

        self.assertEqual(result['totalProducts'], 7)
        self.assertEqual(result['linkedProducts'], 5)
        self.assertEqual(result['withoutLink'], 1)
        self.assertEqual(result['invalidLink'], 1)
        self.assertEqual(result['linkCoverage'], 71.4)
        self.assertEqual(result['distinctStores'], 3)
        self.assertEqual(result['knownStores'], 2)

        zara = result['stores'][0]
        self.assertEqual(zara, {'domain': 'zara.com', 'name': 'ZARA', 'knownStore': True, 'products': 3,
                                'users': 2, 'purchased': 1, 'purchasedPercentage': 33.3, 'share': 60.0})
        # Ties on products and users fall back to the domain, so the order is stable.
        self.assertEqual([row['domain'] for row in result['stores']], ['zara.com', 'amazon.com', 'falabella.com.co'])
        amazon = result['stores'][1]
        self.assertEqual((amazon['name'], amazon['knownStore']), ('amazon.com', False))

    def test_limit_groups_the_remaining_stores(self):
        products = [product(f'https://store{index}.com/p') for index in range(4)] + [product('https://store0.com/q')]
        result = compute_store_domains(products, limit=2)
        self.assertEqual([row['domain'] for row in result['stores']], ['store0.com', 'store1.com'])
        self.assertEqual(result['otherStores'], {'stores': 2, 'products': 2})

    def test_category_leaders_keep_ties(self):
        products = [
            product('https://zara.com/1', category='fashion'),
            product('https://hm.com/1', category='fashion'),
            product('https://ktronix.com/1', category='technology'),
            product('https://ktronix.com/2', category='technology'),
            product('https://alkosto.com/1', category='technology'),
            product('', category='home'),
        ]
        result = compute_store_domains(products, categories={'fashion': 'Fashion'})
        self.assertEqual(result['categoryLeaders'], [
            {'categoryId': 'fashion', 'categoryName': 'Fashion', 'products': 1,
             'stores': [{'domain': 'hm.com', 'name': 'hm.com'}, {'domain': 'zara.com', 'name': 'zara.com'}]},
            {'categoryId': 'technology', 'categoryName': 'technology', 'products': 2,
             'stores': [{'domain': 'ktronix.com', 'name': 'ktronix.com'}]},
        ])

    def test_owner_and_purchase_fields_are_defensive(self):
        result = compute_store_domains([{'productUrl': 'zara.com', 'purchased': 'yes'}, {'productUrl': 'zara.com', 'ownerId': 7}])
        row = result['stores'][0]
        self.assertEqual((row['products'], row['users'], row['purchased']), (2, 0, 0))


def snapshot(doc_id, data):
    return SimpleNamespace(id=doc_id, to_dict=lambda: data)


class StoreDomainsFirestoreTest(unittest.TestCase):
    def fake_db(self):
        collections = {
            'products': [snapshot('p1', product('https://www.zara.com/co/1')), snapshot('p2', product(''))],
            'stores': [snapshot('zara-andino', {'name': 'ZARA - Andino', 'websiteUrl': 'https://www.zara.com/co/'})],
            'categories': [snapshot('fashion', {'name': 'Fashion'})],
        }
        db = Mock()
        db.collection.side_effect = lambda name: SimpleNamespace(stream=lambda: iter(collections[name]))
        return db

    def test_reads_products_stores_and_categories(self):
        result = compute_from_firestore(self.fake_db(), {'limit': 5})
        self.assertEqual(result['limit'], 5)
        self.assertEqual(result['stores'][0]['name'], 'ZARA')
        self.assertEqual(result['categoryLeaders'][0]['categoryName'], 'Fashion')
        self.assertEqual(result['linkCoverage'], 50.0)

    def test_invalid_limits_fall_back_or_clamp(self):
        db = self.fake_db()
        self.assertEqual(compute_from_firestore(db, {'limit': 'all'})['limit'], 10)
        self.assertEqual(compute_from_firestore(db, {'limit': True})['limit'], 10)
        self.assertEqual(compute_from_firestore(db, {'limit': 0})['limit'], 1)
        self.assertEqual(compute_from_firestore(db, {'limit': 500})['limit'], 50)
        self.assertEqual(compute_from_firestore(db, None)['limit'], 10)

    def test_admin_endpoint_registration_and_access(self):
        from analytics import endpoint
        from firebase_functions import https_fn
        self.assertIs(endpoint.METRICS['store_domains'], compute_from_firestore)
        request = SimpleNamespace(auth=SimpleNamespace(token={'admin': True}),
                                  data={'metric': 'store_domains', 'params': {}})
        with patch.object(endpoint.firestore, 'client', return_value=self.fake_db()):
            response = endpoint.get_admin_analytics(request)
        self.assertEqual(response['metric'], 'store_domains')
        self.assertEqual(response['data']['distinctStores'], 1)
        request.auth.token = {'admin': False}
        with self.assertRaises(https_fn.HttpsError):
            endpoint.get_admin_analytics(request)


if __name__ == '__main__':
    unittest.main()
