import pytest

from jyyfinhub_spendtracker.categories import SPEND_CATEGORIES, is_valid_pair


def test_declared_pair_is_valid() -> None:
    """Test every declared category and subcategory in SPEND_CATEGORIES is valid"""
    for category, subcategories in SPEND_CATEGORIES.items():
        assert is_valid_pair(category, None)
        for subcategory in subcategories:
            assert is_valid_pair(category, subcategory)


@pytest.mark.parametrize(
    "category, subcategory, expected",
    [
        ("Housing", "Rent", True),  # basic valid test
        ("Groceries", None, True),  # valid sub-category none test
        ("Groceries", "Others", False),  # non-existent sub-category
        ("Random", "", False),  # non-existent category
        ("Housing", "Gym", False),  # bad combo
        ("housing", "Rent", False),  # case sensitivity
    ],
)
def test_is_valid_pair(category: str, subcategory: str | None, expected: bool) -> None:
    """Test edge pair cases"""
    assert is_valid_pair(category, subcategory) is expected
