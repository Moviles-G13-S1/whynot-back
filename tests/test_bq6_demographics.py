"""Unit tests for BQ6: buyer demographics per category."""

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace


FUNCTIONS_DIR = Path(__file__).resolve().parents[1] / "functions"
sys.path.insert(0, str(FUNCTIONS_DIR))

from analytics.bq6_demographics import (  # noqa: E402
    compute_demographic_profile,
    compute_from_firestore,
)


def product(owner_id, category_id="tech", purchased=True):
    return {
        "ownerId": owner_id,
        "categoryId": category_id,
        "purchased": purchased,
    }


def user(age=25, gender="Female", city_id="bogota"):
    profile = {"age": age, "gender": gender}
    if city_id is not None:
        profile["cityId"] = city_id
    return profile


def only_category(result):
    self_check = result["categories"]
    assert len(self_check) == 1, self_check
    return self_check[0]


class BuyerSelectionTest(unittest.TestCase):
    def test_buyer_counted_once_per_category_despite_many_purchases(self):
        result = compute_demographic_profile(
            [product("u1"), product("u1"), product("u1", "beauty")],
            {"u1": user()},
        )

        self.assertEqual(
            {c["categoryId"]: c["buyers"] for c in result["categories"]},
            {"tech": 1, "beauty": 1},
        )
        self.assertEqual(result["totalBuyers"], 1)

    def test_products_not_purchased_are_ignored(self):
        result = compute_demographic_profile(
            [product("u1", purchased=False), product("u2")],
            {"u1": user(), "u2": user()},
        )

        self.assertEqual(only_category(result)["buyers"], 1)
        self.assertEqual(result["totalBuyers"], 1)

    def test_owner_without_profile_is_skipped(self):
        result = compute_demographic_profile(
            [product("ghost"), product("u1")],
            {"u1": user()},
        )

        self.assertEqual(only_category(result)["buyers"], 1)
        self.assertEqual(result["totalBuyers"], 1)

    def test_no_purchases_gives_empty_profile(self):
        result = compute_demographic_profile([], {})

        self.assertEqual(
            result,
            {"categories": [], "totalBuyers": 0, "profilesWithoutCity": 0},
        )

    def test_categories_sorted_by_buyers_then_id_with_names(self):
        result = compute_demographic_profile(
            [
                product("u1", "tech"),
                product("u1", "beauty"),
                product("u1", "home"),
                product("u2", "home"),
            ],
            {"u1": user(), "u2": user()},
            categories={"home": "Home"},
        )

        self.assertEqual(
            [(c["categoryId"], c["categoryName"]) for c in result["categories"]],
            [("home", "Home"), ("beauty", "beauty"), ("tech", "tech")],
        )


class MedianAgeTest(unittest.TestCase):
    def median_for(self, ages):
        users = {f"u{i}": user(age=age) for i, age in enumerate(ages)}
        result = compute_demographic_profile(
            [product(uid) for uid in users],
            users,
        )
        return only_category(result)["medianAge"]

    def test_odd_count_uses_middle_age(self):
        self.assertEqual(self.median_for([40, 20, 30]), 30)

    def test_even_count_floors_average_of_middles(self):
        self.assertEqual(self.median_for([20, 25, 30, 40]), 27)

    def test_no_valid_age_gives_none(self):
        self.assertIsNone(self.median_for([0, 0]))

    def test_invalid_ages_are_left_out(self):
        self.assertEqual(self.median_for([0, 30, 50]), 40)


class AgeGroupTest(unittest.TestCase):
    def test_every_group_is_present_with_its_count(self):
        ages = [13, 17, 18, 30, 44, 45, 90]
        users = {f"u{i}": user(age=age) for i, age in enumerate(ages)}
        result = compute_demographic_profile(
            [product(uid) for uid in users],
            users,
        )

        self.assertEqual(
            only_category(result)["ageGroups"],
            [
                {"label": "13–17", "userCount": 2},
                {"label": "18–24", "userCount": 1},
                {"label": "25–34", "userCount": 1},
                {"label": "35–44", "userCount": 1},
                {"label": "45+", "userCount": 2},
            ],
        )


class GenderTest(unittest.TestCase):
    def test_percentages_sorted_by_count_with_unknown_for_blank(self):
        genders = ["Female", "Female", "Male", "", None]
        users = {}
        for i, gender in enumerate(genders):
            profile = user()
            if gender is None:
                del profile["gender"]
            else:
                profile["gender"] = gender
            users[f"u{i}"] = profile

        result = compute_demographic_profile(
            [product(uid) for uid in users],
            users,
        )

        self.assertEqual(
            only_category(result)["genders"],
            [
                {"gender": "Female", "userCount": 2, "percentage": 40.0},
                {"gender": "Unknown", "userCount": 2, "percentage": 40.0},
                {"gender": "Male", "userCount": 1, "percentage": 20.0},
            ],
        )


class CityTest(unittest.TestCase):
    def test_top_four_cities_and_the_rest_merged_into_other(self):
        city_ids = (
            ["bogota"] * 3 + ["cali"] * 2 + ["medellin"] * 2
            + ["pasto", "tunja", "neiva"]
        )
        users = {f"u{i}": user(city_id=c) for i, c in enumerate(city_ids)}

        result = compute_demographic_profile(
            [product(uid) for uid in users],
            users,
            cities={"bogota": "Bogotá", "cali": "Cali"},
        )

        self.assertEqual(
            only_category(result)["topCities"],
            [
                {"cityId": "bogota", "userCount": 3, "cityName": "Bogotá"},
                {"cityId": "cali", "userCount": 2, "cityName": "Cali"},
                {"cityId": "medellin", "userCount": 2},
                {"cityId": "neiva", "userCount": 1},
                {"cityId": "other", "userCount": 2, "cityName": "Other cities"},
            ],
        )

    def test_missing_or_blank_city_is_unknown_and_counted(self):
        users = {
            "u1": user(city_id=None),
            "u2": user(city_id="  "),
            "u3": user(city_id="cali"),
        }

        result = compute_demographic_profile(
            [product(uid) for uid in users] + [product("u1", "beauty")],
            users,
        )

        tech = next(c for c in result["categories"] if c["categoryId"] == "tech")
        self.assertEqual(
            tech["topCities"],
            [
                {"cityId": "unknown", "userCount": 2},
                {"cityId": "cali", "userCount": 1},
            ],
        )
        self.assertEqual(result["profilesWithoutCity"], 2)


class FakeSnapshot:
    def __init__(self, doc_id, data):
        self.id = doc_id
        self._data = data
        self.exists = data is not None

    def to_dict(self):
        return self._data


class FakeDb:
    """Just enough of the Firestore client for compute_from_firestore."""

    def __init__(self, collections):
        self.collections = collections
        self.queries = []
        self.fetched_users = []

    def collection(self, name):
        db = self
        docs = self.collections.get(name, {})

        class Collection:
            def where(self, field, op, value):
                db.queries.append((name, field, op, value))
                matching = {
                    doc_id: data for doc_id, data in docs.items()
                    if op == "==" and data.get(field) == value
                }
                return SimpleNamespace(stream=lambda: [
                    FakeSnapshot(doc_id, data)
                    for doc_id, data in matching.items()
                ])

            def stream(self):
                return [FakeSnapshot(i, d) for i, d in docs.items()]

            def document(self, doc_id):
                return SimpleNamespace(id=doc_id, collection=name)

        return Collection()

    def get_all(self, refs):
        users = self.collections.get("users", {})
        for ref in refs:
            self.fetched_users.append(ref.id)
            yield FakeSnapshot(ref.id, users.get(ref.id))


class FirestoreReadTest(unittest.TestCase):
    def test_reads_purchased_products_and_only_their_owners(self):
        db = FakeDb({
            "products": {
                "p1": product("u1"),
                "p2": product("u2", purchased=False),
                "p3": product("ghost"),
            },
            "users": {"u1": user(), "u2": user(), "u3": user()},
            "categories": {"tech": {"name": "Tech"}},
            "cities": {"bogota": {"name": "Bogotá"}},
        })

        result = compute_from_firestore(db, {})

        self.assertEqual(db.queries, [("products", "purchased", "==", True)])
        self.assertEqual(sorted(db.fetched_users), ["ghost", "u1"])
        category = only_category(result)
        self.assertEqual(category["categoryName"], "Tech")
        self.assertEqual(category["buyers"], 1)
        self.assertEqual(
            category["topCities"],
            [{"cityId": "bogota", "userCount": 1, "cityName": "Bogotá"}],
        )


if __name__ == "__main__":
    unittest.main()
