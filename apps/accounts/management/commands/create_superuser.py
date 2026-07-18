import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from apps.accounts.models import Roles


class Command(BaseCommand):
    help = (
        "Create the initial admin (superuser) from SUPERUSER_* environment "
        "variables. Idempotent and safe to run on every deploy: it skips when "
        "the variables are unset or a superuser already exists. For interactive "
        "setup, use the standard `createsuperuser` command instead."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Reset the password/flags if the named user already exists.",
        )

    def handle(self, *args, **options):
        User = get_user_model()
        username = os.environ.get("SUPERUSER_USERNAME")
        email = os.environ.get("SUPERUSER_EMAIL", "")
        password = os.environ.get("SUPERUSER_PASSWORD")
        employee_id = os.environ.get("SUPERUSER_EMPLOYEE_ID", "ADMIN-0001")

        if not username or not password:
            self.stdout.write(
                "SUPERUSER_USERNAME or SUPERUSER_PASSWORD not set; "
                "skipping superuser creation."
            )
            return

        existing = User.objects.filter(username=username).first()
        if existing:
            if options["force"]:
                existing.set_password(password)
                existing.is_staff = True
                existing.is_superuser = True
                existing.role = Roles.ADMIN
                existing.save()
                self.stdout.write(
                    self.style.SUCCESS(f"Updated existing superuser '{username}'.")
                )
            else:
                self.stdout.write(
                    f"User '{username}' already exists; skipping "
                    "(use --force to reset the password)."
                )
            return

        if User.objects.filter(is_superuser=True).exists():
            self.stdout.write(
                "A superuser already exists; skipping superuser creation."
            )
            return

        User.objects.create_superuser(
            username=username,
            email=email,
            password=password,
            employee_id=employee_id,
            role=Roles.ADMIN,
        )
        self.stdout.write(self.style.SUCCESS(f"Created superuser '{username}'."))
