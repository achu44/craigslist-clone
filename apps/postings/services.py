import secrets
from datetime import timedelta

from django.contrib.auth.hashers import check_password, make_password
from django.utils import timezone

from apps.taxonomy.models import Category

from .exceptions import (
    AreaRequired,
    ConfirmationExpired,
    ImageLimitExceeded,
    InvalidCategoryAssignment,
    InvalidPriceForPolicy,
    InvalidTransition,
    RenewalTooSoon,
    RenewalWindowExpired,
)
from .models import Posting, PostingImage

CONFIRMATION_WINDOW = timedelta(hours=72)
RENEWAL_MIN_INTERVAL = timedelta(hours=48)
RENEWAL_GRACE_PERIOD = timedelta(days=7)
MAX_POSTING_IMAGES = 24


def generate_manage_token() -> tuple[str, str]:
    """Return (plaintext, hash). The plaintext is returned exactly once by the caller."""
    token = secrets.token_urlsafe(32)
    return token, make_password(token)


def get_posting_for_management(public_id, token: str) -> Posting:
    """Look up a posting by manage token. Raises Posting.DoesNotExist for either a bad
    public_id or a bad token, so callers 404 identically in both cases (spec 001 §5.4)."""
    posting = Posting.objects.get(public_id=public_id)
    if not check_password(token, posting.manage_token_hash):
        raise Posting.DoesNotExist(f"No posting matches public_id={public_id} and this token.")
    return posting


def create_posting(
    *,
    site,
    category: Category,
    title: str,
    body: str,
    contact_email: str,
    area=None,
    price=None,
    contact_name: str = "",
    contact_phone: str = "",
    show_phone: bool = False,
    location_text: str = "",
    latitude=None,
    longitude=None,
) -> tuple[Posting, str]:
    if not category.is_leaf:
        raise InvalidCategoryAssignment("Postings may only attach to leaf categories.")
    if category.price_policy == Category.PricePolicy.REQUIRED and price is None:
        raise InvalidPriceForPolicy(f"Category {category} requires a price.")
    if category.price_policy == Category.PricePolicy.FORBIDDEN and price is not None:
        raise InvalidPriceForPolicy(f"Category {category} forbids a price.")
    if area is None and site.areas.exists():
        raise AreaRequired(f"Site {site} has areas; one must be selected.")

    token, token_hash = generate_manage_token()
    posting = Posting.objects.create(
        site=site,
        area=area,
        category=category,
        title=title,
        body=body,
        price=price,
        contact_email=contact_email,
        contact_name=contact_name,
        contact_phone=contact_phone,
        show_phone=show_phone,
        location_text=location_text,
        latitude=latitude,
        longitude=longitude,
        status=Posting.Status.DRAFT,
        manage_token_hash=token_hash,
    )
    return posting, token


def submit_posting(posting: Posting) -> None:
    if posting.status != Posting.Status.DRAFT:
        raise InvalidTransition(f"Cannot submit a posting in status {posting.status}.")
    posting.status = Posting.Status.PENDING
    posting.submitted_at = timezone.now()
    posting.save(update_fields=["status", "submitted_at", "updated_at"])


def confirm_posting(posting: Posting) -> None:
    if posting.status != Posting.Status.PENDING:
        raise InvalidTransition(f"Cannot confirm a posting in status {posting.status}.")
    if timezone.now() > posting.submitted_at + CONFIRMATION_WINDOW:
        raise ConfirmationExpired(
            "Confirmation window has passed; the posting cannot be confirmed."
        )

    now = timezone.now()
    posting.status = Posting.Status.ACTIVE
    posting.published_at = now
    posting.expires_at = now + timedelta(days=posting.category.lifetime_days)
    posting.save(update_fields=["status", "published_at", "expires_at", "updated_at"])


def renew_posting(posting: Posting) -> None:
    if posting.status not in (Posting.Status.ACTIVE, Posting.Status.EXPIRED):
        raise InvalidTransition(f"Cannot renew a posting in status {posting.status}.")

    now = timezone.now()
    anchor = posting.last_renewed_at or posting.published_at
    if anchor is not None and now - anchor < RENEWAL_MIN_INTERVAL:
        raise RenewalTooSoon("Renewal was attempted too soon after publish or last renewal.")
    if posting.expires_at is not None and now - posting.expires_at > RENEWAL_GRACE_PERIOD:
        raise RenewalWindowExpired("Renewal window has passed; repost instead.")

    posting.expires_at = now + timedelta(days=posting.category.lifetime_days)
    posting.last_renewed_at = now
    if posting.status == Posting.Status.EXPIRED:
        # Reviving the posting is the point of renewal — leaving it EXPIRED with a
        # future expires_at would keep it out of the visible queryset forever.
        posting.status = Posting.Status.ACTIVE
    posting.save(update_fields=["status", "expires_at", "last_renewed_at", "updated_at"])


def delete_posting(posting: Posting) -> None:
    deletable = (
        Posting.Status.DRAFT,
        Posting.Status.PENDING,
        Posting.Status.ACTIVE,
        Posting.Status.EXPIRED,
    )
    if posting.status not in deletable:
        raise InvalidTransition(f"Cannot delete a posting in status {posting.status}.")
    posting.status = Posting.Status.DELETED
    posting.removed_at = timezone.now()
    posting.save(update_fields=["status", "removed_at", "updated_at"])


def expire_active_postings() -> int:
    """Bulk-transition every ACTIVE posting past its expiry to EXPIRED. Returns the count."""
    return Posting.objects.filter(
        status=Posting.Status.ACTIVE, expires_at__lte=timezone.now()
    ).update(status=Posting.Status.EXPIRED)


def hide_posting(posting: Posting) -> None:
    if posting.status != Posting.Status.ACTIVE:
        raise InvalidTransition(f"Cannot hide a posting in status {posting.status}.")
    posting.status = Posting.Status.HIDDEN
    posting.removed_at = timezone.now()
    posting.save(update_fields=["status", "removed_at", "updated_at"])


def block_posting(posting: Posting) -> None:
    """No caller is wired up yet in this feature — the operator-triggered entry point
    (admin action or moderation UI) is deferred to the moderation feature."""
    if posting.status == Posting.Status.DELETED:
        raise InvalidTransition(f"Cannot block a posting in status {posting.status}.")
    posting.status = Posting.Status.BLOCKED
    posting.removed_at = timezone.now()
    posting.save(update_fields=["status", "removed_at", "updated_at"])


def repost_posting(source: Posting, token: str) -> tuple[Posting, str]:
    if not check_password(token, source.manage_token_hash):
        raise Posting.DoesNotExist("Manage token does not match the source posting.")
    if source.status == Posting.Status.BLOCKED:
        raise InvalidTransition("Cannot repost a posting removed by an operator.")

    new_token, new_hash = generate_manage_token()
    new_posting = Posting.objects.create(
        site=source.site,
        area=source.area,
        category=source.category,
        title=source.title,
        body=source.body,
        price=source.price,
        contact_email=source.contact_email,
        contact_name=source.contact_name,
        contact_phone=source.contact_phone,
        show_phone=source.show_phone,
        location_text=source.location_text,
        latitude=source.latitude,
        longitude=source.longitude,
        status=Posting.Status.DRAFT,
        manage_token_hash=new_hash,
        reposted_from=source,
    )
    return new_posting, new_token


def add_posting_image(posting: Posting, image) -> PostingImage:
    existing_count = posting.images.count()
    if existing_count >= MAX_POSTING_IMAGES:
        raise ImageLimitExceeded(f"Posting already has the maximum of {MAX_POSTING_IMAGES} images.")
    return PostingImage.objects.create(posting=posting, image=image, sort_order=existing_count)
