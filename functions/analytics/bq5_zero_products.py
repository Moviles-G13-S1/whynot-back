"""BQ5: registered users who currently own no products (Martin Riveira)."""


def count_zero_product_users(product_owner_ids, profiles):
    owners = set(product_owner_ids)
    registered_ids = {uid for uid, _ in profiles}
    return len(registered_ids - owners)
