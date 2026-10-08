from django.core.management.base import BaseCommand
from django.db import transaction
from permissions.constants import PERMISSION_DESCRIPTIONS, ROLE_PERMISSIONS
from permissions.models import Permission, RolePermission


class Command(BaseCommand):
    help = "Create all permissions and give every role its starting permissions (safe to run many times)."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Delete every role->permission link first and start again from constants.py")

    @transaction.atomic
    def handle(self, *args, **options):
        if options["reset"]:
            RolePermission.objects.all().delete()
            self.stdout.write(self.style.WARNING("All role permissions were deleted."))

        for name, description in PERMISSION_DESCRIPTIONS.items():
            Permission.objects.update_or_create(name=name, defaults={"description": description})

        created = 0
        for role, names in ROLE_PERMISSIONS.items():
            for permission in Permission.objects.filter(name__in=names):
                _, was_created = RolePermission.objects.get_or_create(role=role, permission=permission)
                created += was_created

        self.stdout.write(self.style.SUCCESS(f"{Permission.objects.count()} permissions, {created} new role permissions created."))


# This file reduces developer's workload of adding permissions in the Django Admin's PERMISSIONS Tab one by one.
# After creating the permissions app and the models for it, run the command below and that is what creates the permissions in Django Admin's PERMISSIONS.