from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

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


def test_browse_search_narrows_results(client):
    site = make_site()
    make_posting(site=site, status=Posting.Status.ACTIVE, title="Blue velvet couch")
    make_posting(site=site, status=Posting.Status.ACTIVE, title="Mountain bicycle")

    response = client.get(reverse("postings:browse", args=[site.slug]), {"q": "couch"})

    body = response.content.decode()
    assert response.status_code == 200
    assert "Blue velvet couch" in body
    assert "Mountain bicycle" not in body


def test_browse_search_and_category_filter_apply_together(client):
    site = make_site()
    wanted = make_category()
    other = make_category()
    make_posting(site=site, category=wanted, title="Wanted couch")
    make_posting(site=site, category=other, title="Other couch")
    make_posting(site=site, category=wanted, title="Wanted bicycle")

    response = client.get(
        reverse("postings:browse", args=[site.slug]),
        {"q": "couch", "category": wanted.slug},
    )

    body = response.content.decode()
    assert "Wanted couch" in body
    assert "Other couch" not in body
    assert "Wanted bicycle" not in body


@pytest.mark.parametrize("params", [{}, {"q": ""}, {"q": "   "}])
def test_browse_without_a_search_term_keeps_spec_002_ordering(client, params):
    site = make_site()
    now = timezone.now()
    make_posting(site=site, title="Older posting", published_at=now - timedelta(days=2))
    make_posting(site=site, title="Newer posting", published_at=now - timedelta(days=1))

    body = client.get(reverse("postings:browse", args=[site.slug]), params).content.decode()

    assert body.index("Newer posting") < body.index("Older posting")


def test_browse_echoes_the_submitted_term_into_the_search_input(client):
    site = make_site()

    response = client.get(reverse("postings:browse", args=[site.slug]), {"q": "velvet couch"})

    assert 'name="q" id="q" value="velvet couch"' in response.content.decode()


def test_browse_no_match_message_names_the_term(client):
    site = make_site()
    make_posting(site=site, title="Mountain bicycle")

    response = client.get(reverse("postings:browse", args=[site.slug]), {"q": "couch"})

    assert 'No postings match "couch".' in response.content.decode()


def test_browse_without_a_term_shows_the_plain_empty_message(client):
    site = make_site()

    body = client.get(reverse("postings:browse", args=[site.slug])).content.decode()

    assert "No postings yet." in body


def test_browse_search_keeps_the_selected_category_on_the_next_request(client):
    site = make_site()
    wanted = make_category()
    make_posting(site=site, category=wanted, title="Wanted couch")

    response = client.get(
        reverse("postings:browse", args=[site.slug]),
        {"q": "couch", "category": wanted.slug},
    )

    body = response.content.decode()
    # Both controls live in one form, so a follow-up submit carries both parameters.
    assert 'name="q" id="q" value="couch"' in body
    assert f'value="{wanted.slug}" selected' in body


def test_browse_search_does_not_500_on_full_text_operators(client):
    site = make_site()
    make_posting(site=site, title="Oak desk")

    response = client.get(
        reverse("postings:browse", args=[site.slug]), {"q": "desk & chair | !sofa"}
    )

    assert response.status_code == 200


def test_browse_search_truncates_an_over_long_term(client):
    site = make_site()
    make_posting(site=site, title="Oak desk")

    response = client.get(reverse("postings:browse", args=[site.slug]), {"q": "a" * 500})

    assert response.status_code == 200
    assert response.context["term"] == "a" * 200


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
