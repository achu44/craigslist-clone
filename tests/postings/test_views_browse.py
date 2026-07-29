import pytest
from django.urls import reverse

from apps.postings.models import Posting
from tests.factories import make_category, make_posting, make_site

pytestmark = pytest.mark.django_db


def test_browse_returns_404_for_unknown_site(client):
    response = client.get(reverse("postings:browse", args=["nope"]))
    assert response.status_code == 404


def test_browse_shows_active_posting(client):
    site = make_site()
    make_posting(site=site, status=Posting.Status.ACTIVE, title="Couch for sale")

    response = client.get(reverse("postings:browse", args=[site.slug]))

    assert response.status_code == 200
    assert "Couch for sale" in response.content.decode()


@pytest.mark.parametrize(
    "status",
    [
        Posting.Status.DRAFT,
        Posting.Status.PENDING,
        Posting.Status.EXPIRED,
        Posting.Status.DELETED,
        Posting.Status.HIDDEN,
        Posting.Status.BLOCKED,
    ],
)
def test_browse_hides_non_active_postings(client, status):
    site = make_site()
    make_posting(site=site, status=status, title="Hidden thing")

    response = client.get(reverse("postings:browse", args=[site.slug]))

    assert "Hidden thing" not in response.content.decode()


def test_browse_category_filter_narrows_results(client):
    site = make_site()
    wanted = make_category()
    other = make_category()
    make_posting(site=site, status=Posting.Status.ACTIVE, category=wanted, title="Wanted item")
    make_posting(site=site, status=Posting.Status.ACTIVE, category=other, title="Other item")

    response = client.get(reverse("postings:browse", args=[site.slug]), {"category": wanted.slug})

    body = response.content.decode()
    assert "Wanted item" in body
    assert "Other item" not in body


def test_detail_returns_404_for_unknown_site(client):
    import uuid

    response = client.get(reverse("postings:detail", args=["nope", uuid.uuid4()]))
    assert response.status_code == 404


def test_detail_shows_active_posting(client):
    site = make_site()
    posting = make_posting(site=site, status=Posting.Status.ACTIVE, title="A great couch")

    response = client.get(reverse("postings:detail", args=[site.slug, posting.public_id]))

    assert response.status_code == 200
    assert "A great couch" in response.content.decode()


@pytest.mark.parametrize(
    "status",
    [
        Posting.Status.DRAFT,
        Posting.Status.PENDING,
        Posting.Status.EXPIRED,
        Posting.Status.DELETED,
        Posting.Status.HIDDEN,
        Posting.Status.BLOCKED,
    ],
)
def test_detail_404s_for_non_active_postings(client, status):
    site = make_site()
    posting = make_posting(site=site, status=status)

    response = client.get(reverse("postings:detail", args=[site.slug, posting.public_id]))

    assert response.status_code == 404
