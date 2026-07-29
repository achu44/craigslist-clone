from django.conf import settings

from apps.postings.models import Posting
from apps.postings.services import hide_posting

from .models import Flag


def flag_posting(posting: Posting, reason: str, reporter_fingerprint: str) -> None:
    """Record a flag and hide the posting once the global threshold is reached.

    get_or_create, not create, so a repeat fingerprint on the same posting counts once
    (spec 001 §5.4) rather than raising IntegrityError on the unique_together constraint.
    """
    Flag.objects.get_or_create(
        posting=posting,
        reporter_fingerprint=reporter_fingerprint,
        defaults={"reason": reason},
    )

    flag_count = posting.flags.count()
    if flag_count >= settings.FLAG_HIDE_THRESHOLD and posting.status == Posting.Status.ACTIVE:
        hide_posting(posting)
