# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

from django.contrib.auth.models import Group, Permission, User
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Set up the Rate Manager group and manage user membership"

    def add_arguments(self, parser):
        parser.add_argument(
            "--create-group",
            action="store_true",
            help="Create the Rate Manager group with the can_manage_rates permission",
        )
        parser.add_argument(
            "--add-user",
            type=str,
            help="Username to add to Rate Manager group",
        )
        parser.add_argument(
            "--remove-user",
            type=str,
            help="Username to remove from Rate Manager group",
        )
        parser.add_argument(
            "--list",
            action="store_true",
            help="List all users in the Rate Manager group",
        )

    def handle(self, *args, **options):
        # Check if any action was specified
        if not any(
            [
                options["create_group"],
                options["add_user"],
                options["remove_user"],
                options["list"],
            ]
        ):
            self.stdout.write(
                self.style.WARNING(
                    "No action specified. Use --help for available options."
                )
            )
            return

        if options["create_group"]:
            self._create_group()

        if options["add_user"]:
            self._add_user(options["add_user"])

        if options["remove_user"]:
            self._remove_user(options["remove_user"])

        if options["list"]:
            self._list_users()

    def _get_permission(self):
        """Get the can_manage_rates permission."""
        try:
            return Permission.objects.get(codename="can_manage_rates")
        except Permission.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(
                    "Permission 'can_manage_rates' not found. "
                    "Make sure migrations have been run."
                )
            )
            return None

    def _create_group(self):
        """Create the Rate Manager group with permissions."""
        perm = self._get_permission()
        if not perm:
            return

        group, created = Group.objects.get_or_create(name="Rate Manager")
        group.permissions.add(perm)

        if created:
            self.stdout.write(
                self.style.SUCCESS(
                    "Created 'Rate Manager' group with can_manage_rates permission"
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    "'Rate Manager' group already exists; ensured permission is assigned"
                )
            )

    def _add_user(self, username):
        """Add a user to the Rate Manager group."""
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"User not found: {username}"))
            return

        try:
            group = Group.objects.get(name="Rate Manager")
        except Group.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(
                    "Rate Manager group not found. Run with --create-group first."
                )
            )
            return

        if group in user.groups.all():
            self.stdout.write(
                self.style.WARNING(f"User '{username}' is already a Rate Manager")
            )
        else:
            user.groups.add(group)
            self.stdout.write(
                self.style.SUCCESS(f"Added '{username}' to Rate Manager group")
            )

    def _remove_user(self, username):
        """Remove a user from the Rate Manager group."""
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"User not found: {username}"))
            return

        try:
            group = Group.objects.get(name="Rate Manager")
        except Group.DoesNotExist:
            self.stdout.write(self.style.ERROR("Rate Manager group not found."))
            return

        if group not in user.groups.all():
            self.stdout.write(
                self.style.WARNING(f"User '{username}' is not a Rate Manager")
            )
        else:
            user.groups.remove(group)
            self.stdout.write(
                self.style.SUCCESS(f"Removed '{username}' from Rate Manager group")
            )

    def _list_users(self):
        """List all users in the Rate Manager group."""
        try:
            group = Group.objects.get(name="Rate Manager")
        except Group.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(
                    "Rate Manager group not found. Run with --create-group first."
                )
            )
            return

        users = group.user_set.all().order_by("username")
        if users:
            self.stdout.write(self.style.SUCCESS("Rate Manager members:"))
            for user in users:
                name = f"{user.first_name} {user.last_name}".strip() or "(no name)"
                self.stdout.write(f"  - {user.username} ({user.email}) - {name}")
        else:
            self.stdout.write(
                self.style.WARNING("No users in Rate Manager group")
            )

