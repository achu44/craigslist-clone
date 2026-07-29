from django.db import models


class Site(models.Model):
    """A geographic region with its own subdomain, e.g. `houston`."""

    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=100)
    hostname = models.CharField(max_length=255, unique=True)
    timezone = models.CharField(max_length=64)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    is_active = models.BooleanField(default=True)

    def __str__(self) -> str:
        return self.name


class Area(models.Model):
    """A subdivision within a Site, e.g. `katy` within `houston`."""

    site = models.ForeignKey(Site, on_delete=models.PROTECT, related_name="areas")
    slug = models.SlugField()
    name = models.CharField(max_length=100)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = [("site", "slug")]
        ordering = ["sort_order", "name"]

    def __str__(self) -> str:
        return f"{self.site.slug}/{self.slug}"
