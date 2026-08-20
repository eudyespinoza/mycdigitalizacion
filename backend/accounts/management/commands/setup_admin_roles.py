from django.core.management.base import BaseCommand

from config.admin_roles import sync_admin_roles


class Command(BaseCommand):
    help = "Synchronize exact least-privilege Django Admin role permissions."

    def handle(self, *args, **options):
        del args, options
        counts = sync_admin_roles()
        summary = ", ".join(f"{role}={count}" for role, count in counts.items())
        self.stdout.write(self.style.SUCCESS(f"Admin roles synchronized: {summary}"))
