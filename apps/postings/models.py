import uuid

from django.db import models
from django.db.models import Q


class PostingQuerySet(models.QuerySet):
    def visible(self):
        """The single canonical queryset of publicly visible postings (spec 001 §5.1)."""
        return self.filter(status=Posting.Status.ACTIVE)


class Posting(models.Model):
    """The central entity: a single classified ad."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PENDING = "pending", "Pending"
        ACTIVE = "active", "Active"
        EXPIRED = "expired", "Expired"
        DELETED = "deleted", "Deleted"
        HIDDEN = "hidden", "Hidden"
        BLOCKED = "blocked", "Blocked"

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    site = models.ForeignKey("geo.Site", on_delete=models.PROTECT, related_name="postings")
    area = models.ForeignKey(
        "geo.Area",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="postings",
    )
    category = models.ForeignKey(
        "taxonomy.Category", on_delete=models.PROTECT, related_name="postings"
    )

    title = models.CharField(max_length=200)
    body = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    contact_email = models.EmailField()
    contact_name = models.CharField(max_length=100, blank=True)
    contact_phone = models.CharField(max_length=32, blank=True)
    show_phone = models.BooleanField(default=False)

    location_text = models.CharField(max_length=200, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    manage_token_hash = models.CharField(max_length=128)

    created_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    last_renewed_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    removed_at = models.DateTimeField(null=True, blank=True)

    reposted_from = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reposts",
    )

    objects = PostingQuerySet.as_manager()

    class Meta:
        indexes = [
            models.Index(
                fields=["site", "category", "status", "published_at"],
                name="posting_visibility_idx",
            ),
            models.Index(fields=["status", "expires_at"], name="posting_expiry_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(price__isnull=True) | Q(price__gte=0),
                name="posting_price_nonnegative",
            ),
        ]

    def __str__(self) -> str:
        return self.title


class PostingImage(models.Model):
    posting = models.ForeignKey(Posting, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="postings/%Y/%m/")
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sort_order", "id"]

    def __str__(self) -> str:
        return f"image {self.sort_order} for {self.posting_id}"
