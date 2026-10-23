import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "functions"))
from analytics.bq5_zero_products import count_zero_product_users
from analytics.dashboard_views import saved_summary, compute_saved
from unittest.mock import Mock


class BQ5Test(unittest.TestCase):
    def test_no_users(self):
        self.assertEqual(count_zero_product_users([], []), 0)

    def test_all_users_have_zero_products(self):
        self.assertEqual(count_zero_product_users([], [("a", {}), ("b", {})]), 2)

    def test_one_active_user(self):
        self.assertEqual(count_zero_product_users(["a"], [("a", {}), ("b", {})]), 1)

    def test_repeated_products_count_owner_once(self):
        self.assertEqual(count_zero_product_users(["a", "a"], [("a", {}), ("b", {})]), 1)

    def test_deleted_owner_is_ignored(self):
        self.assertEqual(count_zero_product_users(["deleted"], [("a", {})]), 1)

    def test_duplicate_profiles_are_not_double_counted(self):
        self.assertEqual(count_zero_product_users([], [("a", {}), ("a", {})]), 1)

    def test_purchased_products_keep_existing_semantics(self):
        result = saved_summary([("p", {"ownerId": "a", "purchased": True})], [("a", {})])
        self.assertEqual(result["zeroProductUsers"], 0)

    def test_shared_saved_response_is_unchanged(self):
        products = [("p1", {"ownerId": "a"}), ("p2", {"ownerId": "a"})]
        self.assertEqual(saved_summary(products, [("a", {}), ("b", {})]), {
            "activeUsers": 1, "zeroProductUsers": 1, "totalProducts": 2,
            "singleProductUsers": 0, "multipleProductUsers": 1,
            "averagePerActiveUser": 2.0, "distributionCounts": [1, 0, 0, 0, 0],
        })

    def test_firestore_adapter_reads_users_and_products(self):
        db = Mock()
        products = [Mock(id="p", to_dict=Mock(return_value={"ownerId": "a"}))]
        profiles = [Mock(id="a", to_dict=Mock(return_value={})), Mock(id="b", to_dict=Mock(return_value={}))]
        db.collection.side_effect = lambda name: Mock(stream=Mock(return_value=products if name == "products" else profiles))
        self.assertEqual(compute_saved(db, {})["zeroProductUsers"], 1)
        self.assertEqual([c.args[0] for c in db.collection.call_args_list], ["products", "users"])
