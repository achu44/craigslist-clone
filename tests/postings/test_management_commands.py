from datetime import timedelta

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.postings.models import Posting
from tests.factories import make_posting

pytestmark = pytest.mark.django_db


def test_expire_postings_command_transitions_past_due_postings():
    past_due = make_posting(
        status=Posting.Status.ACTIVE, expires_at=timezone.now() - timedelta(hours=1)
    )

    call_command("expire_postings")

    past_due.refresh_from_db()
    assert past_due.status == Posting.Status.EXPIRED
