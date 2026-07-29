from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction

from apps.postings.models import Posting
from tests.factories import make_posting

pytestmark = pytest.mark.django_db


def test_negative_price_rejected_by_db_constraint():
    posting = make_posting(status=Posting.Status.DRAFT, price=None)
    posting.price = Decimal("-1.00")
    with pytest.raises(IntegrityError), transaction.atomic():
        posting.save(update_fields=["price"])


def test_null_price_is_allowed():
    posting = make_posting(status=Posting.Status.DRAFT, price=None)
    posting.full_clean(exclude=["manage_token_hash"])


def test_visibility_and_expiry_indexes_are_declared():
    index_names = {index.name for index in Posting._meta.indexes}
    assert "posting_visibility_idx" in index_names
    assert "posting_expiry_idx" in index_names


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
def test_visible_queryset_excludes_non_active_statuses(status):
    make_posting(status=status)
    assert Posting.objects.visible().count() == 0


def test_visible_queryset_includes_only_active():
    active = make_posting(status=Posting.Status.ACTIVE)
    make_posting(status=Posting.Status.EXPIRED)
    assert list(Posting.objects.visible()) == [active]
