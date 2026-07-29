from django.db import models


class Channel(models.Model):
    """A top-level grouping, e.g. for sale, housing, jobs, services, community."""

    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=100)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "name"]

    def __str__(self) -> str:
        return self.name


class Category(models.Model):
    """A leaf under a Channel, identified by a short code, e.g. `cto`."""

    class PricePolicy(models.TextChoices):
        REQUIRED = "required", "Required"
        OPTIONAL = "optional", "Optional"
        FORBIDDEN = "forbidden", "Forbidden"

    channel = models.ForeignKey(Channel, on_delete=models.PROTECT, related_name="categories")
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="children",
    )
    code = models.CharField(max_length=10)
    slug = models.SlugField()
    name = models.CharField(max_length=100)
    sort_order = models.PositiveIntegerField(default=0)
    lifetime_days = models.PositiveIntegerField()
    price_policy = models.CharField(max_length=10, choices=PricePolicy.choices)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = [("channel", "code"), ("channel", "slug")]
        ordering = ["sort_order", "name"]
        verbose_name_plural = "categories"

    def __str__(self) -> str:
        return f"{self.channel.slug}/{self.code}"

    @property
    def is_leaf(self) -> bool:
        return not self.children.exists()
