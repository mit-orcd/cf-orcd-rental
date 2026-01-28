# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Django management command to create user accounts.

Creates user accounts with optional API token generation and manager group
assignment. Configuration via environment variables for secrets.

Environment Variables:
    ORCD_EMAIL_DOMAIN: Default email domain (e.g., 'example.edu')
    ORCD_USER_PASSWORD: Default password for new users (optional)

Examples:
    coldfront create_user jsmith
    coldfront create_user jsmith --email jsmith@university.edu --with-token
    coldfront create_user jsmith --with-token --add-to-group rental
    coldfront create_user jsmith --dry-run
"""

import os
import secrets
import string

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User, Group


# Map of group aliases to actual group names
GROUP_MAP = {
    "rental": "Rental Manager",
    "billing": "Billing Manager",
    "rate": "Rate Manager",
}


def generate_random_password(length=16):
    """Generate a secure random password."""
    alphabet = string.ascii_letters + string.digits + string.punctuation
    return "".join(secrets.choice(alphabet) for _ in range(length))


class Command(BaseCommand):
    help = "Create a user account with optional API token generation and group assignment"

    def add_arguments(self, parser):
        # Required positional argument
        parser.add_argument(
            "username",
            type=str,
            help="Username to create",
        )

        # Optional arguments
        parser.add_argument(
            "--email",
            type=str,
            help="Email address (defaults to {username}@{ORCD_EMAIL_DOMAIN})",
        )
        parser.add_argument(
            "--password",
            type=str,
            help="Password (defaults to $ORCD_USER_PASSWORD env var, or generates random)",
        )
        parser.add_argument(
            "--with-token",
            action="store_true",
            help="Generate and display API token for the user",
        )
        parser.add_argument(
            "--add-to-group",
            type=str,
            action="append",
            choices=list(GROUP_MAP.keys()),
            help="Add user to a manager group (can be specified multiple times)",
        )
        parser.add_argument(
            "--active",
            dest="is_active",
            action="store_true",
            default=True,
            help="Set user as active (default)",
        )
        parser.add_argument(
            "--inactive",
            dest="is_active",
            action="store_false",
            help="Set user as inactive",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show the Django ORM commands that would be executed without making changes",
        )
        parser.add_argument(
            "--quiet",
            action="store_true",
            help="Suppress non-essential output",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Update existing user instead of reporting error",
        )

    def handle(self, *args, **options):
        username = options["username"]
        dry_run = options["dry_run"]
        quiet = options["quiet"]
        force = options["force"]

        # Determine email
        email = options.get("email")
        if not email:
            domain = os.environ.get("ORCD_EMAIL_DOMAIN", "")
            if domain:
                email = f"{username}@{domain}"
            else:
                email = ""

        # Determine password
        password = options.get("password")
        password_source = "provided via --password"
        if not password:
            password = os.environ.get("ORCD_USER_PASSWORD", "")
            if password:
                password_source = "from ORCD_USER_PASSWORD"
            else:
                password = generate_random_password()
                password_source = "generated random"

        is_active = options["is_active"]
        with_token = options["with_token"]
        groups_to_add = options.get("add_to_group") or []

        # Check if user already exists
        user_exists = User.objects.filter(username=username).exists()
        if user_exists and not force:
            self.stdout.write(self.style.ERROR(
                f"User '{username}' already exists. Use --force to update."
            ))
            return

        # Dry-run mode: print commands that would be executed
        if dry_run:
            self._print_dry_run(
                username=username,
                email=email,
                password_source=password_source,
                is_active=is_active,
                user_exists=user_exists,
                with_token=with_token,
                groups_to_add=groups_to_add,
            )
            return

        # Execute the commands
        if user_exists:
            user = User.objects.get(username=username)
            user.email = email
            user.is_active = is_active
            user.set_password(password)
            user.save()
            if not quiet:
                self.stdout.write(self.style.SUCCESS(
                    f"Updated existing user '{username}'"
                ))
        else:
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                is_active=is_active,
            )
            if not quiet:
                self.stdout.write(self.style.SUCCESS(
                    f"Created user '{username}' (email: {email or 'none'})"
                ))

        # Generate API token if requested
        if with_token:
            token = self._generate_token(user, quiet)
            if token:
                self.stdout.write(f"API Token: {token.key}")

        # Add to groups if requested
        for group_alias in groups_to_add:
            self._add_to_group(user, group_alias, quiet)

        # Summary
        if not quiet:
            self.stdout.write("")
            self.stdout.write(self.style.SUCCESS("User creation complete."))
            if password_source == "generated random":
                self.stdout.write(f"Password ({password_source}): {password}")

    def _print_dry_run(self, username, email, password_source, is_active,
                       user_exists, with_token, groups_to_add):
        """Print the Django ORM commands that would be executed."""
        self.stdout.write("")
        self.stdout.write(self.style.WARNING("[DRY-RUN] Would execute the following commands:"))
        self.stdout.write("")

        if user_exists:
            self.stdout.write("# Update existing user")
            self.stdout.write(f"user = User.objects.get(username='{username}')")
            self.stdout.write(f"user.email = '{email}'")
            self.stdout.write(f"user.is_active = {is_active}")
            self.stdout.write(f"user.set_password('<{password_source}>')")
            self.stdout.write("user.save()")
        else:
            self.stdout.write("# Create user")
            self.stdout.write("User.objects.create_user(")
            self.stdout.write(f"    username='{username}',")
            self.stdout.write(f"    email='{email}',")
            self.stdout.write(f"    password='<{password_source}>',")
            self.stdout.write(f"    is_active={is_active}")
            self.stdout.write(")")

        if with_token:
            self.stdout.write("")
            self.stdout.write("# Generate API token")
            self.stdout.write("from rest_framework.authtoken.models import Token")
            self.stdout.write(f"Token.objects.get_or_create(user=<User: {username}>)")

        for group_alias in groups_to_add:
            group_name = GROUP_MAP.get(group_alias)
            self.stdout.write("")
            self.stdout.write(f"# Add to {group_name} group")
            self.stdout.write(f"group = Group.objects.get(name='{group_name}')")
            self.stdout.write(f"group.user_set.add(<User: {username}>)")

        self.stdout.write("")
        self.stdout.write(self.style.WARNING("[DRY-RUN] No changes made."))

    def _generate_token(self, user, quiet):
        """Generate an API token for the user."""
        try:
            from rest_framework.authtoken.models import Token
        except ImportError:
            self.stdout.write(self.style.ERROR(
                "Django REST Framework authtoken not available. "
                "Make sure PLUGIN_API=True is set."
            ))
            return None

        token, created = Token.objects.get_or_create(user=user)
        if not quiet:
            if created:
                self.stdout.write(self.style.SUCCESS(
                    f"Generated new API token for '{user.username}'"
                ))
            else:
                self.stdout.write(self.style.WARNING(
                    f"Retrieved existing API token for '{user.username}'"
                ))
        return token

    def _add_to_group(self, user, group_alias, quiet):
        """Add user to a manager group."""
        group_name = GROUP_MAP.get(group_alias)
        if not group_name:
            self.stdout.write(self.style.ERROR(
                f"Unknown group alias: {group_alias}"
            ))
            return

        try:
            group = Group.objects.get(name=group_name)
        except Group.DoesNotExist:
            self.stdout.write(self.style.ERROR(
                f"Group '{group_name}' not found. "
                f"Run 'coldfront setup_{group_alias}_manager --create-group' first."
            ))
            return

        if group in user.groups.all():
            if not quiet:
                self.stdout.write(self.style.WARNING(
                    f"User '{user.username}' is already in '{group_name}' group"
                ))
        else:
            user.groups.add(group)
            if not quiet:
                self.stdout.write(self.style.SUCCESS(
                    f"Added '{user.username}' to '{group_name}' group"
                ))
