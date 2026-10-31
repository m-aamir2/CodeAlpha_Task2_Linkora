from django.core.management.base import BaseCommand
from social.services import cleanup_expired_stories


class Command(BaseCommand):
    help = "Delete expired stories and their media files."

    def handle(self, *args, **options):
        deleted = cleanup_expired_stories()
        self.stdout.write(self.style.SUCCESS(f"Deleted {deleted} expired stories."))
