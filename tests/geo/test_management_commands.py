import pytest
from django.core.management import call_command

from apps.geo.models import Site
from apps.taxonomy.models import Category

pytestmark = pytest.mark.django_db


def test_seed_dev_data_creates_a_site_and_leaf_categories():
    call_command("seed_dev_data")

    assert Site.objects.filter(slug="dev").exists()
    assert Category.objects.filter(is_active=True).exists()
    assert any(category.is_leaf for category in Category.objects.all())


def test_seed_dev_data_is_idempotent():
    call_command("seed_dev_data")
    call_command("seed_dev_data")

    assert Site.objects.filter(slug="dev").count() == 1
