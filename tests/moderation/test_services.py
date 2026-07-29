import pytest

from apps.moderation.models import Flag
from apps.moderation.services import flag_posting
from apps.postings.models import Posting
from tests.factories import make_posting

pytestmark = pytest.mark.django_db


def test_flag_posting_records_a_flag():
    posting = make_posting(status=Posting.Status.ACTIVE)
    flag_posting(posting, reason="spam", reporter_fingerprint="fp-1")
    assert Flag.objects.filter(posting=posting).count() == 1


def test_flag_posting_same_fingerprint_counts_once(settings):
    settings.FLAG_HIDE_THRESHOLD = 2
    posting = make_posting(status=Posting.Status.ACTIVE)

    flag_posting(posting, reason="spam", reporter_fingerprint="fp-1")
    flag_posting(posting, reason="spam", reporter_fingerprint="fp-1")

    assert Flag.objects.filter(posting=posting).count() == 1
    posting.refresh_from_db()
    assert posting.status == Posting.Status.ACTIVE


def test_flag_posting_hides_at_threshold(settings):
    settings.FLAG_HIDE_THRESHOLD = 2
    posting = make_posting(status=Posting.Status.ACTIVE)

    flag_posting(posting, reason="spam", reporter_fingerprint="fp-1")
    flag_posting(posting, reason="spam", reporter_fingerprint="fp-2")

    posting.refresh_from_db()
    assert posting.status == Posting.Status.HIDDEN
    assert posting.removed_at is not None


def test_flag_posting_below_threshold_stays_active(settings):
    settings.FLAG_HIDE_THRESHOLD = 5
    posting = make_posting(status=Posting.Status.ACTIVE)

    flag_posting(posting, reason="spam", reporter_fingerprint="fp-1")

    posting.refresh_from_db()
    assert posting.status == Posting.Status.ACTIVE
