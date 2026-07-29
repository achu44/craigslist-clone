from django.core.management.base import BaseCommand

from apps.geo.models import Site
from apps.taxonomy.models import Category, Channel


class Command(BaseCommand):
    help = "Create a small set of dev-only Site/Channel/Category rows for local use."

    def handle(self, *args, **options):
        site, _ = Site.objects.get_or_create(
            slug="dev",
            defaults={
                "name": "Dev Site",
                "hostname": "dev.localhost",
                "timezone": "UTC",
                "latitude": 0,
                "longitude": 0,
            },
        )
        channel, _ = Channel.objects.get_or_create(slug="for-sale", defaults={"name": "For Sale"})
        Category.objects.get_or_create(
            channel=channel,
            code="gen",
            defaults={
                "slug": "general",
                "name": "General",
                "lifetime_days": 30,
                "price_policy": Category.PricePolicy.OPTIONAL,
            },
        )
        Category.objects.get_or_create(
            channel=channel,
            code="fre",
            defaults={
                "slug": "free",
                "name": "Free Stuff",
                "lifetime_days": 7,
                "price_policy": Category.PricePolicy.FORBIDDEN,
            },
        )
        self.stdout.write(self.style.SUCCESS(f'Seeded site "{site.slug}".'))
