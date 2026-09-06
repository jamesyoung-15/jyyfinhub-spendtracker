"""Spend category vocabulary and the category/subcategory validity rule."""

# Empty tuple means the category is flat. There is no "Other" subcategory; None means no subcategory.
SPEND_CATEGORIES: dict[str, tuple[str, ...]] = {
    "Housing": ("Rent", "Electricity", "Insurance"),
    "Utility": ("Internet", "Phone"),
    "Subscriptions": ("Productivity", "Entertainment", "Gaming"),
    "Tech": ("Hardware", "Cloud", "Software"),
    "Groceries": (),
    "Restaurants": ("Fast Food", "Dining", "Cafe"),
    "Transit": (),
    "Travel": ("Accommodation", "Transport", "Activities"),
    "Health & Fitness": ("Gym", "Sports", "Medical"),
    "Lifestyle": ("Personal Care", "Clothing", "Household"),
    "Leisure": ("Gaming", "Entertainment", "Hobbies"),
}


def is_valid_pair(category: str, subcategory: str | None) -> bool:
    """Whether a category/subcategory combination is allowed.

    A None subcategory is always valid. Services raise the domain exception; this only answers the
    question, so the API and CLI share one definition of validity.
    """
    subcategories = SPEND_CATEGORIES.get(category)
    if subcategories is None:
        return False
    return subcategory is None or subcategory in subcategories
