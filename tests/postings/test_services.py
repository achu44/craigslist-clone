from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth.hashers import check_password
from django.utils import timezone

from apps.postings.exceptions import (
    AreaRequired,
    ConfirmationExpired,
    ImageLimitExceeded,
    InvalidPriceForPolicy,
    InvalidTransition,
    RenewalTooSoon,
    RenewalWindowExpired,
)
from apps.postings.models import Posting, PostingImage
from apps.postings.services import (
    MAX_POSTING_IMAGES,
    add_posting_image,
    block_posting,
    confirm_posting,
    create_posting,
    delete_posting,
    expire_active_postings,
    generate_manage_token,
    get_posting_for_management,
    hide_posting,
    renew_posting,
    repost_posting,
    submit_posting,
)
from apps.taxonomy.models import Category
from tests.factories import make_area, make_category, make_posting, make_site

pytestmark = pytest.mark.django_db


# --- manage token helpers -------------------------------------------------


def test_generate_manage_token_hash_verifies_plaintext():
    plaintext, token_hash = generate_manage_token()
    assert check_password(plaintext, token_hash)


def test_get_posting_for_management_succeeds_with_correct_token():
    posting = make_posting(status=Posting.Status.ACTIVE, token="right-token")
    found = get_posting_for_management(posting.public_id, "right-token")
    assert found == posting


def test_get_posting_for_management_rejects_wrong_token():
    posting = make_posting(status=Posting.Status.ACTIVE, token="right-token")
    with pytest.raises(Posting.DoesNotExist):
        get_posting_for_management(posting.public_id, "wrong-token")


def test_get_posting_for_management_rejects_unknown_public_id():
    import uuid

    with pytest.raises(Posting.DoesNotExist):
        get_posting_for_management(uuid.uuid4(), "anything")


# --- create_posting --------------------------------------------------------


def test_create_posting_sets_draft_status_and_returns_plaintext_token():
    site = make_site()
    category = make_category()

    posting, token = create_posting(
        site=site, category=category, title="Couch", body="Comfy", contact_email="a@example.com"
    )

    assert posting.status == Posting.Status.DRAFT
    assert check_password(token, posting.manage_token_hash)


def test_create_posting_rejects_missing_price_when_required():
    site = make_site()
    category = make_category(price_policy=Category.PricePolicy.REQUIRED)

    with pytest.raises(InvalidPriceForPolicy):
        create_posting(
            site=site, category=category, title="t", body="b", contact_email="a@example.com"
        )


def test_create_posting_rejects_price_when_forbidden():
    site = make_site()
    category = make_category(price_policy=Category.PricePolicy.FORBIDDEN)

    with pytest.raises(InvalidPriceForPolicy):
        create_posting(
            site=site,
            category=category,
            title="t",
            body="b",
            contact_email="a@example.com",
            price=Decimal("5.00"),
        )


def test_create_posting_rejects_missing_area_when_site_has_areas():
    site = make_site()
    make_area(site=site)
    category = make_category()

    with pytest.raises(AreaRequired):
        create_posting(
            site=site, category=category, title="t", body="b", contact_email="a@example.com"
        )


def test_create_posting_allows_no_area_when_site_has_no_areas():
    site = make_site()
    category = make_category()

    posting, _token = create_posting(
        site=site, category=category, title="t", body="b", contact_email="a@example.com"
    )
    assert posting.area is None


# --- submit_posting ---------------------------------------------------------


def test_submit_posting_transitions_draft_to_pending_and_sets_submitted_at():
    posting = make_posting(status=Posting.Status.DRAFT)
    submit_posting(posting)
    posting.refresh_from_db()
    assert posting.status == Posting.Status.PENDING
    assert posting.submitted_at is not None


@pytest.mark.parametrize(
    "status",
    [
        Posting.Status.PENDING,
        Posting.Status.ACTIVE,
        Posting.Status.EXPIRED,
        Posting.Status.DELETED,
        Posting.Status.HIDDEN,
        Posting.Status.BLOCKED,
    ],
)
def test_submit_posting_rejects_from_non_draft(status):
    posting = make_posting(status=status)
    with pytest.raises(InvalidTransition):
        submit_posting(posting)


# --- confirm_posting ---------------------------------------------------------


def test_confirm_posting_transitions_pending_to_active_and_sets_expiry():
    category = make_category(lifetime_days=10)
    posting = make_posting(status=Posting.Status.PENDING, category=category)
    confirm_posting(posting)
    posting.refresh_from_db()
    assert posting.status == Posting.Status.ACTIVE
    assert posting.published_at is not None
    assert posting.expires_at == posting.published_at + timedelta(days=10)


def test_confirm_posting_rejects_after_confirmation_window():
    posting = make_posting(status=Posting.Status.PENDING)
    posting.submitted_at = timezone.now() - timedelta(hours=73)
    posting.save(update_fields=["submitted_at"])

    with pytest.raises(ConfirmationExpired):
        confirm_posting(posting)


def test_confirm_posting_rejects_from_non_pending():
    posting = make_posting(status=Posting.Status.DRAFT)
    with pytest.raises(InvalidTransition):
        confirm_posting(posting)


# --- renew_posting ------------------------------------------------------------


def test_renew_posting_from_active_extends_expiry_and_sets_last_renewed_at():
    category = make_category(lifetime_days=30)
    posting = make_posting(
        status=Posting.Status.ACTIVE,
        category=category,
        published_at=timezone.now() - timedelta(hours=49),
    )
    renew_posting(posting)
    posting.refresh_from_db()
    assert posting.status == Posting.Status.ACTIVE
    assert posting.last_renewed_at is not None
    assert posting.expires_at > timezone.now() + timedelta(days=29)


def test_renew_posting_from_expired_reactivates_to_active():
    posting = make_posting(
        status=Posting.Status.EXPIRED,
        published_at=timezone.now() - timedelta(days=40),
        expires_at=timezone.now() - timedelta(days=3),
    )
    renew_posting(posting)
    posting.refresh_from_db()
    assert posting.status == Posting.Status.ACTIVE


def test_renew_posting_rejects_too_soon_after_publish():
    posting = make_posting(status=Posting.Status.ACTIVE, published_at=timezone.now())
    with pytest.raises(RenewalTooSoon):
        renew_posting(posting)


def test_renew_posting_rejects_after_grace_period():
    posting = make_posting(
        status=Posting.Status.EXPIRED,
        published_at=timezone.now() - timedelta(days=40),
        expires_at=timezone.now() - timedelta(days=8),
    )
    with pytest.raises(RenewalWindowExpired):
        renew_posting(posting)


def test_renew_posting_rejects_from_draft():
    posting = make_posting(status=Posting.Status.DRAFT)
    with pytest.raises(InvalidTransition):
        renew_posting(posting)


# --- delete_posting ------------------------------------------------------------


def test_delete_posting_from_active_sets_deleted_and_removed_at():
    posting = make_posting(status=Posting.Status.ACTIVE)
    delete_posting(posting)
    posting.refresh_from_db()
    assert posting.status == Posting.Status.DELETED
    assert posting.removed_at is not None


def test_delete_posting_rejects_from_blocked():
    posting = make_posting(status=Posting.Status.BLOCKED)
    with pytest.raises(InvalidTransition):
        delete_posting(posting)


def test_delete_posting_rejects_from_hidden():
    posting = make_posting(status=Posting.Status.HIDDEN)
    with pytest.raises(InvalidTransition):
        delete_posting(posting)


# --- expire_active_postings -----------------------------------------------------


def test_expire_active_postings_only_transitions_past_due():
    past_due = make_posting(
        status=Posting.Status.ACTIVE, expires_at=timezone.now() - timedelta(hours=1)
    )
    not_due = make_posting(
        status=Posting.Status.ACTIVE, expires_at=timezone.now() + timedelta(days=1)
    )

    count = expire_active_postings()

    past_due.refresh_from_db()
    not_due.refresh_from_db()
    assert count == 1
    assert past_due.status == Posting.Status.EXPIRED
    assert not_due.status == Posting.Status.ACTIVE


# --- hide_posting ------------------------------------------------------------


def test_hide_posting_from_active_sets_hidden_and_removed_at():
    posting = make_posting(status=Posting.Status.ACTIVE)
    hide_posting(posting)
    posting.refresh_from_db()
    assert posting.status == Posting.Status.HIDDEN
    assert posting.removed_at is not None


def test_hide_posting_rejects_from_non_active():
    posting = make_posting(status=Posting.Status.DRAFT)
    with pytest.raises(InvalidTransition):
        hide_posting(posting)


# --- block_posting ------------------------------------------------------------


def test_block_posting_from_active_sets_blocked_and_removed_at():
    posting = make_posting(status=Posting.Status.ACTIVE)
    block_posting(posting)
    posting.refresh_from_db()
    assert posting.status == Posting.Status.BLOCKED
    assert posting.removed_at is not None


def test_block_posting_rejects_from_deleted():
    posting = make_posting(status=Posting.Status.DELETED)
    with pytest.raises(InvalidTransition):
        block_posting(posting)


# --- repost_posting ------------------------------------------------------------


def test_repost_posting_creates_new_draft_linked_to_source():
    source = make_posting(status=Posting.Status.EXPIRED, token="source-token")
    reposted, token = repost_posting(source, "source-token")

    assert reposted.status == Posting.Status.DRAFT
    assert reposted.reposted_from == source
    assert reposted.public_id != source.public_id
    assert check_password(token, reposted.manage_token_hash)


def test_repost_posting_rejects_wrong_token():
    source = make_posting(status=Posting.Status.EXPIRED, token="source-token")
    with pytest.raises(Posting.DoesNotExist):
        repost_posting(source, "wrong-token")


def test_repost_posting_rejects_blocked_source():
    source = make_posting(status=Posting.Status.BLOCKED, token="source-token")
    with pytest.raises(InvalidTransition):
        repost_posting(source, "source-token")


# --- add_posting_image ------------------------------------------------------------


def test_add_posting_image_up_to_limit():
    posting = make_posting(status=Posting.Status.DRAFT)
    for _ in range(MAX_POSTING_IMAGES):
        add_posting_image(posting, "placeholder.jpg")
    assert PostingImage.objects.filter(posting=posting).count() == MAX_POSTING_IMAGES


def test_add_posting_image_rejects_beyond_limit():
    posting = make_posting(status=Posting.Status.DRAFT)
    for _ in range(MAX_POSTING_IMAGES):
        add_posting_image(posting, "placeholder.jpg")

    with pytest.raises(ImageLimitExceeded):
        add_posting_image(posting, "placeholder.jpg")
