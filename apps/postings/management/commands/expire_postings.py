from django.core.management.base import BaseCommand

from apps.postings.services import expire_active_postings


class Command(BaseCommand):
    help = "Transition every ACTIVE posting past its expiry date to EXPIRED."

    def handle(self, *args, **options):
        count = expire_active_postings()
        self.stdout.write(self.style.SUCCESS(f"Expired {count} posting(s)."))
