import itertools
from datetime import timedelta

from django.contrib.auth.hashers import make_password
from django.utils import timezone

from apps.geo.models import Area, Site
from apps.postings.models import Posting
from apps.taxonomy.models import Category, Channel

_counter = itertools.count(1)


def _next(prefix: str) -> str:
    return f"{prefix}{next(_counter)}"


def make_site(**overrides) -> Site:
    n = _next("site")
    defaults = {
        "slug": n,
        "name": n,
        "hostname": f"{n}.example.com",
        "timezone": "UTC",
        "latitude": 0,
        "longitude": 0,
        "is_active": True,
    }
    defaults.update(overrides)
    return Site.objects.create(**defaults)


def make_area(**overrides) -> Area:
    n = _next("area")
    site = overrides.pop("site", None) or make_site()
    defaults = {
        "site": site,
        "slug": n,
        "name": n,
        "sort_order": 0,
    }
    defaults.update(overrides)
    return Area.objects.create(**defaults)


def make_channel(**overrides) -> Channel:
    n = _next("channel")
    defaults = {"slug": n, "name": n, "sort_order": 0}
    defaults.update(overrides)
    return Channel.objects.create(**defaults)


def make_category(**overrides) -> Category:
    n = _next("category")
    channel = overrides.pop("channel", None) or make_channel()
    defaults = {
        "channel": channel,
        "parent": None,
        "code": _next("c"),
        "slug": n,
        "name": n,
        "sort_order": 0,
        "lifetime_days": 30,
        "price_policy": Category.PricePolicy.OPTIONAL,
        "is_active": True,
    }
    defaults.update(overrides)
    return Category.objects.create(**defaults)


def make_posting(
    status: str = Posting.Status.ACTIVE, token: str = "test-token", **overrides
) -> Posting:
    """Sets fields directly for the requested status rather than replaying transitions,
    so each service function can be tested in isolation from a known starting state."""
    n = _next("posting")
    site = overrides.pop("site", None) or make_site()
    category = overrides.pop("category", None) or make_category()
    now = timezone.now()

    defaults = {
        "site": site,
        "area": None,
        "category": category,
        "title": n,
        "body": f"body for {n}",
        "price": None,
        "contact_email": f"{n}@example.com",
        "contact_name": "Test Poster",
        "contact_phone": "",
        "show_phone": False,
        "location_text": "",
        "latitude": None,
        "longitude": None,
        "status": status,
        "manage_token_hash": make_password(token),
        "submitted_at": None,
        "published_at": None,
        "expires_at": None,
        "last_renewed_at": None,
        "removed_at": None,
        "reposted_from": None,
    }

    if status == Posting.Status.PENDING:
        defaults["submitted_at"] = now - timedelta(hours=1)
    elif status == Posting.Status.ACTIVE:
        defaults["submitted_at"] = now - timedelta(hours=2)
        defaults["published_at"] = now - timedelta(hours=1)
        defaults["expires_at"] = now + timedelta(days=category.lifetime_days)
    elif status == Posting.Status.EXPIRED:
        defaults["submitted_at"] = now - timedelta(days=40)
        defaults["published_at"] = now - timedelta(days=35)
        defaults["expires_at"] = now - timedelta(days=5)
    elif status == Posting.Status.DELETED:
        defaults["submitted_at"] = now - timedelta(days=10)
        defaults["published_at"] = now - timedelta(days=9)
        defaults["expires_at"] = now + timedelta(days=20)
        defaults["removed_at"] = now - timedelta(days=1)
    elif status in (Posting.Status.HIDDEN, Posting.Status.BLOCKED):
        defaults["submitted_at"] = now - timedelta(days=5)
        defaults["published_at"] = now - timedelta(days=4)
        defaults["expires_at"] = now + timedelta(days=25)
        defaults["removed_at"] = now - timedelta(hours=1)
    # DRAFT needs nothing beyond the defaults above.

    defaults.update(overrides)
    return Posting.objects.create(**defaults)
