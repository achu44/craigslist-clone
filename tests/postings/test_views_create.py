from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.postings.models import Posting
from apps.taxonomy.models import Category
from tests.factories import make_area, make_category, make_posting, make_site

pytestmark = pytest.mark.django_db


def _post_data(category, **overrides):
    data = {
        "category": category.pk,
        "title": "A nice couch",
        "body": "Barely used",
        "contact_email": "poster@example.com",
    }
    data.update(overrides)
    return data


def test_create_valid_post_creates_pending_posting_and_redirects(client):
    site = make_site()
    category = make_category()

    response = client.post(reverse("postings:create", args=[site.slug]), _post_data(category))

    posting = Posting.objects.get(site=site)
    assert posting.status == Posting.Status.PENDING
    assert posting.submitted_at is not None
    assert response.status_code == 302
    assert response.url.startswith(f"/{site.slug}/postings/{posting.public_id}/submitted/")


def test_create_rejects_missing_price_when_required(client):
    site = make_site()
    category = make_category(price_policy=Category.PricePolicy.REQUIRED)

    response = client.post(reverse("postings:create", args=[site.slug]), _post_data(category))

    assert response.status_code == 200
    assert "requires a price" in response.content.decode()
    assert not Posting.objects.filter(site=site).exists()


def test_create_rejects_price_when_forbidden(client):
    site = make_site()
    category = make_category(price_policy=Category.PricePolicy.FORBIDDEN)

    response = client.post(
        reverse("postings:create", args=[site.slug]), _post_data(category, price="5.00")
    )

    assert response.status_code == 200
    assert "forbids a price" in response.content.decode()
    assert not Posting.objects.filter(site=site).exists()


def test_create_rejects_missing_area_when_site_has_areas(client):
    site = make_site()
    make_area(site=site)
    category = make_category()

    response = client.post(reverse("postings:create", args=[site.slug]), _post_data(category))

    assert response.status_code == 200
    assert not Posting.objects.filter(site=site).exists()


def test_create_form_preserves_entered_values_on_error(client):
    site = make_site()
    category = make_category(price_policy=Category.PricePolicy.REQUIRED)

    response = client.post(
        reverse("postings:create", args=[site.slug]),
        _post_data(category, title="My unique title"),
    )

    assert "My unique title" in response.content.decode()


def test_price_field_partial_marks_required_for_required_policy(client):
    site = make_site()
    category = make_category(price_policy=Category.PricePolicy.REQUIRED)

    response = client.get(
        reverse("postings:price_field", args=[site.slug]), {"category": category.pk}
    )

    assert "required" in response.content.decode()


def test_price_field_partial_hides_for_forbidden_policy(client):
    site = make_site()
    category = make_category(price_policy=Category.PricePolicy.FORBIDDEN)

    response = client.get(
        reverse("postings:price_field", args=[site.slug]), {"category": category.pk}
    )

    assert 'type="hidden"' in response.content.decode()


def test_submitted_page_shows_confirm_link_for_valid_token(client):
    site = make_site()
    posting = make_posting(site=site, status=Posting.Status.PENDING, token="right-token")

    response = client.get(
        reverse("postings:submitted", args=[site.slug, posting.public_id, "right-token"])
    )

    assert response.status_code == 200
    assert "Confirm now" in response.content.decode()


def test_submitted_page_404s_for_wrong_token(client):
    site = make_site()
    posting = make_posting(site=site, status=Posting.Status.PENDING, token="right-token")

    response = client.get(
        reverse("postings:submitted", args=[site.slug, posting.public_id, "wrong-token"])
    )

    assert response.status_code == 404


def test_confirm_activates_pending_posting_within_window(client):
    site = make_site()
    posting = make_posting(
        site=site,
        status=Posting.Status.PENDING,
        token="right-token",
        submitted_at=timezone.now() - timedelta(hours=1),
    )

    response = client.get(
        reverse("postings:confirm", args=[site.slug, posting.public_id, "right-token"])
    )

    posting.refresh_from_db()
    assert posting.status == Posting.Status.ACTIVE
    assert response.status_code == 302


def test_confirm_shows_error_past_confirmation_window(client):
    site = make_site()
    posting = make_posting(
        site=site,
        status=Posting.Status.PENDING,
        token="right-token",
        submitted_at=timezone.now() - timedelta(hours=73),
    )

    response = client.get(
        reverse("postings:confirm", args=[site.slug, posting.public_id, "right-token"])
    )

    posting.refresh_from_db()
    assert posting.status == Posting.Status.PENDING
    assert response.status_code == 200
    assert "Couldn" in response.content.decode()


def test_confirm_shows_error_for_already_active_posting(client):
    site = make_site()
    posting = make_posting(site=site, status=Posting.Status.ACTIVE, token="right-token")

    response = client.get(
        reverse("postings:confirm", args=[site.slug, posting.public_id, "right-token"])
    )

    assert response.status_code == 200
    assert "Couldn" in response.content.decode()
