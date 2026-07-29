import pytest

from apps.postings.forms import PostingCreateForm
from tests.factories import make_area, make_category, make_site

pytestmark = pytest.mark.django_db


def test_area_field_required_when_site_has_areas():
    site = make_site()
    area = make_area(site=site)

    form = PostingCreateForm(site=site)

    assert form.fields["area"].required is True
    assert list(form.fields["area"].queryset) == [area]


def test_area_field_absent_when_site_has_no_areas():
    site = make_site()

    form = PostingCreateForm(site=site)

    assert "area" not in form.fields


def test_category_queryset_excludes_non_leaf_categories():
    site = make_site()
    parent = make_category()
    make_category(parent=parent, channel=parent.channel)

    form = PostingCreateForm(site=site)

    assert parent not in form.fields["category"].queryset
