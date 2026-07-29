import pytest

from apps.postings.exceptions import InvalidCategoryAssignment
from apps.postings.services import create_posting
from tests.factories import make_category, make_site

pytestmark = pytest.mark.django_db


def test_category_with_no_children_is_leaf():
    category = make_category()
    assert category.is_leaf is True


def test_category_with_children_is_not_leaf():
    parent = make_category()
    make_category(parent=parent, channel=parent.channel)
    assert parent.is_leaf is False


def test_posting_rejects_assignment_to_non_leaf_category():
    parent = make_category()
    make_category(parent=parent, channel=parent.channel)
    site = make_site()

    with pytest.raises(InvalidCategoryAssignment):
        create_posting(
            site=site,
            category=parent,
            title="t",
            body="b",
            contact_email="poster@example.com",
        )


def test_posting_allowed_on_leaf_category():
    category = make_category()
    site = make_site()

    posting, token = create_posting(
        site=site,
        category=category,
        title="t",
        body="b",
        contact_email="poster@example.com",
    )
    assert posting.category == category
    assert token
