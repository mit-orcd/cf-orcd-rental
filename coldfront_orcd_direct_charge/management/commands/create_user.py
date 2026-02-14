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
    coldfront create_user jsmith --no-password --with-token  # OIDC-only account
    coldfront create_user jsmith --date-joined 2024-06-15
    coldfront create_user jsmith --last-modified 2025-01-20T14:30:00
    coldfront create_user jsmith --dry-run
"""

import os
import secrets
import string
from datetime import datetime

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User, Group
from django.utils import timezone


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

        # Password options (mutually exclusive)
        password_group = parser.add_mutually_exclusive_group()
        password_group.add_argument(
            "--password",
            type=str,
            help="Password (defaults to $ORCD_USER_PASSWORD env var, or generates random)",
        )
        password_group.add_argument(
            "--no-password",
            action="store_true",
            help="Create account with no password (OIDC/SSO-only authentication)",
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
            "--date-joined",
            type=str,
            help="Override creation date (YYYY-MM-DD or ISO 8601 datetime)",
        )
        parser.add_argument(
            "--last-modified",
            type=str,
            help="Override last-modified date (YYYY-MM-DD or ISO 8601 datetime)",
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

        # Determine password mode
        no_password = options.get("no_password", False)
        password = None
        password_source = None

        if no_password:
            # OIDC/SSO-only account - no password authentication
            password_source = "no password (OIDC/SSO-only)"
        else:
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

        # Parse optional date overrides
        date_joined = self._parse_datetime(options.get("date_joined"), "date-joined")
        last_modified = self._parse_datetime(options.get("last_modified"), "last-modified")

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
                no_password=no_password,
                date_joined=date_joined,
                last_modified=last_modified,
            )
            return

        # Execute the commands
        if user_exists:
            user = User.objects.get(username=username)
            user.email = email
            user.is_active = is_active
            if no_password:
                user.set_unusable_password()
            else:
                user.set_password(password)
            user.save()
            if not quiet:
                self.stdout.write(self.style.SUCCESS(
                    f"Updated existing user '{username}'"
                ))
                if no_password:
                    self.stdout.write(self.style.SUCCESS(
                        "Password disabled (OIDC/SSO-only authentication)"
                    ))
        else:
            if no_password:
                # Create user without password (OIDC/SSO-only)
                user = User.objects.create_user(
                    username=username,
                    email=email,
                )
                user.is_active = is_active
                user.set_unusable_password()
                user.save()
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
                if no_password:
                    self.stdout.write(self.style.SUCCESS(
                        "Password disabled (OIDC/SSO-only authentication)"
                    ))

        # Override date_joined if specified
        if date_joined is not None:
            User.objects.filter(pk=user.pk).update(date_joined=date_joined)
            user.refresh_from_db()
            if not quiet:
                self.stdout.write(self.style.SUCCESS(
                    f"Set date_joined to {date_joined.isoformat()}"
                ))

        # Override last_modified if specified
        if last_modified is not None:
            from coldfront_orcd_direct_charge.models import UserAccountTimestamp
            UserAccountTimestamp.objects.update_or_create(
                user=user,
                defaults={"last_modified": last_modified},
            )
            if not quiet:
                self.stdout.write(self.style.SUCCESS(
                    f"Set last_modified to {last_modified.isoformat()}"
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
            if not no_password and password_source == "generated random":
                self.stdout.write(f"Password ({password_source}): {password}")

    def _print_dry_run(self, username, email, password_source, is_active,
                       user_exists, with_token, groups_to_add, no_password=False,
                       date_joined=None, last_modified=None):
        """Print the Django ORM commands that would be executed."""
        self.stdout.write("")
        self.stdout.write(self.style.WARNING("[DRY-RUN] Would execute the following commands:"))
        self.stdout.write("")

        if user_exists:
            self.stdout.write("# Update existing user")
            self.stdout.write(f"user = User.objects.get(username='{username}')")
            self.stdout.write(f"user.email = '{email}'")
            self.stdout.write(f"user.is_active = {is_active}")
            if no_password:
                self.stdout.write("user.set_unusable_password()  # OIDC/SSO-only")
            else:
                self.stdout.write(f"user.set_password('<{password_source}>')")
            self.stdout.write("user.save()")
        else:
            if no_password:
                self.stdout.write("# Create user (OIDC/SSO-only - no password authentication)")
                self.stdout.write("user = User.objects.create_user(")
                self.stdout.write(f"    username='{username}',")
                self.stdout.write(f"    email='{email}'")
                self.stdout.write(")")
                self.stdout.write(f"user.is_active = {is_active}")
                self.stdout.write("user.set_unusable_password()  # Disable password login")
                self.stdout.write("user.save()")
            else:
                self.stdout.write("# Create user")
                self.stdout.write("User.objects.create_user(")
                self.stdout.write(f"    username='{username}',")
                self.stdout.write(f"    email='{email}',")
                self.stdout.write(f"    password='<{password_source}>',")
                self.stdout.write(f"    is_active={is_active}")
                self.stdout.write(")")

        if date_joined is not None:
            self.stdout.write("")
            self.stdout.write("# Override date_joined")
            self.stdout.write(
                f"User.objects.filter(pk=user.pk).update(date_joined='{date_joined.isoformat()}')"
            )

        if last_modified is not None:
            self.stdout.write("")
            self.stdout.write("# Override last_modified")
            self.stdout.write(
                f"UserAccountTimestamp.objects.update_or_create("
                f"user=user, defaults={{'last_modified': '{last_modified.isoformat()}'}})"
            )

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

    @staticmethod
    def _parse_datetime(value, flag_name):
        """Parse a date or datetime string into a timezone-aware datetime.

        Accepts ``YYYY-MM-DD`` (interpreted as midnight UTC) or any ISO 8601
        datetime string.  Returns ``None`` when *value* is ``None`` or empty.
        """
        if not value:
            return None
        try:
            # Try full ISO 8601 datetime first
            dt = datetime.fromisoformat(value)
        except ValueError:
            try:
                # Fall back to date-only (YYYY-MM-DD -> midnight)
                dt = datetime.strptime(value, "%Y-%m-%d")
            except ValueError:
                raise ValueError(
                    f"Invalid --{flag_name} value '{value}'. "
                    "Use YYYY-MM-DD or ISO 8601 datetime format."
                )
        # Ensure timezone-aware
        if dt.tzinfo is None:
            dt = timezone.make_aware(dt)
        return dt

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
