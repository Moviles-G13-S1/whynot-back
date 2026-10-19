"""Dependency-free helpers for demographic recommendation logic."""


def has_valid_demographics(user):
    """Return whether a profile contains the fields used for ranking."""
    if not isinstance(user, dict):
        return False

    age = user.get("age")
    return (
        isinstance(user.get("gender"), str)
        and bool(user["gender"].strip())
        and isinstance(user.get("preferredCategoryId"), str)
        and bool(user["preferredCategoryId"].strip())
        and isinstance(age, int)
        and not isinstance(age, bool)
        and 13 <= age <= 120
    )
