import pytest
from django.db import IntegrityError, transaction

from tests.factories import make_area, make_site

pytestmark = pytest.mark.django_db


def test_site_created_with_expected_fields():
    site = make_site(name="Houston", slug="houston")
    assert site.name == "Houston"
    assert site.is_active is True


def test_area_slug_unique_per_site():
    site = make_site()
    make_area(site=site, slug="katy")
    with pytest.raises(IntegrityError), transaction.atomic():
        make_area(site=site, slug="katy")


def test_area_slug_can_repeat_across_sites():
    site_a = make_site()
    site_b = make_site()
    make_area(site=site_a, slug="downtown")
    # Should not raise — unique_together is scoped to (site, slug).
    make_area(site=site_b, slug="downtown")
