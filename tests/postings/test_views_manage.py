from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.postings.models import Posting
from tests.factories import make_posting, make_site

pytestmark = pytest.mark.django_db


def _manage_url(name, site, posting, token):
    return reverse(f"postings:{name}", args=[site.slug, posting.public_id, token])


def test_manage_404s_for_wrong_token(client):
    site = make_site()
    posting = make_posting(site=site, status=Posting.Status.ACTIVE, token="right-token")

    response = client.get(_manage_url("manage", site, posting, "wrong-token"))

    assert response.status_code == 404


@pytest.mark.parametrize(
    ("status", "expect_renew", "expect_delete"),
    [
        (Posting.Status.ACTIVE, True, True),
        (Posting.Status.EXPIRED, True, True),
        (Posting.Status.DELETED, False, False),
        (Posting.Status.HIDDEN, False, False),
        (Posting.Status.BLOCKED, False, False),
    ],
)
def test_manage_shows_actions_matching_status(client, status, expect_renew, expect_delete):
    site = make_site()
    posting = make_posting(site=site, status=status, token="right-token")

    response = client.get(_manage_url("manage", site, posting, "right-token"))

    body = response.content.decode()
    assert response.status_code == 200
    assert (">Renew<" in body) is expect_renew
    assert (">Delete<" in body) is expect_delete


def test_manage_delete_transitions_active_posting_to_deleted(client):
    site = make_site()
    posting = make_posting(site=site, status=Posting.Status.ACTIVE, token="right-token")

    response = client.post(_manage_url("manage_delete", site, posting, "right-token"))

    posting.refresh_from_db()
    assert posting.status == Posting.Status.DELETED
    assert response.status_code == 302


def test_manage_delete_rejects_blocked_posting_with_message(client):
    site = make_site()
    posting = make_posting(site=site, status=Posting.Status.BLOCKED, token="right-token")

    response = client.post(_manage_url("manage_delete", site, posting, "right-token"), follow=True)

    posting.refresh_from_db()
    assert posting.status == Posting.Status.BLOCKED
    messages = list(response.context["messages"])
    assert any("Cannot delete" in str(m) for m in messages)


def test_manage_delete_rejects_hidden_posting_with_message(client):
    site = make_site()
    posting = make_posting(site=site, status=Posting.Status.HIDDEN, token="right-token")

    response = client.post(_manage_url("manage_delete", site, posting, "right-token"), follow=True)

    posting.refresh_from_db()
    assert posting.status == Posting.Status.HIDDEN
    messages = list(response.context["messages"])
    assert any("Cannot delete" in str(m) for m in messages)


def test_manage_renew_extends_active_posting(client):
    site = make_site()
    posting = make_posting(
        site=site,
        status=Posting.Status.ACTIVE,
        token="right-token",
        published_at=timezone.now() - timedelta(hours=49),
    )

    response = client.post(_manage_url("manage_renew", site, posting, "right-token"))

    posting.refresh_from_db()
    assert posting.status == Posting.Status.ACTIVE
    assert posting.last_renewed_at is not None
    assert response.status_code == 302


def test_manage_renew_reactivates_expired_posting(client):
    site = make_site()
    posting = make_posting(
        site=site,
        status=Posting.Status.EXPIRED,
        token="right-token",
        published_at=timezone.now() - timedelta(days=40),
        expires_at=timezone.now() - timedelta(days=3),
    )

    client.post(_manage_url("manage_renew", site, posting, "right-token"))

    posting.refresh_from_db()
    assert posting.status == Posting.Status.ACTIVE


def test_manage_renew_rejects_too_soon_with_message(client):
    site = make_site()
    posting = make_posting(
        site=site,
        status=Posting.Status.ACTIVE,
        token="right-token",
        published_at=timezone.now(),
    )

    response = client.post(_manage_url("manage_renew", site, posting, "right-token"), follow=True)

    posting.refresh_from_db()
    assert posting.last_renewed_at is None
    messages = list(response.context["messages"])
    assert any("too soon" in str(m) for m in messages)


def test_manage_renew_rejects_past_grace_period_with_message(client):
    site = make_site()
    posting = make_posting(
        site=site,
        status=Posting.Status.EXPIRED,
        token="right-token",
        published_at=timezone.now() - timedelta(days=40),
        expires_at=timezone.now() - timedelta(days=8),
    )

    response = client.post(_manage_url("manage_renew", site, posting, "right-token"), follow=True)

    posting.refresh_from_db()
    assert posting.status == Posting.Status.EXPIRED
    messages = list(response.context["messages"])
    assert any("repost" in str(m) for m in messages)
